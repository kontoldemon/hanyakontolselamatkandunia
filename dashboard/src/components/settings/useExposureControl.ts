"use client";

import { useEffect, useState } from "react";
import type { SensorOperations, WarRoomState } from "@/lib/liveEvents";

const EXPOSURE_STATE_KEY = "cloudsentinel.exposure.paused";

export type ExposureToast = {
    message: string;
    type: "success" | "error" | "info";
};

export function useExposureControl(
    operations: SensorOperations | null,
    warRoom: WarRoomState,
) {
    const [exposurePaused, setExposurePaused] = useState(() => {
        if (typeof window === "undefined") return false;
        return window.sessionStorage.getItem(EXPOSURE_STATE_KEY) === "1";
    });
    const [exposureBusy, setExposureBusy] = useState(false);
    const [toast, setToast] = useState<ExposureToast | null>(null);
    const [showExposureConfirm, setShowExposureConfirm] = useState(false);
    const [pendingExposurePaused, setPendingExposurePaused] = useState<boolean | null>(null);
    const [pendingEffectiveExposurePaused, setPendingEffectiveExposurePaused] = useState<boolean | null>(null);
    const [syncStartedAt, setSyncStartedAt] = useState<number | null>(null);
    const [exposureCooldownUntil, setExposureCooldownUntil] = useState<number>(0);
    const [cooldownNow, setCooldownNow] = useState<number>(() => Date.now());

    const sensorOnline = operations?.source === "live" || operations?.sensor.readiness.ok === true;
    const exposureSyncing = warRoom.exposure?.syncing === true;
    const effectiveExposureEnabled = warRoom.exposure?.effectiveEnabled;
    const cooldownRemainingSec = Math.max(0, Math.ceil((exposureCooldownUntil - cooldownNow) / 1000));
    const exposureCooldownActive = cooldownRemainingSec > 0;

    async function applyExposure(nextPaused: boolean) {
        setExposureBusy(true);
        setSyncStartedAt(Date.now());
        setPendingEffectiveExposurePaused(nextPaused);
        try {
            const response = await fetch("/api/cloudsentinel/exposure", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: !nextPaused }),
            });
            const data = await response.json();
            const hasPausedState = typeof data.paused === "boolean";
            if (hasPausedState) {
                const paused = Boolean(data.paused);
                setExposurePaused(paused);
                if (typeof window !== "undefined") {
                    window.sessionStorage.setItem(EXPOSURE_STATE_KEY, paused ? "1" : "0");
                }
            }
            if (data.ok) {
                const paused = hasPausedState ? Boolean(data.paused) : nextPaused;
                setToast({
                    message: paused ? "Applying offline state..." : "Applying online state...",
                    type: "info",
                });
            } else if (data.error === "cooldown_active") {
                const remainingMs = Number(data.cooldownRemainingMs ?? 0);
                if (Number.isFinite(remainingMs) && remainingMs > 0) {
                    setExposureCooldownUntil(Date.now() + remainingMs);
                }
                setExposureBusy(false);
                setPendingEffectiveExposurePaused(null);
                setToast({
                    message: `Exposure cooldown active. Try again in ${Math.max(1, Math.ceil(remainingMs / 1000))}s.`,
                    type: "info",
                });
                return;
            } else if (hasPausedState) {
                const paused = Boolean(data.paused);
                setExposureBusy(false);
                setPendingEffectiveExposurePaused(null);
                setToast({
                    message: paused
                        ? "Exposure switched to offline with partial backend warning."
                        : "Exposure switched to online with partial backend warning.",
                    type: "info",
                });
            } else {
                setExposureBusy(false);
                setPendingEffectiveExposurePaused(null);
                setToast({ message: data.error ?? "Exposure update failed.", type: "error" });
            }
        } catch {
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setToast({ message: "Exposure update failed.", type: "error" });
        }
    }

    function openExposureConfirm() {
        if (exposureBusy || exposureSyncing || exposureCooldownActive || !sensorOnline) return;
        setPendingExposurePaused(!exposurePaused);
        setShowExposureConfirm(true);
    }

    async function confirmExposureToggle() {
        if (pendingExposurePaused === null) {
            setShowExposureConfirm(false);
            return;
        }
        setShowExposureConfirm(false);
        await applyExposure(pendingExposurePaused);
        setPendingExposurePaused(null);
    }

    function cancelExposureConfirm() {
        setShowExposureConfirm(false);
        setPendingExposurePaused(null);
        setToast({ message: "Exposure update cancelled.", type: "info" });
    }

    useEffect(() => {
        if (!toast) return;
        const timer = window.setTimeout(() => setToast(null), 2500);
        return () => window.clearTimeout(timer);
    }, [toast]);

    useEffect(() => {
        const timer = window.setInterval(() => setCooldownNow(Date.now()), 500);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        if (!exposureSyncing || !syncStartedAt) {
            return;
        }
        const timer = window.setInterval(() => {
            const elapsed = Date.now() - syncStartedAt;
            if (elapsed < 8000) {
                return;
            }
            setToast({
                message: "Exposure sync taking too long. Keeping last effective state.",
                type: "error",
            });
            if (typeof effectiveExposureEnabled === "boolean") {
                const paused = !effectiveExposureEnabled;
                setExposurePaused(paused);
                if (typeof window !== "undefined") {
                    window.sessionStorage.setItem(EXPOSURE_STATE_KEY, paused ? "1" : "0");
                }
            }
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setSyncStartedAt(null);
        }, 400);
        return () => window.clearInterval(timer);
    }, [exposureSyncing, syncStartedAt, effectiveExposureEnabled]);

    useEffect(() => {
        if (pendingEffectiveExposurePaused === null || typeof effectiveExposureEnabled !== "boolean" || exposureSyncing) {
            return;
        }
        const effectivePaused = !effectiveExposureEnabled;
        if (effectivePaused !== pendingEffectiveExposurePaused) {
            return;
        }
        const timer = window.setTimeout(() => {
            setExposurePaused(effectivePaused);
            if (typeof window !== "undefined") {
                window.sessionStorage.setItem(EXPOSURE_STATE_KEY, effectivePaused ? "1" : "0");
            }
            setExposureCooldownUntil(Date.now() + 8000);
            setExposureBusy(false);
            setPendingEffectiveExposurePaused(null);
            setSyncStartedAt(null);
            setToast({
                message: effectivePaused ? "Honeypot exposure set to offline." : "Honeypot exposure set to online.",
                type: "success",
            });
        }, 0);
        return () => window.clearTimeout(timer);
    }, [pendingEffectiveExposurePaused, effectiveExposureEnabled, exposureSyncing]);

    return {
        exposurePaused,
        exposureBusy,
        toast,
        showExposureConfirm,
        pendingExposurePaused,
        cooldownRemainingSec,
        exposureCooldownActive,
        sensorOnline,
        exposureSyncing,
        effectiveExposureEnabled,
        openExposureConfirm,
        confirmExposureToggle,
        cancelExposureConfirm,
    };
}
