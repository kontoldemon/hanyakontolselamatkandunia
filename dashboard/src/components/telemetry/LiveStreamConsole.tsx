"use client";

import { Check, Copy, Maximize2, Pause, Play, Radio, Terminal, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAgentCommand } from "@/lib/AgentContext";
import type { SocketTelemetrySnapshot, SocketTelemetryEvent } from "@/lib/telemetry/types";
import { cn } from "@/lib/utils";

interface LiveStreamConsoleProps {
    socketTelemetry: SocketTelemetrySnapshot;
}

export default function LiveStreamConsole({ socketTelemetry }: LiveStreamConsoleProps) {
    const [isFullScreen, setIsFullScreen] = useState(false);
    const [isClosingFullScreen, setIsClosingFullScreen] = useState(false);
    const [isPaused, setIsPaused] = useState(false);
    const [filterLevel, setFilterLevel] = useState<"all" | "info" | "warn" | "error">("all");
    const [copiedAll, setCopiedAll] = useState(false);
    const [pausedSnapshot, setPausedSnapshot] = useState<SocketTelemetryEvent[] | null>(null);
    const [clearedAt, setClearedAt] = useState("");
    const inlineTerminalRef = useRef<HTMLDivElement>(null);
    const fullscreenTerminalRef = useRef<HTMLDivElement>(null);

    useAgentCommand("socket.fullscreen", useCallback((value: string) => {
        if (value === "toggle") {
            setIsFullScreen((previous) => !previous);
        } else {
            setIsFullScreen(value === "true" || value === "open");
        }
    }, []));

    const events = isPaused
        ? (pausedSnapshot ?? socketTelemetry.recent)
        : (clearedAt ? socketTelemetry.recent.filter((event) => event.timestamp > clearedAt) : socketTelemetry.recent);

    // Auto-scroll ONLY the terminal container internally without affecting outer page scroll
    useEffect(() => {
        if (isPaused) return;
        if (inlineTerminalRef.current) {
            inlineTerminalRef.current.scrollTop = inlineTerminalRef.current.scrollHeight;
        }
        if (fullscreenTerminalRef.current) {
            fullscreenTerminalRef.current.scrollTop = fullscreenTerminalRef.current.scrollHeight;
        }
    }, [events, isPaused]);

    const closeFullScreen = useCallback(() => {
        if (isClosingFullScreen) return;
        setIsClosingFullScreen(true);
        setTimeout(() => {
            setIsFullScreen(false);
            setIsClosingFullScreen(false);
        }, 180);
    }, [isClosingFullScreen]);

    useEffect(() => {
        if (!isFullScreen) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") closeFullScreen();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [isFullScreen, closeFullScreen]);

    const filteredEvents = events.filter((evt) => {
        if (filterLevel === "all") return true;
        return evt.level === filterLevel;
    });

    const handleCopyLogs = async () => {
        const text = filteredEvents
            .map((e) => `${e.timestamp} [${e.level}] ${e.event}${e.detail ? ` - ${e.detail}` : ""}`)
            .join("\n");
        await navigator.clipboard.writeText(text);
        setCopiedAll(true);
        setTimeout(() => setCopiedAll(false), 1800);
    };

    const handleClearLogs = () => {
        setClearedAt(new Date().toISOString());
        setPausedSnapshot([]);
    };

    const togglePause = () => {
        if (!isPaused) {
            setPausedSnapshot(socketTelemetry.recent);
        } else {
            setPausedSnapshot(null);
        }
        setIsPaused((previous) => !previous);
    };

    const renderLogLine = (evt: SocketTelemetryEvent, index: number) => {
        const isWarn = evt.level === "warn";
        const isError = evt.level === "error";
        const isInfo = evt.level === "info";

        return (
            <div
                key={`${evt.timestamp}-${index}`}
                className={cn(
                    "flex items-start gap-2.5 py-0.5 leading-relaxed font-mono text-[11px] select-text hover:bg-white/[0.03] px-1.5 rounded transition-colors",
                    isWarn && "text-amber-400/90",
                    isError && "text-rose-400 font-semibold",
                    isInfo && "text-slate-300 dark:text-slate-300",
                    !isWarn && !isError && !isInfo && "text-slate-400"
                )}
            >
                <span className="text-slate-600 select-none text-[10px] w-6 text-right shrink-0">
                    {index + 1}
                </span>
                <span className="text-slate-500 shrink-0">{evt.timestamp}</span>
                <span
                    className={cn(
                        "text-[9px] font-bold px-1 rounded uppercase tracking-wider shrink-0",
                        isError && "bg-rose-500/20 text-rose-400",
                        isWarn && "bg-amber-500/20 text-amber-400",
                        isInfo && "bg-blue-500/20 text-blue-400"
                    )}
                >
                    {evt.level}
                </span>
                <span className="break-all">
                    {evt.event}
                    {evt.detail && <span className="text-slate-400 ml-1.5">({evt.detail})</span>}
                </span>
            </div>
        );
    };

    return (
        <>
            <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden flex flex-col">
                {/* Console Header */}
                <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                        <Terminal size={14} className="text-blue-500" />
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white">
                            Live WebSocket Event Stream Console
                        </h3>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Live Socket Stats */}
                        <div className="flex items-center gap-2 text-[10.5px] font-mono text-slate-500 mr-1">
                            <span className="flex items-center gap-1">
                                Conn: <strong className="text-slate-800 dark:text-slate-200">{socketTelemetry.connectCount}</strong>
                            </span>
                            <span>&bull;</span>
                            <span className="flex items-center gap-1">
                                Drops: <strong className={socketTelemetry.disconnectCount > 0 ? "text-amber-500" : "text-slate-800 dark:text-slate-200"}>{socketTelemetry.disconnectCount}</strong>
                            </span>
                            <span>&bull;</span>
                            <span className="flex items-center gap-1">
                                Reconnects: <strong className="text-slate-800 dark:text-slate-200">{socketTelemetry.reconnectAttempts}</strong>
                            </span>
                        </div>

                        {/* Filter Buttons */}
                        <div className="flex items-center bg-slate-100 dark:bg-white/[0.05] p-0.5 rounded-lg border border-slate-200/80 dark:border-white/10 text-[10px] font-mono">
                            {(["all", "info", "warn", "error"] as const).map((lvl) => (
                                <button
                                    key={lvl}
                                    type="button"
                                    onClick={() => setFilterLevel(lvl)}
                                    className={cn(
                                        "px-2 py-0.5 rounded capitalize transition cursor-pointer",
                                        filterLevel === lvl
                                            ? "bg-white dark:bg-white/15 text-slate-900 dark:text-white font-bold shadow-xs"
                                            : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                                    )}
                                >
                                    {lvl}
                                </button>
                            ))}
                        </div>

                        {/* Stream Controls */}
                        <button
                            type="button"
                            onClick={togglePause}
                            className={cn(
                                "h-7 px-2 rounded-lg border text-xs flex items-center gap-1 transition cursor-pointer",
                                isPaused
                                    ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30"
                                    : "border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                            )}
                            title={isPaused ? "Resume auto-scroll" : "Pause stream"}
                        >
                            {isPaused ? <Play size={11} /> : <Pause size={11} />}
                            <span className="text-[10px] font-mono hidden sm:inline">{isPaused ? "Paused" : "Live"}</span>
                        </button>

                        <button
                            type="button"
                            onClick={handleCopyLogs}
                            className="h-7 w-7 rounded-lg border border-slate-200 dark:border-white/10 text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center justify-center transition cursor-pointer"
                            title="Copy logs"
                        >
                            {copiedAll ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                        </button>

                        <button
                            type="button"
                            onClick={handleClearLogs}
                            className="h-7 w-7 rounded-lg border border-slate-200 dark:border-white/10 text-slate-500 hover:text-rose-500 flex items-center justify-center transition cursor-pointer"
                            title="Clear console"
                        >
                            <Trash2 size={12} />
                        </button>

                        <button
                            type="button"
                            onClick={() => setIsFullScreen(true)}
                            className="h-7 w-7 rounded-lg border border-slate-200 dark:border-white/10 text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center justify-center transition cursor-pointer"
                            title="Fullscreen"
                        >
                            <Maximize2 size={12} />
                        </button>
                    </div>
                </div>

                {/* Console Log Terminal Window */}
                <div
                    ref={inlineTerminalRef}
                    className="p-3 bg-[#08080a] text-slate-200 font-mono text-xs h-72 overflow-y-auto terminal-scrollbar space-y-0.5"
                >
                    {filteredEvents.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-1">
                            <Radio size={16} className="text-slate-600 animate-pulse" />
                            <span className="text-xs">Waiting for stream events...</span>
                        </div>
                    ) : (
                        filteredEvents.map(renderLogLine)
                    )}
                </div>
            </div>

            {/* Fullscreen Modal View with Smooth In/Out Animations */}
            {isFullScreen && (
                <div
                    onClick={closeFullScreen}
                    className={cn(
                        "fixed inset-0 z-[200] flex items-center justify-center bg-black/75 backdrop-blur-md p-4 sm:p-6",
                        isClosingFullScreen ? "animate-overlay-out" : "animate-overlay-in"
                    )}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className={cn(
                            "relative max-w-5xl w-full h-[85vh] rounded-2xl border border-slate-200/80 bg-[#08080a] shadow-2xl overflow-hidden flex flex-col dark:border-white/10",
                            isClosingFullScreen ? "animate-modal-out" : "animate-modal-in"
                        )}
                    >
                        {/* Fullscreen Header */}
                        <div className="px-5 py-3 border-b border-white/10 bg-white/[0.02] flex items-center justify-between shrink-0">
                            <div className="flex items-center gap-2">
                                <Terminal size={15} className="text-blue-500" />
                                <h3 className="font-display font-semibold text-sm text-white">
                                    WebSocket Debug Console (Fullscreen)
                                </h3>
                                <span className="text-xs font-mono text-slate-400 ml-2">
                                    {filteredEvents.length} events logged
                                </span>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={handleCopyLogs}
                                    className="h-8 px-3 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-white text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                                >
                                    {copiedAll ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                                    <span>{copiedAll ? "Copied" : "Copy All"}</span>
                                </button>
                                <button
                                    type="button"
                                    onClick={handleClearLogs}
                                    className="h-8 px-3 rounded-lg border border-white/10 bg-white/5 hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 text-xs font-medium flex items-center gap-1.5 transition cursor-pointer"
                                >
                                    <Trash2 size={13} />
                                    <span>Clear</span>
                                </button>
                                <button
                                    type="button"
                                    onClick={closeFullScreen}
                                    className="h-8 w-8 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white flex items-center justify-center transition cursor-pointer"
                                    title="Close fullscreen"
                                >
                                    <X size={15} />
                                </button>
                            </div>
                        </div>

                        {/* Fullscreen Scrollable Terminal */}
                        <div
                            ref={fullscreenTerminalRef}
                            className="flex-1 p-4 overflow-y-auto terminal-scrollbar space-y-0.5"
                        >
                            {filteredEvents.length === 0 ? (
                                <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                                    No logs recorded.
                                </div>
                            ) : (
                                filteredEvents.map(renderLogLine)
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
