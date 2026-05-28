"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Copy, Terminal as TerminalIcon, Check, Maximize2, Minimize2 } from "lucide-react";
import { useAgentCommand } from "@/lib/AgentContext";

import CustomDropdown from "@/components/CustomDropdown";

type ReplayEntry = {
    role: "attacker" | "honeypot";
    text: string;
    timestamp?: string;
};

interface TerminalReplayProps {
    lines: string[];
    replay?: ReplayEntry[];
    mode?: "attacker" | "both";
    onModeChange?: (mode: "attacker" | "both") => void;
}

export default function TerminalReplay({ lines, replay, mode = "both", onModeChange }: TerminalReplayProps) {
    const scrollRef = useRef<HTMLDivElement>(null);
    const stickToBottomRef = useRef(true);
    const [copied, setCopied] = useState(false);
    const [isFullScreen, setIsFullScreen] = useState(false);

    // ── Agent command handlers ──
    useAgentCommand("replay.fullscreen", useCallback(() => setIsFullScreen((p) => !p), []));
    useAgentCommand("replay.mode", useCallback((v: string) => onModeChange?.(v as "attacker" | "both"), [onModeChange]));
    useAgentCommand("replay.copy", useCallback(() => {
        const text = (replay && replay.length > 0 ? replay : lines.map((l) => ({ role: "attacker" as const, text: l }))).map((e) => `${e.role === "honeypot" ? "#" : "$"} ${e.text}`).join("\n");
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
        if (!scrollRef.current || !stickToBottomRef.current) {
            return;
        }
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [visibleEntries]);

    function handleScroll() {
        if (!scrollRef.current) {
            return;
        }
        const el = scrollRef.current;
        const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
        stickToBottomRef.current = distanceFromBottom < 24;
    }

    function handleCopy() {
        const text = visibleEntries.map(e => `${e.role === 'honeypot' ? '#' : '$'} ${e.text}`).join('\n');
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }

    return (
        <div className={isFullScreen ? "fixed inset-4 z-[120] bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 overflow-hidden font-mono text-sm shadow-2xl flex flex-col" : "w-full bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 overflow-hidden font-mono text-sm shadow-sm flex flex-col h-full min-h-[300px]"}>
            {isFullScreen && <div className="fixed inset-0 z-[-1] bg-black/60 backdrop-blur-sm" onClick={() => setIsFullScreen(false)} />}
            {/* Terminal Header */}
            <div className="bg-slate-100 dark:bg-white/[0.02] px-4 py-2.5 flex items-center justify-between border-b border-slate-200 dark:border-white/5 shrink-0">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-400 dark:bg-red-500/80"></div>
                        <div className="w-3 h-3 rounded-full bg-amber-400 dark:bg-yellow-500/80"></div>
                        <div className="w-3 h-3 rounded-full bg-emerald-400 dark:bg-green-500/80"></div>
                    </div>
                    <span className="ml-3 text-slate-500 dark:text-slate-400 text-xs flex items-center gap-2">
                        <TerminalIcon size={12} />
                        root@cloudsentinel:~
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => setIsFullScreen(!isFullScreen)} className="p-1 text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded hover:bg-slate-200 dark:hover:bg-white/10" title={isFullScreen ? "Exit Fullscreen" : "Fullscreen"}>
                        {isFullScreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
                    </button>
                    <button onClick={handleCopy} className="p-1 text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors rounded hover:bg-slate-200 dark:hover:bg-white/10" title="Copy to clipboard">
                        {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                    </button>
                </div>
            </div>
            <div className="bg-slate-50 dark:bg-[#0f0f0f] px-4 py-2 border-b border-slate-200 dark:border-white/5 flex items-center justify-between gap-3 shrink-0">
                <span className="text-[10px] uppercase tracking-wide text-slate-500 font-bold">Replay Filter</span>
                <CustomDropdown
                    options={[
                        { label: "Attacker Only", value: "attacker" },
                        { label: "Both", value: "both" }
                    ]}
                    value={mode}
                    onChange={(val) => onModeChange?.(val as "attacker" | "both")}
                    className="w-32"
                />
            </div>

            {/* Terminal Content */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto p-4 text-slate-800 dark:text-green-400 terminal-scrollbar"
            >
                {visibleEntries.length === 0 && (
                    <div className="text-slate-400 dark:text-slate-500">
                        No command replay stored for this session yet.
                    </div>
                )}
                {visibleEntries.map((entry, i) => (
                    <div key={`${entry.role}-${i}-${entry.timestamp ?? "na"}`} className="mb-1.5 leading-relaxed break-words">
                        <span className={`select-none mr-2 font-bold ${entry.role === "honeypot" ? "text-amber-500 dark:text-amber-400" : "text-blue-600 dark:text-blue-400"}`}>
                            {entry.role === "honeypot" ? "#" : "$"}
                        </span>
                        <span className="typing-effect whitespace-pre-wrap">{entry.text}</span>
                        {entry.timestamp && <span className="ml-3 text-[10px] text-slate-400 dark:text-slate-500">{entry.timestamp}</span>}
                    </div>
                ))}
                <div className="animate-pulse inline-block w-2 h-4 bg-slate-400 dark:bg-green-400 align-middle ml-1"></div>
            </div>
        </div>
    );
}
