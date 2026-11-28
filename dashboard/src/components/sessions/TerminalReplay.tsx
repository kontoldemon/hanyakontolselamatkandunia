"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Copy, Terminal as TerminalIcon, Check, Maximize2, Minimize2, Search, X } from "lucide-react";
import { useAgentCommand } from "@/lib/AgentContext";
import { cn } from "@/lib/utils";
import ScrollDownHint from "@/components/ui/ScrollDownHint";

type ReplayEntry = {
    role: "attacker" | "honeypot";
    text: string;
    timestamp?: string;
};

type ReplayInfoType = "OPEN" | "CLOSE" | "AUTH" | "VERSION";

interface TerminalReplayProps {
    lines: string[];
    replay?: ReplayEntry[];
    mode?: "attacker" | "both";
    onModeChange?: (mode: "attacker" | "both") => void;
    isSeamless?: boolean;
}

const getInfoType = (text: string): ReplayInfoType | null => {
    const normalized = (text || "").trim().toLowerCase();
    if (normalized.startsWith("[open]")) return "OPEN";
    if (normalized.startsWith("[close]")) return "CLOSE";
    if (normalized.startsWith("[auth]")) return "AUTH";
    if (normalized.startsWith("[version]")) return "VERSION";
    return null;
};

const formatReplayLine = (entry: ReplayEntry) => {
    const infoType = getInfoType(entry.text);
    if (infoType) {
        return `! ${entry.text}`;
    }
    return `${entry.role === "honeypot" ? "#" : "$"} ${entry.text}`;
};

const infoTypeClass = (infoType: ReplayInfoType) => {
    if (infoType === "OPEN") return "bg-cyan-500/15 text-cyan-700 border-cyan-500/30 dark:bg-cyan-500/20 dark:text-cyan-300 dark:border-cyan-400/30";
    if (infoType === "CLOSE") return "bg-slate-500/10 text-slate-700 border-slate-400/30 dark:bg-slate-400/10 dark:text-slate-300 dark:border-slate-300/20";
    if (infoType === "AUTH") return "bg-amber-500/15 text-amber-700 border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-400/30";
    return "bg-violet-500/15 text-violet-700 border-violet-500/30 dark:bg-violet-500/20 dark:text-violet-300 dark:border-violet-400/30";
};

function parseReplayStamp(stamp: string): number | null {
    const match = /^(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$/.exec(stamp.trim());
    if (!match) return null;
    const fraction = Number((match[4] ?? "").padEnd(3, "0"));
    return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]) + fraction / 1000;
}

function formatElapsed(seconds: number): string {
    const total = Math.max(0, Math.round(seconds));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    return hours > 0
        ? `+${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`
        : `+${minutes}:${String(secs).padStart(2, "0")}`;
}

