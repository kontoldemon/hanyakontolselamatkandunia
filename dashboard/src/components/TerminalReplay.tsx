"use client";

import { useEffect, useMemo, useRef } from "react";
import { Copy, Terminal as TerminalIcon } from "lucide-react";

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
    const entries = useMemo(() => {
        if (replay && replay.length > 0) {
            return replay.filter((item) => item.role === "attacker" || item.role === "honeypot");
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

    return (
        <div className="w-full bg-[#0a0a0a] rounded-lg border border-slate-800 overflow-hidden font-mono text-sm shadow-2xl">
            {/* Terminal Header */}
            <div className="bg-[#1a1a1a] px-4 py-2 flex items-center justify-between border-b border-slate-800">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                        <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                        <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                    </div>
                    <span className="ml-3 text-slate-400 text-xs flex items-center gap-2">
                        <TerminalIcon size={12} />
                        root@cloudsentinel:~
                    </span>
                </div>
                <button className="text-slate-500 hover:text-slate-300 transition-colors">
                    <Copy size={14} />
                </button>
            </div>
            <div className="bg-[#151515] px-4 py-2 border-b border-slate-800 flex items-center justify-between gap-3">
                <span className="text-[11px] uppercase tracking-wide text-slate-400">Replay Filter</span>
                <select
                    value={mode}
                    onChange={(event) => onModeChange?.(event.target.value as "attacker" | "both")}
                    className="rounded-md border border-slate-700 bg-[#0f0f0f] text-slate-200 text-xs px-2 py-1"
                >
                    <option value="attacker">Attacker Only</option>
                    <option value="both">Attacker + Honeypot Response</option>
                </select>
            </div>

            {/* Terminal Content */}
            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="h-[400px] overflow-y-auto p-4 text-green-400 terminal-scrollbar"
            >
                {visibleEntries.length === 0 && (
                    <div className="text-slate-500">
                        No command replay stored for this session yet.
                    </div>
                )}
                {visibleEntries.map((entry, i) => (
                    <div key={`${entry.role}-${i}-${entry.timestamp ?? "na"}`} className="mb-1 leading-relaxed break-words">
                        <span className={`select-none mr-2 ${entry.role === "honeypot" ? "text-amber-400" : "text-blue-400"}`}>
                            {entry.role === "honeypot" ? "#" : "$"}
                        </span>
                        <span className="typing-effect whitespace-pre-wrap">{entry.text}</span>
                        {entry.timestamp && <span className="ml-2 text-[10px] text-slate-500">{entry.timestamp}</span>}
                    </div>
                ))}
                <div className="animate-pulse inline-block w-2 h-4 bg-green-400 align-middle ml-1"></div>
            </div>
        </div>
    );
}
