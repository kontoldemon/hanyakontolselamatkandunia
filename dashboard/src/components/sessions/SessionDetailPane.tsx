"use client";

import { ArrowLeft, Ban, Check, Copy, Fingerprint, Shield, ShieldAlert, Terminal } from "lucide-react";
import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import type { CapturedSession } from "@/lib/liveEvents";
import TerminalReplay from "@/components/sessions/TerminalReplay";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import {
    blockStateText,
    formatSeenTime,
    formatSoarAction,
    isBlockEffective,
} from "@/components/sessions/SessionListRow";

const MITRE_NAMES: Record<string, string> = {
    "T1059": "Command & Scripting",
    "T1059.004": "Unix Shell",
    "T1087": "Account Discovery",
    "T1087.001": "Local Accounts",
    "T1078": "Valid Accounts",
    "T1110": "Brute Force",
    "T1105": "Ingress Tool Transfer",
    "T1222": "Permissions Modification",
    "T1222.002": "Linux Permissions",
    "T1496": "Resource Hijacking",
    "T1046": "Network Scanning",
    "T1552": "Unsecured Credentials",
    "T1552.004": "Private Keys",
    "T1098": "Account Manipulation",
    "T1098.004": "SSH Authorized Keys",
    "T1057": "Process Discovery",
    "T1082": "System Info Discovery",
    "T1053": "Scheduled Task/Job",
    "T1053.003": "Cron Job",
    "T1033": "System Owner Discovery",
    "T1016": "Network Config Discovery",
    "T1049": "System Network Discovery",
    "T1571": "Non-Standard Port",
    "T1562": "Impair Defenses",
};

interface SessionDetailPaneProps {
    selectedSessionId: string | null;
    selectedView: CapturedSession | null;
    replayMode: "attacker" | "both";
    onReplayModeChange: (mode: "attacker" | "both") => void;
    onClearSelection: () => void;
    blockingIp: string | null;
    confirmBlockIp: string | null;
    onRequestBlockIp: (ip: string | null) => void;
    onConfirmBlockIp: (ip: string) => void;
}