export default function TerminalReplay({ lines, replay, mode = "both", onModeChange, isSeamless = false }: TerminalReplayProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const stickToBottomRef = useRef(true);
    const [copied, setCopied] = useState(false);
    const [isFullScreen, setIsFullScreen] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [showScrollBottom, setShowScrollBottom] = useState(false);

    useAgentCommand("replay.fullscreen", useCallback(() => setIsFullScreen((p) => !p), []));
    useAgentCommand("replay.mode", useCallback((v: string) => onModeChange?.(v as "attacker" | "both"), [onModeChange]));
    useAgentCommand("replay.copy", useCallback(() => {
        const text = (replay && replay.length > 0 ? replay : lines.map((l) => ({ role: "attacker" as const, text: l }))).map((e) => formatReplayLine(e)).join("\n");
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [replay, lines]));

    const entries = useMemo(() => {
        if (replay && replay.length > 0) {
            const valid = replay.filter((item) => item.role === "attacker" || item.role === "honeypot");
            return valid.sort((a, b) => {
                if (!a.timestamp || !b.timestamp) return 0;
                if (a.timestamp === b.timestamp) {
                    return a.role === "attacker" ? -1 : 1;
                }
                return a.timestamp.localeCompare(b.timestamp);
            });
        }
        return lines.map((line) => ({ role: "attacker" as const, text: line, timestamp: undefined }));
    }, [lines, replay]);

    const visibleEntries = useMemo(
        () => (mode === "attacker" ? entries.filter((item) => item.role === "attacker") : entries),
        [entries, mode],
    );

    const filteredEntries = useMemo(() => {
        if (!searchQuery.trim()) return visibleEntries;
        const q = searchQuery.toLowerCase();
        return visibleEntries.filter((item) =>
            item.text.toLowerCase().includes(q) || (item.timestamp && item.timestamp.toLowerCase().includes(q))
        );
    }, [visibleEntries, searchQuery]);

    const baseStampSeconds = useMemo(() => {
        for (const entry of entries) {
            if (!entry.timestamp) continue;
            const seconds = parseReplayStamp(entry.timestamp);
            if (seconds !== null) return seconds;
        }
        return null;
    }, [entries]);

    const timeLabels = useMemo(() => {
        const labels = filteredEntries.map(() => "");
        if (baseStampSeconds === null) {
            filteredEntries.forEach((entry, index) => {
                labels[index] = entry.timestamp ? entry.timestamp.replace(/\.\d+$/, "") : "";
            });
            return labels;
        }
        let lastShown = -1;
        filteredEntries.forEach((entry, index) => {
            if (!entry.timestamp) return;
            const seconds = parseReplayStamp(entry.timestamp);
            if (seconds === null) {
                labels[index] = entry.timestamp.replace(/\.\d+$/, "");
                return;
            }
            let offset = seconds - baseStampSeconds;
            if (offset < 0) offset += 24 * 3600;
            if (lastShown < 0 || offset - lastShown >= 1) {
                labels[index] = formatElapsed(offset);
                lastShown = offset;
            }
        });
        return labels;
    }, [filteredEntries, baseStampSeconds]);

    const showTimeColumn = filteredEntries.some((entry) => entry.timestamp);

    useEffect(() => {
        if (!scrollRef.current) return;
        if (stickToBottomRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [filteredEntries]);

    function handleScroll() {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
        stickToBottomRef.current = distanceFromBottom < 30;
        setShowScrollBottom(distanceFromBottom > 70);
    }

    function scrollToBottom() {
        if (!scrollRef.current) return;
        scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
        setShowScrollBottom(false);
    }

    function handleCopy() {
        const text = filteredEntries.map((entry) => formatReplayLine(entry)).join("\n");
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    return (
        <>
            {isFullScreen && (
                <div
                    className="fixed inset-0 z-[190] bg-black/50 backdrop-blur-xs transition-opacity duration-200"
                    onClick={() => setIsFullScreen(false)}
                />
            )}
            <div
                className={
                    isFullScreen
                        ? "fixed inset-3 md:inset-6 z-[200] bg-white dark:bg-[#0a0a0a] rounded-2xl border border-slate-200/90 dark:border-white/10 overflow-hidden font-mono text-xs shadow-2xl flex flex-col transition-all"
                        : isSeamless
                            ? "w-full overflow-hidden font-mono text-xs flex flex-col h-full min-h-0 bg-transparent"
                            : "w-full bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 overflow-hidden font-mono text-xs shadow-sm flex flex-col h-full min-h-[280px]"
                }
            >
                <div className="bg-slate-50/80 dark:bg-white/[0.02] px-3.5 py-2 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 dark:border-white/5 shrink-0">
                    <div className="flex items-center gap-1.5 min-w-0">
                        <TerminalIcon size={13} className="text-blue-500 shrink-0" />
                        <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                            Terminal Output
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 shrink-0 hidden sm:inline">
                            &bull; {searchQuery.trim() ? `${filteredEntries.length}/${visibleEntries.length}` : visibleEntries.length} {visibleEntries.length === 1 ? "line" : "lines"}
                        </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                        {/* Search filter input */}
                        <div className="relative flex items-center">
                            <Search size={11} className="text-slate-400 dark:text-slate-500 absolute left-2 pointer-events-none" />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="Filter..."
                                className="w-28 sm:w-24 focus:w-36 sm:focus:w-32 h-9 sm:h-6.5 pl-5 pr-5 py-0.5 text-[11px] font-sans rounded-md bg-slate-200/50 dark:bg-white/[0.06] border border-slate-300/40 dark:border-white/10 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none transition-all focus:border-blue-500/50"
                            />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-0 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                                title="Clear filter"
                            >
                                <X size={10} />
                            </button>
                        )}
                    </div>

                    <div className="inline-flex h-6.5 items-center p-0.5 rounded-md bg-slate-200/60 dark:bg-white/[0.06] text-[10.5px] font-sans">
                        <button
                            type="button"
                            onClick={() => onModeChange?.("both")}
                            className={cn(
                                "px-2 py-0.5 rounded transition-all",
                                mode === "both"
                                    ? "bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-xs font-semibold"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 font-medium"
                            )}
                        >
                            All
                        </button>
                        <button
                            type="button"
                            onClick={() => onModeChange?.("attacker")}
                            className={cn(
                                "px-2 py-0.5 rounded transition-all",
                                mode === "attacker"
                                    ? "bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-xs font-semibold"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 font-medium"
                            )}
                        >
                            Attacker
                        </button>
                    </div>

                    <div className="w-[1px] h-3.5 bg-slate-300 dark:bg-white/10" />

                    <div className="flex items-center gap-0.5">
                        <button
                            onClick={handleCopy}
                            className="inline-flex h-9 w-9 items-center justify-center text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors rounded hover:bg-slate-200/70 dark:hover:bg-white/10 sm:h-6.5 sm:w-6.5"
                            title="Copy replay"
                            aria-label="Copy replay"
                        >
                            {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                        </button>
                        <button
                            onClick={() => setIsFullScreen(!isFullScreen)}
                            className="inline-flex h-9 w-9 items-center justify-center text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors rounded hover:bg-slate-200/70 dark:hover:bg-white/10 sm:h-6.5 sm:w-6.5"
                            title={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
                            aria-label={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
                        >
                            {isFullScreen ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                        </button>
                    </div>
                </div>
            </div>

            <div className="relative flex-1 min-h-0 bg-white dark:bg-[#0a0a0a]">
                <div
                    ref={scrollRef}
                    onScroll={handleScroll}
                    className="h-full overflow-y-auto px-3 py-3 text-[11.5px] text-slate-800 dark:text-slate-200 terminal-scrollbar bg-white dark:bg-[#0a0a0a]"
                >
                    {filteredEntries.length === 0 && (
                        <div className="text-slate-400 dark:text-slate-500 text-xs px-2 py-1">
                            {searchQuery.trim()
                                ? `No commands matching "${searchQuery}".`
                                : "No command replay stored for this session yet."}
                        </div>
                    )}
                    {filteredEntries.map((entry, i) => {
                        const infoType = getInfoType(entry.text);
                        const stampTitle = entry.timestamp
                            ? `${timeLabels[i] ? `${timeLabels[i]} from replay start | ` : ""}${entry.timestamp} (sensor time)`
                            : undefined;
                        return (
                            <div key={`${entry.role}-${i}-${entry.timestamp ?? "na"}`} className="group flex items-start gap-2 mb-1 leading-relaxed font-mono hover:bg-slate-100/60 dark:hover:bg-white/[0.03] -mx-1 px-1 py-0.5 rounded transition-colors">
                                <span className="select-none text-[10.5px] font-mono text-slate-400/60 dark:text-slate-600 w-7 text-right shrink-0 pt-[1px] tabular-nums">
                                    {i + 1}
                                </span>
                                <div className="flex-1 min-w-0 flex items-start justify-between gap-3">
                                    <div className="font-mono break-all whitespace-pre-wrap flex-1 min-w-0">
                                        {infoType ? (
                                            <>
                                                <span className={`select-none mr-1.5 font-semibold text-[9.5px] uppercase px-1 py-0.5 rounded border ${infoTypeClass(infoType)} inline-block shrink-0`}>
                                                    {infoType}
                                                </span>
                                                <span className={
                                                    infoType === "AUTH"
                                                        ? "text-amber-700 dark:text-amber-300 font-medium"
                                                        : infoType === "VERSION"
                                                            ? "text-violet-700 dark:text-violet-300"
                                                            : infoType === "OPEN"
                                                                ? "text-cyan-700 dark:text-cyan-300"
                                                                : "text-slate-600 dark:text-slate-400"
                                                }>
                                                    {entry.text.replace(/^\[[A-Z]+\]\s*/i, "")}
                                                </span>
                                            </>
                                        ) : (
                                            <>
                                                <span className={`select-none mr-1.5 font-bold ${entry.role === "honeypot" ? "text-amber-500 dark:text-amber-400" : "text-sky-600 dark:text-sky-400"} shrink-0`}>
                                                    {entry.role === "honeypot" ? "#" : "$"}
                                                </span>
                                                <span className={
                                                    entry.role === "attacker"
                                                        ? "text-slate-900 dark:text-slate-100 font-semibold"
                                                        : "text-slate-600 dark:text-slate-300"
                                                }>
                                                    {entry.text}
                                                </span>
                                            </>
                                        )}
                                    </div>
                                    {showTimeColumn && (
                                        <span
                                            className="select-none text-[9.5px] font-mono text-slate-400/80 dark:text-slate-500 shrink-0 tabular-nums ml-auto pt-[1px] min-w-[48px] text-right"
                                            title={stampTitle}
                                        >
                                            {timeLabels[i]}
                                        </span>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                    <div className="flex items-center gap-2.5 ml-8 mt-1">
                        <div className="animate-pulse inline-block w-1.5 h-3.5 bg-slate-400 dark:bg-emerald-400 align-middle" />
                    </div>
                </div>

                {/* More below / Jump to latest command button */}
                <ScrollDownHint
                    visible={showScrollBottom}
                    onScrollDown={scrollToBottom}
                    label="Latest commands"
                    className="pb-5"
                />
            </div>
        </div>
        </>
    );
}
