"use client";

import TerminalReplay from "@/components/TerminalReplay";
import { Terminal, Clock, Activity, ArrowRight, ShieldAlert, ArrowLeft, Shield, Cpu, Search, Bot, Loader2, Ban } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useCapturedSessions } from "@/lib/liveEvents";

import CustomDropdown from "@/components/CustomDropdown";

function HighlightText({ text, highlight }: { text: string; highlight: string }) {
    if (!highlight.trim() || !text) {
        return <>{text}</>;
    }
    const escaped = highlight.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "gi");
    const parts = text.split(regex);
    return (
        <>
            {parts.map((part, i) =>
                i % 2 === 1 ? (
                    <span key={i} className="bg-yellow-200 dark:bg-yellow-900/50 text-slate-900 dark:text-yellow-200 rounded-sm px-0.5 font-bold">
                        {part}
                    </span>
                ) : (
                    <span key={i}>{part}</span>
                )
            )}
        </>
    );
}

function formatSoarAction(action?: string) {
    const normalized = (action ?? "none").trim().toLowerCase();
    if (!normalized || normalized === "none") {
        return "none";
    }
    return normalized;
}

function isBlockEffective(action?: string, reported?: boolean) {
    if (reported) {
        return true;
    }
    const normalized = formatSoarAction(action);
    return normalized === "iptables_block" || normalized === "already_blocked";
}

function blockStateText(action?: string, effective?: boolean) {
    const normalized = formatSoarAction(action);
    if (normalized === "already_blocked") {
        return "Existing firewall rule";
    }
    if (normalized === "iptables_block") {
        return "New firewall block";
    }
    if (normalized === "event_published") {
        return "Block event published";
    }
    if (isBlockEffective(action, effective)) {
        return "Blocked";
    }
    if (normalized === "dry_run_block") {
        return "Dry run only";
    }
    return "No block applied";
}

// Removed export const dynamic = 'force-static' to let Next.js auto-detect

