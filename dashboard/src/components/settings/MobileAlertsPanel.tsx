"use client";

import { useCallback, useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
    BellRing,
    Check,
    Copy,
    QrCode,
    RefreshCw,
    Smartphone,
    Trash2,
    Link2,
    Maximize2,
    X,
} from "lucide-react";
import { cn } from "@/lib/utils";

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

export default function MobileAlertsPanel({
    onNotify,
}: {
    onNotify?: (message: string) => void;
}) {
    const [devices, setDevices] = useState<PairedDevice[]>([]);
    const [serverUrl, setServerUrl] = useState("http://127.0.0.1:8080");
    const [challenge, setChallenge] = useState<PairingChallenge | null>(null);
    const [remainingSec, setRemainingSec] = useState(0);
    const [copiedCode, setCopiedCode] = useState(false);
    const [copiedToken, setCopiedToken] = useState(false);
    const [copiedLink, setCopiedLink] = useState(false);
    const [isQrModalOpen, setIsQrModalOpen] = useState(false);
    const [isClosingQrModal, setIsClosingQrModal] = useState(false);
    const [loadingPair, setLoadingPair] = useState(false);
    const [sendingTest, setSendingTest] = useState(false);

    const closeQrModal = useCallback(() => {
        if (isClosingQrModal) return;
        setIsClosingQrModal(true);
        setTimeout(() => {
            setIsQrModalOpen(false);
            setIsClosingQrModal(false);
        }, 180);
    }, [isClosingQrModal]);

    useEffect(() => {
        if (!isQrModalOpen) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") closeQrModal();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [isQrModalOpen, closeQrModal]);

    const loadMobileState = useCallback(async () => {
        try {
            const res = await fetch("/api/cloudsentinel/mobile");
            const data = await res.json();
            if (data?.ok) {
                if (Array.isArray(data.devices)) setDevices(data.devices);
                if (typeof data.serverUrl === "string" && data.serverUrl) {
                    setServerUrl(data.serverUrl);
                }
            }
        } catch {
            // Keep defaults when offline
        }
    }, []);

    useEffect(() => {
        if (typeof window !== "undefined") {
            const proto = window.location.protocol === "https:" ? "https:" : "http:";
            const host = window.location.hostname || "127.0.0.1";
            setServerUrl(`${proto}//${host}:8080`);
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
            } else {
                onNotify?.(`Pairing failed: ${data?.error ?? "sensor unreachable"}`);
            }
        } catch {
            onNotify?.("Pairing failed: sensor unreachable");
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

    const handleCopyToken = async () => {
        if (!challenge) return;
        try {
            await navigator.clipboard.writeText(challenge.pairingToken);
            setCopiedToken(true);
            setTimeout(() => setCopiedToken(false), 1800);
        } catch {
            // Ignore clipboard errors
        }
    };

    const handleCopyLink = async () => {
        if (!challenge) return;
        try {
            const deepLink = `cloudsentinel://pair?server=${encodeURIComponent(challenge.serverUrl)}&code=${encodeURIComponent(challenge.pairingCode)}&token=${encodeURIComponent(challenge.pairingToken)}`;
            await navigator.clipboard.writeText(deepLink);
            setCopiedLink(true);
            setTimeout(() => setCopiedLink(false), 1800);
            onNotify?.("One-click pairing link copied to clipboard.");
        } catch {
            // Ignore clipboard errors
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
            } else {
                onNotify?.(`Test alert failed: ${data?.error ?? "sensor unreachable"}`);
            }
        } catch {
            onNotify?.("Test alert failed: sensor unreachable");
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
            } else {
                onNotify?.(`Unlink failed: ${data?.error ?? "sensor unreachable"}`);
            }
        } catch {
            onNotify?.("Unlink failed: sensor unreachable");
        }
    };

    const formatCountdown = (sec: number) => {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${String(s).padStart(2, "0")}`;
    };

    return (
        <div className="space-y-3.5 animate-in fade-in duration-200">
            {/* 1. Device Pairing (QR & One-Click Link) - Full Width Card */}
            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex items-center justify-between">
                    <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                        <QrCode size={14} className="text-blue-500" /> Device Pairing (QR &amp; Link)
                    </h3>
                    <button
                        type="button"
                        onClick={handleSendTestAlert}
                        disabled={sendingTest}
                        className="h-9 sm:h-7.5 inline-flex items-center gap-1.5 px-3 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-semibold transition-all active:scale-95 disabled:opacity-50 cursor-pointer shrink-0"
                    >
                        <BellRing size={12} />
                        <span>{sendingTest ? "Sending..." : "Test Alert"}</span>
                    </button>
                </div>

                <div className="divide-y divide-slate-100 dark:divide-white/5">
                    {/* Endpoint Configuration */}
                    <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                        <div className="min-w-0 sm:pr-2">
                            <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Sensor Admin API Endpoint</label>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Target gateway URL that companion devices connect to.</p>
                        </div>
                        <div className="w-full sm:w-72 shrink-0">
                            <input
                                type="text"
                                value={serverUrl}
                                onChange={(e) => setServerUrl(e.target.value)}
                                placeholder="http://127.0.0.1:8080"
                                className="w-full h-10 sm:h-8 rounded-lg bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-3 text-xs font-mono text-slate-900 dark:text-white outline-none focus:ring-1 focus:ring-blue-500"
                            />
                        </div>
                    </div>

                    {/* Pairing Execution Area */}
                    <div className="px-4 py-3 sm:px-5">
                        {!challenge ? (
                            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-xl border border-dashed border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-white/[0.01]">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-9 h-9 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
                                        <QrCode size={18} />
                                    </div>
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-slate-900 dark:text-white">Generate Companion Pairing Token</div>
                                        <p className="text-[11px] text-slate-400 truncate">Create a 5-minute cryptographic session to pair your Android device.</p>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={handleGeneratePairing}
                                    disabled={loadingPair}
                                    className="h-10 sm:h-8 shrink-0 inline-flex items-center gap-1.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition active:scale-95 disabled:opacity-50 cursor-pointer shadow-xs"
                                >
                                    <RefreshCw size={12} className={loadingPair ? "animate-spin" : ""} />
                                    <span>Generate Pairing</span>
                                </button>
                            </div>
                        ) : (
                            <div className="p-3.5 rounded-xl border border-blue-500/30 bg-blue-500/[0.02] space-y-3">
                                <div className="flex flex-col sm:flex-row items-center gap-5">
                                    {/* QR Code */}
                                    <div className="flex flex-col items-center gap-1.5 shrink-0">
                                        <div
                                            onClick={() => setIsQrModalOpen(true)}
                                            className="relative group rounded-xl bg-white p-2 shadow-sm cursor-pointer border border-slate-200 transition-all hover:scale-105"
                                            title="Click to zoom in fullscreen"
                                        >
                                            <QRCodeSVG
                                                value={challenge.qrPayload}
                                                size={100}
                                                level="M"
                                                bgColor="#ffffff"
                                                fgColor="#050505"
                                            />
                                            <div className="absolute inset-0 bg-black/40 rounded-xl flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-[1px]">
                                                <Maximize2 size={16} className="text-white drop-shadow" />
                                            </div>
                                        </div>
                                        <div className="flex items-center justify-center text-[10.5px]">
                                            <span className="font-mono text-amber-500 font-semibold">{formatCountdown(remainingSec)}</span>
                                        </div>
                                    </div>

                                    {/* Methods and Actions */}
                                    <div className="flex-1 min-w-0 space-y-2.5 w-full">
                                        <div className="flex items-center justify-between gap-2">
                                            <span className="text-xs font-semibold text-slate-900 dark:text-white">Active Pairing Session</span>
                                            <button
                                                type="button"
                                                onClick={handleGeneratePairing}
                                                disabled={loadingPair}
                                                className="h-9 px-1 inline-flex items-center gap-1 text-[11px] text-blue-500 hover:text-blue-400 font-medium cursor-pointer sm:h-6"
                                            >
                                                <RefreshCw size={11} className={loadingPair ? "animate-spin" : ""} />
                                                Regenerate
                                            </button>
                                        </div>

                                        <button
                                            type="button"
                                            onClick={handleCopyLink}
                                            className="w-full h-10 sm:h-8.5 flex items-center justify-center gap-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition active:scale-95 cursor-pointer shadow-xs"
                                        >
                                            {copiedLink ? <Check size={13} className="text-emerald-300" /> : <Link2 size={13} />}
                                            <span>{copiedLink ? "Pairing Link Copied to Clipboard!" : "Copy One-Click Pairing Link"}</span>
                                        </button>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            <button
                                                type="button"
                                                onClick={handleCopyCode}
                                                className="h-10 sm:h-8 flex items-center justify-between px-3 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.04] hover:bg-slate-50 dark:hover:bg-white/[0.08] text-slate-800 dark:text-slate-200 text-xs font-mono font-medium transition cursor-pointer"
                                            >
                                                <span className="truncate">Code: <strong className="text-blue-500">{challenge.pairingCode}</strong></span>
                                                {copiedCode ? <Check size={12} className="text-emerald-500 shrink-0" /> : <Copy size={12} className="text-slate-400 shrink-0" />}
                                            </button>
                                            <button
                                                type="button"
                                                onClick={handleCopyToken}
                                                className="h-10 sm:h-8 flex items-center justify-between px-3 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-white/[0.04] hover:bg-slate-50 dark:hover:bg-white/[0.08] text-slate-800 dark:text-slate-200 text-xs font-mono font-medium transition cursor-pointer"
                                            >
                                                <span className="truncate">Token: <strong className="text-purple-500">{challenge.pairingToken.slice(0, 6)}...</strong></span>
                                                {copiedToken ? <Check size={12} className="text-emerald-500 shrink-0" /> : <Copy size={12} className="text-slate-400 shrink-0" />}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Linked Devices Section */}
                    <div className="px-4 py-2.5 sm:px-5">
                        <div className="flex items-center gap-2 py-1">
                            <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                                <Smartphone size={13} className="text-slate-500" /> Linked Android Devices
                            </span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.04] text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-white/10">
                                {devices.length} Registered
                            </span>
                        </div>
                        {devices.length === 0 ? (
                            <div className="py-2 text-xs text-slate-400">
                                No Android devices linked yet.
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 dark:divide-white/5 mt-1">
                                {devices.map((dev) => (
                                    <div
                                        key={dev.deviceId}
                                        className="py-2 flex items-center justify-between gap-3"
                                    >
                                        <div className="flex items-center gap-2.5 min-w-0">
                                            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
                                                <Smartphone size={14} />
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
                                            className="flex h-9 w-9 items-center justify-center text-rose-500 hover:bg-rose-500/10 rounded-md transition cursor-pointer shrink-0"
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

            <p className="text-[11px] text-slate-500 dark:text-slate-400 px-1">
                Alert thresholds, per-IP cooldowns, and trigger filters are configured directly inside the CloudSentinel Android app.
            </p>

            {/* Fullscreen QR Lightbox Modal */}
            {isQrModalOpen && challenge && (
                <div
                    className={cn(
                        "fixed inset-0 z-[200] bg-black/60 backdrop-blur-md flex items-center justify-center p-4",
                        isClosingQrModal ? "animate-overlay-out" : "animate-overlay-in"
                    )}
                    onClick={closeQrModal}
                >
                    <div
                        className={cn(
                            "relative max-w-[320px] w-full overflow-hidden rounded-3xl border border-slate-200/80 bg-white/95 p-6 text-center shadow-2xl backdrop-blur-2xl dark:border-white/10 dark:bg-[#0c0c0e] dark:shadow-[0_24px_60px_rgba(0,0,0,0.8)] flex flex-col items-center gap-3",
                            isClosingQrModal ? "animate-modal-out" : "animate-modal-in"
                        )}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <button
                            type="button"
                            onClick={closeQrModal}
                            className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition cursor-pointer"
                            title="Close"
                        >
                            <X size={15} />
                        </button>

                        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/80 bg-slate-100/80 text-blue-600 shadow-sm dark:border-white/10 dark:bg-white/[0.05] dark:text-blue-400">
                            <QrCode size={18} />
                        </div>

                        <div className="text-center">
                            <h3 className="font-display text-base font-bold tracking-tight text-slate-900 dark:text-white">
                                Scan Pairing Code
                            </h3>
                        </div>

                        <div className="p-2.5 bg-white rounded-2xl shadow-sm border border-slate-200">
                            <QRCodeSVG
                                value={challenge.qrPayload}
                                size={190}
                                level="H"
                                bgColor="#ffffff"
                                fgColor="#050505"
                            />
                        </div>

                        <div className="w-full space-y-2">
                            <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 text-xs font-mono">
                                <span className="text-slate-500">Pairing Code:</span>
                                <strong className="text-sm font-bold text-blue-500 tracking-wider">
                                    {challenge.pairingCode}
                                </strong>
                            </div>

                            <div className="flex items-center justify-between text-[11px] text-slate-500 px-1">
                                <span>Expires in:</span>
                                <span className="font-mono font-semibold text-amber-500">
                                    {formatCountdown(remainingSec)}
                                </span>
                            </div>

                            <button
                                type="button"
                                onClick={handleCopyLink}
                                className="w-full inline-flex h-11 items-center justify-center gap-1.5 rounded-full bg-blue-600 hover:bg-blue-500 px-4 text-xs font-semibold text-white shadow-sm transition active:scale-95 cursor-pointer"
                            >
                                {copiedLink ? <Check size={13} className="text-emerald-300" /> : <Link2 size={13} />}
                                <span>{copiedLink ? "Link Copied!" : "Copy One-Click Link"}</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
