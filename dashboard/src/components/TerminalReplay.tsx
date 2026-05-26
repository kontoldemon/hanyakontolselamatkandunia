"use client";

import { useEffect, useRef } from "react";
import { Copy, Terminal as TerminalIcon } from "lucide-react";

interface TerminalReplayProps {
    lines: string[];
}

export default function TerminalReplay({ lines }: TerminalReplayProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [lines]);

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

            {/* Terminal Content */}
            <div ref={scrollRef} className="h-[400px] overflow-y-auto p-4 text-green-400 terminal-scrollbar">
                {lines.length === 0 && (
                    <div className="text-slate-500">
                        No command replay stored for this session yet.
                    </div>
                )}
                {lines.map((line, i) => (
                    <div key={i} className="mb-1 leading-relaxed break-words">
                        <span className="text-blue-400 select-none mr-2">$</span>
                        <span className="typing-effect">{line}</span>
                    </div>
                ))}
                <div className="animate-pulse inline-block w-2 h-4 bg-green-400 align-middle ml-1"></div>
            </div>
        </div>
    );
}