export default function SessionsPage() {
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [lastSelectedIp, setLastSelectedIp] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [filterStatus, setFilterStatus] = useState<"all" | "active">("all");
    const [blockingIp, setBlockingIp] = useState<string | null>(null);
    const [replayMode, setReplayMode] = useState<"attacker" | "both">("both");
    const [nowMs, setNowMs] = useState(() => Date.now());
    const sessions = useCapturedSessions();
    const [focusIp, setFocusIp] = useState("");
    const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

    const exactMatch = selectedSessionId ? sessions.find(s => s.id === selectedSessionId) : null;
    const selectedSession = exactMatch || (lastSelectedIp ? sessions.find(s => s.ip === lastSelectedIp) : null);
    
    // Auto-update selected ID if we fell back to IP match
    useEffect(() => {
        if (!exactMatch && selectedSession && selectedSessionId !== selectedSession.id) {
            setSelectedSessionId(selectedSession.id);
        }
    }, [exactMatch, selectedSession, selectedSessionId]);

    const selectedAction = formatSoarAction(selectedSession?.soarAction);
    const selectedBlocked = isBlockEffective(selectedSession?.soarAction, selectedSession?.blockEffective);

    useEffect(() => {
        setReplayMode("both");
    }, [selectedSessionId]);

    useEffect(() => {
        const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
        return () => window.clearInterval(timer);
    }, []);

    function formatDurationLive(session: { duration: string; status: string; startedAtEpochMs?: number }) {
        if ((session.status || "").toLowerCase() !== "active" || !session.startedAtEpochMs) {
            return session.duration;
        }
        const elapsed = Math.max(0, Math.floor((nowMs - session.startedAtEpochMs) / 1000));
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        return `${minutes}m ${seconds}s`;
    }

    const filteredSessions = useMemo(() => sessions.filter(session => {
        if (filterStatus === "active" && (session.status || "").toLowerCase() !== "active") {
            return false;
        }
        const query = searchQuery.toLowerCase();
        return session.ip.toLowerCase().includes(query) ||
            session.country.toLowerCase().includes(query) ||
            (session.countryName && session.countryName.toLowerCase().includes(query)) ||
            (session.fingerprint && session.fingerprint.toLowerCase().includes(query)) ||
            (session.client && session.client.toLowerCase().includes(query));
    }), [sessions, searchQuery, filterStatus]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const params = new URLSearchParams(window.location.search);
        const value = params.get("focusIp")?.trim() ?? "";
        setFocusIp(value);
    }, []);

    useEffect(() => {
        if (!focusIp) {
            return;
        }
        setSearchQuery(focusIp);
    }, [focusIp]);

    useEffect(() => {
        if (!focusIp || filteredSessions.length === 0) {
            return;
        }
        const target = filteredSessions.find((session) => session.ip === focusIp);
        if (target && cardRefs.current[target.id]) {
            cardRefs.current[target.id]?.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }, [focusIp, filteredSessions]);

    async function blockIp(ip: string) {
        const confirmed = window.confirm(`Block ${ip} at the sensor firewall?`);
        if (!confirmed) {
            return;
        }
        setBlockingIp(ip);
        try {
            const response = await fetch("/api/cloudsentinel/block-ip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip, ttl: 3600, reason: "manual-dashboard" }),
            });
            const data = await response.json();
            if (!data.ok) {
                window.alert(data.error ?? "Block failed");
            }
        } catch {
            window.alert("Block request failed");
        } finally {
            setBlockingIp(null);
        }
    }

    return (
        <div className="h-full flex flex-col md:flex-row gap-6">
            {/* Master View (List) */}
            <div className={cn("flex flex-col h-full md:w-[380px] shrink-0 border border-slate-200 dark:border-white/5 rounded-xl bg-white dark:bg-[#0a0a0a] shadow-sm overflow-hidden", selectedSessionId ? "hidden md:flex" : "flex")}>
                <div className="p-4 border-b border-slate-200 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02]">
                    <div className="flex justify-between items-center mb-3">
                        <h2 className="text-lg font-bold">Sessions</h2>
                        <CustomDropdown 
                            options={[
                                { label: "All Logs", value: "all" },
                                { label: "Active Only", value: "active" }
                            ]}
                            value={filterStatus}
                            onChange={(val) => setFilterStatus(val as "all" | "active")}
                            className="w-28"
                        />
                    </div>
                    <div className="relative">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input 
                            type="text" 
                            placeholder="Search IP, HASSH..." 
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 rounded-lg pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 w-full transition-all shadow-sm"
                        />
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {filteredSessions.length === 0 && (
                        <div className="p-4 text-center text-xs text-slate-500 dark:text-slate-400">
                            No captured sessions.
                        </div>
                    )}
                    {filteredSessions.map((session) => {
                        const isSelected = selectedSessionId === session.id;
                        const isFocused = focusIp && session.ip === focusIp;
                        return (
                        <div
                            key={session.id}
                            ref={(el) => { cardRefs.current[session.id] = el; }}
                            onClick={() => {
                                setSelectedSessionId(session.id);
                                setLastSelectedIp(session.ip);
                            }}
                            className={cn(
                                "cursor-pointer p-3 rounded-lg border transition-all shadow-sm",
                                isSelected ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800" : "bg-white dark:bg-[#0a0a0a] border-slate-100 dark:border-white/5 hover:border-blue-300 dark:hover:border-blue-500/30",
                                isFocused && !isSelected && "ring-1 ring-blue-500",
                            )}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <h3 className="font-bold text-slate-900 dark:text-white font-mono text-sm">
                                    <HighlightText text={session.ip} highlight={searchQuery} />
                                </h3>
                                {(session.status || "").toLowerCase() === "active" && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-600 dark:text-green-400 animate-pulse border border-green-500/20 leading-none">
                                        Live
                                    </span>
                                )}
                            </div>
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                                <span className="flex items-center gap-1 truncate max-w-[120px]">
                                    <HighlightText text={session.countryName || session.country} highlight={searchQuery} />
                                </span>
                                <span className="flex items-center gap-1"><Clock size={10} /> {formatDurationLive(session)}</span>
                                <span className="flex items-center gap-1 font-mono text-[10px] truncate max-w-[100px]"><HighlightText text={session.client || 'Unknown'} highlight={searchQuery} /></span>
                            </div>
                        </div>
                    )})}
                </div>
            </div>

            {/* Detail View */}
            <div className={cn("flex-1 flex flex-col h-full bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/5 rounded-xl shadow-sm overflow-hidden", !selectedSessionId ? "hidden md:flex items-center justify-center" : "flex")}>
                {!selectedSession ? (
                    <div className="text-center text-slate-500 flex flex-col items-center gap-3">
                        <Terminal size={32} className="opacity-20" />
                        <p className="text-sm">Select a session to view details & replay</p>
                    </div>
                ) : (
                    <>
                        <div className="p-4 border-b border-slate-200 dark:border-white/5 flex items-center justify-between shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
                            <div className="flex items-center gap-3">
                                <button onClick={() => setSelectedSessionId(null)} className="md:hidden p-1 -ml-1 hover:bg-slate-100 dark:hover:bg-white/10 rounded">
                                    <ArrowLeft size={16} />
                                </button>
                                <div>
                                    <h2 className="font-bold text-lg font-mono leading-none">{selectedSession.ip}</h2>
                                    <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-2">
                                        <span>ASN: {selectedSession.asn || "N/A"}</span>
                                        <span>•</span>
                                        <span>HASSH: {selectedSession.fingerprint?.slice(0,16) || "N/A"}...</span>
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={() => void blockIp(selectedSession.ip)}
                                disabled={blockingIp === selectedSession.ip}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 text-red-600 dark:text-red-400 rounded-md hover:bg-red-500 hover:text-white disabled:opacity-50 transition-colors text-xs font-semibold"
                            >
                                <Ban size={14} />
                                Block IP
                            </button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-4 md:p-6 grid grid-cols-1 xl:grid-cols-3 gap-6">
                            {/* Main: Terminal Replay */}
                            <div className="xl:col-span-2 flex flex-col">
                                <TerminalReplay
                                    lines={selectedSession.input ?? []}
                                    replay={selectedSession.replay}
                                    mode={replayMode}
                                    onModeChange={setReplayMode}
                                />
                            </div>

                            {/* Sidebar: Intelligence */}
                            <div className="flex flex-col gap-4">
                                <div className="bg-slate-50 dark:bg-white/[0.02] p-4 rounded-xl border border-slate-200 dark:border-white/5 shadow-sm text-sm">
                                    <h3 className="font-semibold mb-3 flex items-center gap-2 text-slate-800 dark:text-slate-200">
                                        <Shield className="text-blue-500" size={16} />
                                        SOAR Action
                                    </h3>
                                    <div className="grid gap-2 text-xs font-mono">
                                        <div className="flex justify-between border-b border-slate-200 dark:border-white/5 pb-2">
                                            <span className="text-slate-500">Action</span>
                                            <span className="text-slate-900 dark:text-slate-300">{selectedAction}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-slate-200 dark:border-white/5 pb-2">
                                            <span className="text-slate-500">Effective</span>
                                            <span className={selectedBlocked ? "text-red-500" : "text-slate-900 dark:text-slate-300"}>{selectedBlocked ? "Yes" : "No"}</span>
                                        </div>
                                        <div className="flex justify-between border-b border-slate-200 dark:border-white/5 pb-2">
                                            <span className="text-slate-500">State</span>
                                            <span className="text-slate-900 dark:text-slate-300">{blockStateText(selectedSession.soarAction, selectedSession.blockEffective)}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">MTTB</span>
                                            <span className="text-slate-900 dark:text-slate-300">{(selectedSession.mttbMs ?? 0) > 0 ? `${(selectedSession.mttbMs ?? 0).toFixed(2)}ms` : "N/A"}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-red-500/5 p-4 rounded-xl border border-red-500/20 shadow-sm text-sm">
                                    <h3 className="font-semibold text-red-600 dark:text-red-400 mb-3 flex items-center gap-2">
                                        <ShieldAlert size={16} />
                                        MITRE ATT&CK
                                    </h3>
                                    {selectedSession.mitreTechniques && selectedSession.mitreTechniques.length > 0 ? (
                                        <ul className="space-y-1.5">
                                            {selectedSession.mitreTechniques.slice(0, 6).map((technique) => (
                                                <li key={technique} className="text-[11px] flex justify-between font-mono bg-red-500/10 px-2 py-1 rounded">
                                                    <span className="text-red-700 dark:text-red-300">{technique}</span>
                                                    <span className="text-red-500">Detected</span>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-xs text-slate-500 dark:text-slate-400">No techniques mapped.</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
