"use client";

import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
    Bell,
    BellRing,
    Check,
    Copy,
    QrCode,
    RefreshCw,
    ShieldAlert,
    Smartphone,
    Trash2,
    Radio,
    Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

type MobilePolicy = {
    enabled: boolean;
    minRiskScore: number;
    cooldownSeconds: number;
    notifyBruteForce: boolean;
    notifyCommandExec: boolean;
    notifySoarBlock: boolean;
};

type PairedDevice = {
    deviceId: string;
    deviceName: string;
    platform: string;
    hasFcmToken: boolean;
    pairedAtMs: number;
    lastSeenAtMs: number;
};

type PairingChallenge = {
    pairingCode: string;
    pairingToken: string;
    serverUrl: string;
    expiresAtMs: number;
    qrPayload: string;
};

const COOLDOWN_OPTIONS = [
    { label: "0s", value: 0 },
    { label: "30s", value: 30 },
    { label: "1m", value: 60 },
    { label: "5m", value: 300 },
];

export default function MobileAlertsPanel({
    onNotify,
}: {
    onNotify?: (message: string) => void;
}) {
    const [policy, setPolicy] = useState<MobilePolicy>({
        enabled: true,
        minRiskScore: 70,
        cooldownSeconds: 60,
        notifyBruteForce: true,
        notifyCommandExec: true,
        notifySoarBlock: true,
    });
    const [devices, setDevices] = useState<PairedDevice[]>([]);
    const [serverUrl, setServerUrl] = useState("https://192.168.1.10:8080");
    const [challenge, setChallenge] = useState<PairingChallenge | null>(null);
    const [remainingSec, setRemainingSec] = useState(0);
    const [copiedCode, setCopiedCode] = useState(false);
    const [loadingPair, setLoadingPair] = useState(false);
    const [sendingTest, setSendingTest] = useState(false);
    const [savingPolicy, setSavingPolicy] = useState(false);

    const loadMobileState = useCallback(async () => {
        try {
            const res = await fetch("/api/cloudsentinel/mobile");
            const data = await res.json();
            if (data?.ok) {
                if (data.policy) setPolicy(data.policy);
                if (Array.isArray(data.devices)) setDevices(data.devices);
            }
        } catch {
            // Keep defaults when offline
        }
    }, []);

    useEffect(() => {
        if (typeof window !== "undefined") {
            const host = window.location.hostname || "127.0.0.1";
            setServerUrl(`https://${host}:8080`);
        }
        void loadMobileState();
    }, [loadMobileState]);

    useEffect(() => {
        if (!challenge) {
            setRemainingSec(0);
            return;
        }
        const update = () => {
            const left = Math.max(0, Math.floor((challenge.expiresAtMs - Date.now()) / 1000));
            setRemainingSec(left);
            if (left <= 0) {
                setChallenge(null);
            }
        };
        update();
        const timer = window.setInterval(update, 1000);
        return () => window.clearInterval(timer);
    }, [challenge]);

    const handleGeneratePairing = async () => {
        setLoadingPair(true);
        try {
            const res = await fetch("/api/cloudsentinel/mobile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "pairing-token", serverUrl }),
            });
            const data = await res.json();
            if (data?.ok && data.pairingCode) {
                setChallenge({
                    pairingCode: data.pairingCode,
                    pairingToken: data.pairingToken,
                    serverUrl: data.serverUrl,
                    expiresAtMs: data.expiresAtMs,
                    qrPayload: data.qrPayload,
                });
                onNotify?.("Pairing QR code generated (valid for 5 minutes).");
            }
        } finally {
            setLoadingPair(false);
        }
    };

    const handleCopyCode = async () => {
        if (!challenge) return;
        try {
            await navigator.clipboard.writeText(challenge.pairingCode);
            setCopiedCode(true);
            setTimeout(() => setCopiedCode(false), 1800);
        } catch {
            // Ignore clipboard errors
        }
    };

    const handleSavePolicy = async () => {
        setSavingPolicy(true);
        try {
            const res = await fetch("/api/cloudsentinel/mobile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "config", policy }),
            });
            const data = await res.json();
            if (data?.ok) {
                onNotify?.("Mobile alert policy saved.");
            }
        } finally {
            setSavingPolicy(false);
        }
    };

    const handleSendTestAlert = async () => {
        setSendingTest(true);
        try {
            const res = await fetch("/api/cloudsentinel/mobile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "test-alert" }),
            });
            const data = await res.json();
            if (data?.ok) {
                const count = Number(data.dispatched ?? 0);
                onNotify?.(
                    count > 0
                        ? `Test alert dispatched to ${count} paired Android device${count === 1 ? "" : "s"}.`
                        : "Test alert queued. Pair an Android device to receive push alerts.",
                );
            }
        } finally {
            setSendingTest(false);
        }
    };

    const handleRevokeDevice = async (deviceId: string) => {
        try {
            const res = await fetch(`/api/cloudsentinel/mobile?deviceId=${encodeURIComponent(deviceId)}`, {
                method: "DELETE",
            });
            const data = await res.json();
            if (data?.ok) {
                setDevices((prev) => prev.filter((d) => d.deviceId !== deviceId));
                onNotify?.("Android device unlinked.");
            }
        } catch {
            // Ignore
        }
    };

    const formatCountdown = (sec: number) => {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${String(s).padStart(2, "0")}`;
    };

    return (
        <div className="space-y-4 animate-in fade-in duration-200">
            {/* Top Grid: 2 balanced cards */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {/* Left Card: QR Pairing & Endpoint */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col justify-between">
                    <div>
                        <div className="pb-3 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
                            <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-blue-500">
                                <QrCode size={15} /> Device Pairing (QR &amp; Token)
                            </h4>
                            <button
                                type="button"
                                onClick={handleSendTestAlert}
                                disabled={sendingTest}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10.5px] font-semibold transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                            >
                                <BellRing size={12} />
                                {sendingTest ? "Sending..." : "Test Alert"}
                            </button>
                        </div>

                        <div className="mt-3.5 space-y-3">
                            <div>
                                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                                    Sensor Admin API Endpoint
                                </label>
                                <input
                                    type="text"
                                    value={serverUrl}
                                    onChange={(e) => setServerUrl(e.target.value)}
                                    placeholder="https://192.168.1.10:8080"
                                    className="w-full h-8 rounded-lg bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-2.5 text-xs font-mono text-slate-900 dark:text-white outline-none focus:ring-1 focus:ring-blue-500"
                                />
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={handleGeneratePairing}
                                    disabled={loadingPair}
                                    className="h-8 inline-flex items-center gap-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all disabled:opacity-50 cursor-pointer shadow-xs"
                                >
                                    <RefreshCw size={12} className={loadingPair ? "animate-spin" : ""} />
                                    {challenge ? "Regenerate QR" : "Generate Pairing QR"}
                                </button>

                                {challenge && (
                                    <button
                                        type="button"
                                        onClick={handleCopyCode}
                                        className="h-8 inline-flex items-center gap-1.5 px-2.5 rounded-lg border border-blue-500/30 bg-blue-50/60 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 text-xs font-mono font-bold tracking-wider transition-colors cursor-pointer"
                                        title="Click to copy pairing code"
                                    >
                                        <span>Code: {challenge.pairingCode}</span>
                                        {copiedCode ? <Check size={12} /> : <Copy size={12} />}
                                    </button>
                                )}
                            </div>

                            {/* Centered QR Box */}
                            <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200/80 dark:border-white/10 bg-slate-50/70 dark:bg-black p-3 my-1">
                                {challenge ? (
                                    <div className="flex flex-col items-center gap-2">
                                        <div className="rounded-lg bg-white p-1.5 shadow-xs">
                                            <QRCodeSVG
                                                value={challenge.qrPayload}
                                                size={110}
                                                level="M"
                                                bgColor="#ffffff"
                                                fgColor="#050505"
                                            />
                                        </div>
                                        <span className="text-[10px] font-mono text-amber-500 font-semibold">
                                            Expires in {formatCountdown(remainingSec)}
                                        </span>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center justify-center text-center p-3 gap-1">
                                        <QrCode size={28} className="text-slate-300 dark:text-slate-700" />
                                        <span className="text-[10px] text-slate-400">
                                            Click Generate Pairing QR to connect your phone
                                        </span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Card: Policy Thresholds */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4 flex flex-col justify-between">
                    <div>
                        <div className="pb-3 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
                            <h4 className="font-display font-semibold text-[13px] tracking-tight flex items-center gap-2 text-amber-500">
                                <Bell size={15} /> Alert Policy &amp; Thresholds
                            </h4>
                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    role="switch"
                                    aria-checked={policy.enabled}
                                    onClick={() => setPolicy((p) => ({ ...p, enabled: !p.enabled }))}
                                    className={cn(
                                        "relative inline-flex h-4.5 w-8 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200",
                                        policy.enabled ? "bg-emerald-500" : "bg-slate-300 dark:bg-white/15"
                                    )}
                                >
                                    <span
                                        className={cn(
                                            "pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-xs transition duration-200",
                                            policy.enabled ? "translate-x-3.5" : "translate-x-0"
                                        )}
                                    />
                                </button>
                            </div>
                        </div>

                        <div className="mt-3.5 space-y-3.5">
                            {/* Minimum Risk Score */}
                            <div>
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="text-slate-600 dark:text-slate-300 font-medium">Minimum Risk Score</span>
                                    <span className="font-mono font-bold text-rose-500">{policy.minRiskScore}/100</span>
                                </div>
                                <input
                                    type="range"
                                    min={0}
                                    max={100}
                                    step={5}
                                    value={policy.minRiskScore}
                                    onChange={(e) => setPolicy((p) => ({ ...p, minRiskScore: Number(e.target.value) }))}
                                    className="w-full accent-blue-600 h-1 bg-slate-200 dark:bg-slate-800 rounded-lg cursor-pointer"
                                />
                            </div>

                            {/* Per-IP Cooldown */}
                            <div>
                                <span className="text-xs text-slate-600 dark:text-slate-300 font-medium block mb-1">
                                    Per-IP Alert Cooldown
                                </span>
                                <div className="grid grid-cols-4 gap-1.5">
                                    {COOLDOWN_OPTIONS.map((opt) => (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            onClick={() => setPolicy((p) => ({ ...p, cooldownSeconds: opt.value }))}
                                            className={cn(
                                                "py-1.5 text-[10.5px] font-mono rounded-md border transition-all cursor-pointer",
                                                policy.cooldownSeconds === opt.value
                                                    ? "border-blue-500/60 bg-blue-50 dark:bg-blue-500/15 text-blue-600 dark:text-blue-400 font-semibold"
                                                    : "border-slate-200 dark:border-white/10 text-slate-500 hover:bg-slate-50 dark:hover:bg-white/5"
                                            )}
                                        >
                                            {opt.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Trigger Event Pills */}
                            <div>
                                <span className="text-xs text-slate-600 dark:text-slate-300 font-medium block mb-1">
                                    Trigger Notifications
                                </span>
                                <div className="flex flex-wrap gap-1.5">
                                    {[
                                        { key: "notifyBruteForce", label: "SSH Brute Force" },
                                        { key: "notifyCommandExec", label: "Command Execution" },
                                        { key: "notifySoarBlock", label: "SOAR Containment" },
                                    ].map((item) => {
                                        const checked = policy[item.key as keyof MobilePolicy] as boolean;
                                        return (
                                            <button
                                                key={item.key}
                                                type="button"
                                                onClick={() => setPolicy((p) => ({ ...p, [item.key]: !checked }))}
                                                className={cn(
                                                    "px-2.5 py-1.5 rounded-md text-[10.5px] border transition-colors cursor-pointer flex items-center gap-1.5",
                                                    checked
                                                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium"
                                                        : "border-slate-200 dark:border-white/10 text-slate-400 hover:text-slate-600"
                                                )}
                                            >
                                                <span className={cn("w-1.5 h-1.5 rounded-full", checked ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-700")} />
                                                {item.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="pt-3 border-t border-slate-100 dark:border-white/5 flex justify-end">
                        <button
                            type="button"
                            onClick={handleSavePolicy}
                            disabled={savingPolicy}
                            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-xs transition cursor-pointer disabled:opacity-50"
                        >
                            {savingPolicy ? "Saving..." : "Save Alert Policy"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Bottom Full-Width Card: Paired Devices & Dispatch Stream */}
            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm p-4">
                <div className="pb-3 border-b border-slate-100 dark:border-white/5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <ShieldAlert size={15} className="text-emerald-500" />
                        <h4 className="font-display font-semibold text-[13px] tracking-tight text-slate-900 dark:text-white">
                            Paired Android Devices
                        </h4>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.04] text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-white/10">
                            {devices.length} Registered
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-emerald-500 flex items-center gap-1.5">
                            <Radio size={12} className="animate-pulse" />
                            FCM Push Bridge: Connected
                        </span>
                    </div>
                </div>

                <div className="mt-3">
                    {devices.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-slate-200 dark:border-white/10 p-4 text-center">
                            <Smartphone size={24} className="mx-auto text-slate-400 dark:text-slate-600 mb-1" />
                            <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                                No Android devices linked to this honeypot cluster yet
                            </p>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                                Generate a pairing QR code above and scan it using the CloudSentinel Android Companion app to receive live push alerts.
                            </p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                            {devices.map((dev) => (
                                <div
                                    key={dev.deviceId}
                                    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200/70 dark:border-white/[0.06] bg-slate-50/50 dark:bg-white/[0.015] p-3"
                                >
                                    <div className="flex items-center gap-2.5 min-w-0">
                                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
                                            <Smartphone size={15} />
                                        </div>
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-1.5">
                                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                                                    {dev.deviceName}
                                                </span>
                                                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 shrink-0">
                                                    {dev.hasFcmToken ? "FCM" : "Local"}
                                                </span>
                                            </div>
                                            <div className="text-[9.5px] font-mono text-slate-400 truncate">
                                                ID: {dev.deviceId.slice(0, 16)}...
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => void handleRevokeDevice(dev.deviceId)}
                                        className="p-1.5 text-rose-500 hover:bg-rose-500/10 rounded-md transition cursor-pointer shrink-0"
                                        title="Unlink device"
                                    >
                                        <Trash2 size={13} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