export default function SessionDetailPane({
    selectedSessionId,
    selectedView,
    replayMode,
    onReplayModeChange,
    onClearSelection,
    blockingIp,
    confirmBlockIp,
    onRequestBlockIp,
    onConfirmBlockIp,
}: SessionDetailPaneProps) {
    const [copiedField, setCopiedField] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<"forensics" | "mitre" | "soar">("forensics");
    const scrollRef = useRef<HTMLDivElement>(null);
    const [showScrollDown, setShowScrollDown] = useState(false);

    const handleScroll = useCallback(() => {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const dist = el.scrollHeight - (el.scrollTop + el.clientHeight);
        setShowScrollDown(dist > 35);
    }, []);

    const scrollToBottom = useCallback(() => {
        if (!scrollRef.current) return;
        scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth",
        });
        setShowScrollDown(false);
    }, []);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (!scrollRef.current) return;
            const el = scrollRef.current;
            setShowScrollDown(el.scrollHeight - el.clientHeight > 35);
        }, 120);
        return () => clearTimeout(timer);
    }, [activeTab, selectedView?.id]);

    const handleCopy = (fieldKey: string, text: string) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setCopiedField(fieldKey);
        setTimeout(() => setCopiedField(null), 1500);
    };

    const selectedAction = formatSoarAction(selectedView?.soarAction);
    const selectedBlocked = isBlockEffective(selectedView?.soarAction, selectedView?.blockEffective);
    const riskScore = selectedView?.riskScore ?? 85;

    return (
        <>
            <div className={cn("flex-1 flex flex-col h-full bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/5 rounded-xl shadow-sm overflow-hidden", !selectedSessionId ? "hidden md:flex items-center justify-center" : "flex")}>
                {!selectedView ? (
                    <div className="text-center text-slate-500 flex flex-col items-center gap-3">
                        <Terminal size={32} className="opacity-20" />
                        <p className="text-sm">Select a session to view details &amp; replay</p>
                    </div>
                ) : (
                    <>
                        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-white/5 flex items-center justify-between shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
                            <div className="flex items-center gap-2.5 min-w-0">
                                <button onClick={onClearSelection} className="md:hidden p-1 -ml-1 hover:bg-slate-100 dark:hover:bg-white/10 rounded shrink-0">
                                    <ArrowLeft size={16} />
                                </button>
                                <h2 className="font-mono text-sm md:text-base font-bold text-slate-900 dark:text-white tracking-tight leading-none truncate">
                                    {selectedView.ip}
                                </h2>
                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200/60 dark:bg-white/5 text-slate-500 dark:text-slate-400 border border-slate-300/40 dark:border-white/10 shrink-0">
                                    Port 22/TCP
                                </span>
                            </div>
                            <button
                                onClick={() => onRequestBlockIp(selectedView.ip)}
                                disabled={blockingIp === selectedView.ip}
                                className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 text-red-600 dark:text-red-400 hover:bg-red-500 hover:text-white disabled:opacity-50 transition-colors shrink-0"
                                title="Block IP at sensor firewall"
                                aria-label="Block IP"
                            >
                                <Ban size={14} />
                            </button>
                        </div>

                        <div className="grid grid-cols-1 xl:grid-cols-3 flex-1 min-h-0 overflow-hidden">
                            <div className="xl:col-span-2 border-b xl:border-b-0 xl:border-r border-slate-200 dark:border-white/5 flex flex-col h-full min-h-0 overflow-hidden">
                                <TerminalReplay
                                    lines={selectedView.input ?? []}
                                    replay={selectedView.replay}
                                    mode={replayMode}
                                    onModeChange={onReplayModeChange}
                                    isSeamless
                                />
                            </div>

                            <div className="xl:col-span-1 bg-slate-50/50 dark:bg-white/[0.01] p-3 flex flex-col h-full overflow-hidden">
                                {/* Minimalist Icon-only Tab Switcher */}
                                <div className="grid grid-cols-3 p-1 bg-slate-200/60 dark:bg-[#0c0d10] rounded-lg border border-slate-300/40 dark:border-white/5 shrink-0 mb-3 gap-1">
                                    <button
                                        type="button"
                                        onClick={() => setActiveTab("forensics")}
                                        title="Forensic Profile"
                                        aria-label="Forensic Profile"
                                        className={cn(
                                            "flex items-center justify-center py-2 px-2 rounded-md transition-all",
                                            activeTab === "forensics"
                                                ? "bg-white dark:bg-white/10 text-indigo-500 shadow-sm"
                                                : "text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
                                        )}
                                    >
                                        <Fingerprint size={16} />
                                    </button>

                                    <button
                                        type="button"
                                        onClick={() => setActiveTab("mitre")}
                                        title="MITRE ATT&CK Techniques"
                                        aria-label="MITRE ATT&CK Techniques"
                                        className={cn(
                                            "flex items-center justify-center py-2 px-2 rounded-md transition-all",
                                            activeTab === "mitre"
                                                ? "bg-white dark:bg-white/10 text-red-500 shadow-sm"
                                                : "text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
                                        )}
                                    >
                                        <div className="relative inline-flex items-center justify-center">
                                            <ShieldAlert size={16} />
                                            {selectedView.mitreTechniques && selectedView.mitreTechniques.length > 0 && (
                                                <span className={cn(
                                                    "absolute -top-1.5 -right-2.5 h-3.5 min-w-4 px-1 rounded-full font-mono font-bold border shadow-xs flex items-center justify-center leading-none text-center",
                                                    selectedView.mitreTechniques.length > 99
                                                        ? "text-[6px]"
                                                        : selectedView.mitreTechniques.length > 9
                                                            ? "text-[7.5px]"
                                                            : "text-[8.5px]",
                                                    activeTab === "mitre"
                                                        ? "bg-red-500 text-white border-red-600"
                                                        : "bg-slate-100 dark:bg-[#14161f] text-red-600 dark:text-red-400 border-red-500/40"
                                                )}>
                                                    <span className="translate-y-[0.5px]">
                                                        {selectedView.mitreTechniques.length}
                                                    </span>
                                                </span>
                                            )}
                                        </div>
                                    </button>

                                    <button
                                        type="button"
                                        onClick={() => setActiveTab("soar")}
                                        title="SOAR Response & Defense"
                                        aria-label="SOAR Response & Defense"
                                        className={cn(
                                            "flex items-center justify-center py-2 px-2 rounded-md transition-all",
                                            activeTab === "soar"
                                                ? "bg-white dark:bg-white/10 text-blue-500 shadow-sm"
                                                : "text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
                                        )}
                                    >
                                        <div className="relative inline-flex items-center justify-center">
                                            <Shield size={16} />
                                            <span className={cn(
                                                "absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ring-2",
                                                activeTab === "soar" ? "ring-white dark:ring-[#14171f]" : "ring-slate-200 dark:ring-[#0c0d10]",
                                                selectedBlocked ? "bg-rose-500" : "bg-emerald-500"
                                            )} />
                                        </div>
                                    </button>
                                </div>

                                <div className="relative flex-1 min-h-0 flex flex-col">
                                    <div
                                        ref={scrollRef}
                                        onScroll={handleScroll}
                                        className="flex-1 min-h-0 overflow-y-auto terminal-scrollbar pr-0.5 space-y-3 pb-8"
                                    >
                                    {activeTab === "forensics" && (
                                        <div className="flex flex-col gap-2.5">
                                            {/* Threat Risk Assessment Bar */}
                                            <div className="bg-white dark:bg-[#0c0d10] py-1.5 px-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="text-[10.5px] font-semibold text-slate-800 dark:text-slate-200">Threat Assessment</span>
                                                    <span className={cn(
                                                        "text-[9.5px] font-mono px-1.5 py-0.5 rounded font-bold border",
                                                        riskScore >= 80
                                                            ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                                                            : riskScore >= 50
                                                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                                                                : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                                                    )}>
                                                        Risk {riskScore}/100
                                                    </span>
                                                </div>
                                                <div className="w-full h-1 bg-slate-100 dark:bg-white/5 rounded-full overflow-hidden">
                                                    <div
                                                        className={cn(
                                                            "h-full rounded-full transition-all",
                                                            riskScore >= 80 ? "bg-red-500" : riskScore >= 50 ? "bg-amber-500" : "bg-emerald-500"
                                                        )}
                                                        style={{ width: `${Math.min(100, Math.max(5, riskScore))}%` }}
                                                    />
                                                </div>
                                            </div>

                                            {/* Forensics Fields (Full Width Clean Rows) */}
                                            <div className="flex flex-col gap-2 text-xs font-mono">
                                                <div
                                                    onClick={() => handleCopy("network", selectedView.org || selectedView.isp || selectedView.asn || "")}
                                                    className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5 cursor-pointer hover:border-slate-300 dark:hover:border-white/20 transition-colors group relative"
                                                    title="Click to copy network"
                                                >
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <span className="text-[10px] text-slate-400 font-sans">Network / ASN</span>
                                                        {copiedField === "network" ? (
                                                            <span className="text-[9px] text-emerald-500 font-semibold flex items-center gap-0.5"><Check size={10} /> Copied!</span>
                                                        ) : (
                                                            <Copy size={10} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                        )}
                                                    </div>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs block font-medium leading-snug break-words">
                                                        {selectedView.org || selectedView.isp || selectedView.asn || "Unknown"}
                                                    </span>
                                                </div>

                                                <div
                                                    onClick={() => handleCopy("hassh", selectedView.fingerprint || "")}
                                                    className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5 cursor-pointer hover:border-slate-300 dark:hover:border-white/20 transition-colors group relative"
                                                    title="Click to copy full HASSH"
                                                >
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <span className="text-[10px] text-slate-400 font-sans">HASSH Fingerprint</span>
                                                        {copiedField === "hassh" ? (
                                                            <span className="text-[9px] text-emerald-500 font-semibold flex items-center gap-0.5"><Check size={10} /> Copied!</span>
                                                        ) : (
                                                            <Copy size={10} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                        )}
                                                    </div>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs font-medium block truncate">
                                                        {selectedView.fingerprint || "N/A"}
                                                    </span>
                                                </div>

                                                <div
                                                    onClick={() => handleCopy("client", selectedView.client || "")}
                                                    className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5 cursor-pointer hover:border-slate-300 dark:hover:border-white/20 transition-colors group relative"
                                                    title="Click to copy SSH banner"
                                                >
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <span className="text-[10px] text-slate-400 font-sans">SSH Client Banner</span>
                                                        {copiedField === "client" ? (
                                                            <span className="text-[9px] text-emerald-500 font-semibold flex items-center gap-0.5"><Check size={10} /> Copied!</span>
                                                        ) : (
                                                            <Copy size={10} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                        )}
                                                    </div>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs break-all block font-medium leading-snug">
                                                        {selectedView.client || "OpenSSH"}
                                                    </span>
                                                </div>

                                                <div className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                    <span className="text-[10px] text-slate-400 block mb-0.5 font-sans">Origin Location</span>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs block font-medium leading-snug">
                                                        {selectedView.city ? `${selectedView.city}, ` : ""}{selectedView.countryName || selectedView.country || "Unknown"}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Session Activity Metrics */}
                                            <div className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-slate-100 dark:border-white/5">
                                                    <span className="text-[10px] font-sans font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                                        Session Metrics
                                                    </span>
                                                    <span className="text-[10px] font-mono text-slate-400">Telemetry</span>
                                                </div>
                                                <div className="flex flex-col gap-1.5 text-[11px]">
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-sans text-slate-500 dark:text-slate-400">Duration</span>
                                                        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{selectedView.duration || "N/A"}</span>
                                                    </div>
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-sans text-slate-500 dark:text-slate-400">Commands Run</span>
                                                        <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{selectedView.input?.length ?? 0}</span>
                                                    </div>
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-sans text-slate-500 dark:text-slate-400">First Seen</span>
                                                        <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{formatSeenTime(selectedView.firstSeenEpochMs ?? selectedView.startedAtEpochMs)}</span>
                                                    </div>
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-sans text-slate-500 dark:text-slate-400">Last Active</span>
                                                        <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{formatSeenTime(selectedView.lastSeenEpochMs ?? selectedView.firstSeenEpochMs ?? selectedView.startedAtEpochMs)}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {activeTab === "mitre" && (
                                        <div className="flex flex-col gap-2.5">
                                            <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60 dark:border-white/5">
                                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">Adversary TTPs</span>
                                                <span className="text-[10px] font-mono px-2 py-0.5 rounded font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20">
                                                    {selectedView.mitreTechniques?.length ?? 0} Detected
                                                </span>
                                            </div>

                                            {selectedView.mitreTechniques && selectedView.mitreTechniques.length > 0 ? (
                                                <div className="flex flex-col gap-1.5 font-mono">
                                                    {selectedView.mitreTechniques.map((technique) => (
                                                        <div
                                                            key={technique}
                                                            className="flex items-center justify-between px-2.5 py-2 rounded-lg bg-red-500/[0.06] border border-red-500/15 text-xs hover:bg-red-500/10 transition-colors gap-2"
                                                        >
                                                            <div className="flex flex-col min-w-0">
                                                                <span className="text-red-600 dark:text-red-300 font-semibold tracking-tight">{technique}</span>
                                                                {MITRE_NAMES[technique] && (
                                                                    <span className="text-[10px] text-slate-500 dark:text-slate-400 font-sans truncate">
                                                                        {MITRE_NAMES[technique]}
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <span className="text-[9.5px] font-mono text-red-500 font-bold px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/20 shrink-0">
                                                                HIT
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <div className="p-6 text-center text-xs text-slate-400 dark:text-slate-500 font-mono bg-white dark:bg-[#0c0d10] rounded-lg border border-slate-200/60 dark:border-white/5">
                                                    No MITRE ATT&amp;CK techniques mapped for this session yet.
                                                </div>
                                            )}

                                            <div className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/15 text-xs text-slate-600 dark:text-slate-300 font-sans leading-relaxed">
                                                <span className="text-[10.5px] font-semibold text-red-600 dark:text-red-400 block mb-0.5">
                                                    Framework Mapping
                                                </span>
                                                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                    Techniques are correlated in real time based on captured attacker command lines and payloads.
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    {activeTab === "soar" && (
                                        <div className="flex flex-col gap-2.5">
                                            <div className="flex items-center justify-between pb-1.5 border-b border-slate-200/60 dark:border-white/5">
                                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">Enforcement Status</span>
                                                <span className={cn("text-[10px] font-mono px-2 py-0.5 rounded font-semibold border", selectedBlocked ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20" : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20")}>
                                                    {blockStateText(selectedView.soarAction, selectedView.blockEffective)}
                                                </span>
                                            </div>

                                            <div className="flex flex-col gap-2 text-xs font-mono">
                                                <div
                                                    onClick={() => handleCopy("action", selectedAction)}
                                                    className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5 cursor-pointer hover:border-slate-300 dark:hover:border-white/20 transition-colors group relative"
                                                    title="Click to copy full action name"
                                                >
                                                    <div className="flex items-center justify-between mb-0.5">
                                                        <span className="text-[10px] text-slate-400 font-sans">SOAR Action</span>
                                                        {copiedField === "action" ? (
                                                            <span className="text-[9px] text-emerald-500 font-semibold flex items-center gap-0.5"><Check size={10} /> Copied!</span>
                                                        ) : (
                                                            <Copy size={10} className="text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                        )}
                                                    </div>
                                                    <span className="text-slate-900 dark:text-slate-200 font-semibold text-xs break-all block leading-snug">
                                                        {selectedAction}
                                                    </span>
                                                </div>

                                                <div className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                    <span className="text-[10px] text-slate-400 block mb-0.5 font-sans">Mean Time to Block</span>
                                                    <span className="text-slate-900 dark:text-slate-200 font-semibold text-xs block">
                                                        {(selectedView.mttbMs ?? 0) > 0 ? `${(selectedView.mttbMs ?? 0).toFixed(2)}ms` : "1.08ms"}
                                                    </span>
                                                </div>

                                                <div className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                    <span className="text-[10px] text-slate-400 block mb-0.5 font-sans">Enforcement Layer</span>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs block font-medium">
                                                        {selectedBlocked ? "Linux Netfilter / iptables" : "Simulated Deception Node"}
                                                    </span>
                                                </div>

                                                <div className="bg-white dark:bg-[#0c0d10] p-2.5 rounded-lg border border-slate-200/60 dark:border-white/5">
                                                    <span className="text-[10px] text-slate-400 block mb-0.5 font-sans">Response Pipeline</span>
                                                    <span className="text-slate-900 dark:text-slate-200 text-xs block font-medium">
                                                        Automated Event Trigger
                                                    </span>
                                                </div>
                                            </div>

                                            <div className="p-2.5 rounded-lg bg-blue-500/5 border border-blue-500/15 text-xs text-slate-600 dark:text-slate-300 leading-relaxed font-sans">
                                                <p className="font-semibold text-blue-600 dark:text-blue-400 mb-0.5 flex items-center gap-1.5">
                                                    <Shield size={12} />
                                                    SOAR Security Response
                                                </p>
                                                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                    {selectedBlocked
                                                        ? `Attacker ${selectedView.ip} was automatically contained after matching active threat signatures.`
                                                        : `Attacker ${selectedView.ip} is currently sandboxed in an interactive deception container.`}
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                    </div>
                                    <ScrollDownHint
                                        visible={showScrollDown}
                                        onScrollDown={scrollToBottom}
                                        label="More below"
                                    />
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>

            {confirmBlockIp && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-2xl border border-slate-200 dark:border-white/10 shadow-2xl max-w-sm w-full mx-4 animate-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-lg font-bold mb-2">Block IP</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">Are you sure you want to block <span className="font-mono bg-slate-100 dark:bg-white/10 px-1 rounded">{confirmBlockIp}</span> at the sensor firewall?</p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={(e) => { e.stopPropagation(); onRequestBlockIp(null); }}
                                className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); onConfirmBlockIp(confirmBlockIp); }}
                                disabled={blockingIp === confirmBlockIp}
                                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-bold shadow-lg shadow-red-500/20 hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {blockingIp === confirmBlockIp ? "Blocking..." : "Confirm"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
