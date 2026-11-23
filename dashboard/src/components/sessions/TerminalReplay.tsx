"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Copy, Terminal as TerminalIcon, Check, Maximize2, Minimize2 } from "lucide-react";
import { useAgentCommand } from "@/lib/AgentContext";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import { cn } from "@/lib/utils";

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

export default function TerminalReplay({ lines, replay, mode = "both", onModeChange, isSeamless = false }: TerminalReplayProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const stickToBottomRef = useRef(true);
    const [copied, setCopied] = useState(false);
    const [isFullScreen, setIsFullScreen] = useState(false);
    const [canScrollDown, setCanScrollDown] = useState(false);

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

    useEffect(() => {
        if (!scrollRef.current) return;
        if (stickToBottomRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [visibleEntries]);

    function handleScroll() {
        if (!scrollRef.current) return;
        const el = scrollRef.current;
        const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
        stickToBottomRef.current = distanceFromBottom < 24;
        setCanScrollDown(distanceFromBottom > 32);
    }

    const scrollToBottom = useCallback(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
            stickToBottomRef.current = true;
            setCanScrollDown(false);
        }
    }, []);

    function handleCopy() {
        const text = visibleEntries.map((entry) => formatReplayLine(entry)).join("\n");
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    return (
        <div className={isFullScreen ? "fixed inset-4 z-[120] bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/10 overflow-hidden font-mono text-xs shadow-2xl flex flex-col" : isSeamless ? "w-full overflow-hidden font-mono text-xs flex flex-col h-full min-h-0 bg-transparent" : "w-full bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 overflow-hidden font-mono text-xs shadow-sm flex flex-col h-full min-h-[280px]"}>
            {isFullScreen && <div className="fixed inset-0 z-[-1] bg-black/60 backdrop-blur-sm" onClick={() => setIsFullScreen(false)} />}
            <div className="bg-slate-50/80 dark:bg-white/[0.02] px-3.5 py-2 flex items-center justify-between gap-2 border-b border-slate-200 dark:border-white/5 shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                    <TerminalIcon size={13} className="text-blue-500 shrink-0" />
                    <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                        Terminal Output
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">
                        &bull; {visibleEntries.length} {visibleEntries.length === 1 ? "line" : "lines"}
                    </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <div className="inline-flex items-center p-0.5 rounded-md bg-slate-200/60 dark:bg-white/[0.06] text-[10.5px] font-sans">
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
                    <div className="w-[1px] h-3.5 bg-slate-200 dark:border-white/10" />
                    <button
                        onClick={handleCopy}
                        className="inline-flex h-6 w-6 items-center justify-center text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors rounded hover:bg-slate-200/70 dark:hover:bg-white/10"
                        title="Copy replay"
                        aria-label="Copy replay"
                    >
                        {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                    </button>
                    <button
                        onClick={() => setIsFullScreen(!isFullScreen)}
                        className="inline-flex h-6 w-6 items-center justify-center text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 transition-colors rounded hover:bg-slate-200/70 dark:hover:bg-white/10"
                        title={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
                        aria-label={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
                    >
                        {isFullScreen ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                    </button>
                </div>
            </div>

            <div className="relative flex-1 min-h-0">
                <div
                    ref={scrollRef}
                    onScroll={handleScroll}
                    className="h-full overflow-y-auto px-3 py-3 text-[11.5px] text-slate-800 dark:text-emerald-400 terminal-scrollbar"
                >
                    {visibleEntries.length === 0 && (
                        <div className="text-slate-400 dark:text-slate-500 text-xs px-2 py-1">
                            No command replay stored for this session yet.
                        </div>
                    )}
                    {visibleEntries.map((entry, i) => {
                        const infoType = getInfoType(entry.text);
                        return (
                            <div key={`${entry.role}-${i}-${entry.timestamp ?? "na"}`} className="group flex items-start gap-2.5 mb-1 leading-relaxed font-mono">
                                <span className="select-none text-[10.5px] font-mono text-slate-400/60 dark:text-slate-600 w-6 text-right shrink-0 pt-[1px] tabular-nums">
                                    {i + 1}
                                </span>
                                <div className="flex-1 min-w-0 break-words">
                                    {infoType ? (
                                        <>
                                            <span className={`select-none mr-1.5 font-semibold text-[9.5px] uppercase px-1 py-0.5 rounded border ${infoTypeClass(infoType)}`}>
                                                {infoType}
                                            </span>
                                            <span className="whitespace-pre-wrap">{entry.text.replace(/^\[[A-Z]+\]\s*/i, "")}</span>
                                        </>
                                    ) : (
                                        <>
                                            <span className={`select-none mr-1.5 font-bold ${entry.role === "honeypot" ? "text-amber-500 dark:text-amber-400" : "text-blue-600 dark:text-blue-400"}`}>
                                                {entry.role === "honeypot" ? "#" : "$"}
                                            </span>
                                            <span className="whitespace-pre-wrap">{entry.text}</span>
                                        </>
                                    )}
                                    {entry.timestamp && <span className="ml-2 text-[10px] text-slate-400 dark:text-slate-500">{entry.timestamp}</span>}
                                </div>
                            </div>
                        );
                    })}
                    <div className="flex items-center gap-2.5 ml-8 mt-1">
                        <div className="animate-pulse inline-block w-1.5 h-3.5 bg-slate-400 dark:bg-emerald-400 align-middle" />
                    </div>
                </div>
                <ScrollDownHint visible={canScrollDown} onScrollDown={scrollToBottom} />
            </div>
        </div>
    );
}
