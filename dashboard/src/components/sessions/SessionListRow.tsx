"use client";

import { Clock } from "lucide-react";
import { type RowComponentProps } from "react-window";
import { cn } from "@/lib/utils";
import type { CapturedSession } from "@/lib/liveEvents";

export function HighlightText({ text, highlight }: { text: string; highlight: string }) {
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
                ),
            )}
        </>
    );
}

export function formatSoarAction(action?: string) {
    const normalized = (action ?? "none").trim().toLowerCase();
    if (!normalized || normalized === "none") {
        return "none";
    }
    return normalized;
}

export function isBlockEffective(action?: string, reported?: boolean) {
    if (reported) {
        return true;
    }
    const normalized = formatSoarAction(action);
    return normalized === "iptables_block" || normalized === "already_blocked";
}

export function blockStateText(action?: string, effective?: boolean) {
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

export function formatDurationLive(session: { duration: string; status: string; startedAtEpochMs?: number }, nowMs: number) {
    if ((session.status || "").toLowerCase() !== "active" || !session.startedAtEpochMs) {
        return session.duration;
    }
    const elapsed = Math.max(0, Math.floor((nowMs - session.startedAtEpochMs) / 1000));
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes}m ${seconds}s`;
}

export function formatSeenTime(epochMs?: number): string {
    if (!epochMs || !Number.isFinite(epochMs) || epochMs <= 0) {
        return "N/A";
    }
    return new Date(epochMs).toLocaleString([], {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
    });
}

export type SessionRowData = {
    sessions: CapturedSession[];
    selectedSessionId: string | null;
    focusIp: string;
    nowMs: number;
    searchQuery: string;
    onSelect: (session: CapturedSession) => void;
    viewedSessionIds?: Set<string>;
};

export const SESSION_ROW_HEIGHT = 90;
export const SESSION_ROW_GAP = 6;

export function SessionRow({ index, style, sessions, selectedSessionId, focusIp, nowMs, searchQuery, onSelect, viewedSessionIds }: RowComponentProps<SessionRowData>) {
    const session = sessions[index];
    const isSelected = selectedSessionId === session.id;
    const isFocused = !!focusIp && session.ip === focusIp;
    const isBrandNew = Boolean(
        nowMs &&
        nowMs > 0 &&
        (
            (session.startedAtEpochMs && nowMs - session.startedAtEpochMs < 3500) ||
            (session.firstSeenEpochMs && nowMs - session.firstSeenEpochMs < 3500)
        )
    );
    const attackCount = session.input?.length ?? 0;

    return (
        <div style={{ ...style, paddingBottom: SESSION_ROW_GAP }}>
            <div
                onClick={() => onSelect(session)}
                className={cn(
                    "cursor-pointer p-2.5 rounded-xl border transition-all duration-500 shadow-sm h-full flex flex-col justify-between",
                    isSelected
                        ? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
                        : isBrandNew
                            ? "border-emerald-500/50 bg-emerald-50/50 dark:bg-emerald-500/[0.08] shadow-[0_0_12px_rgba(16,185,129,0.14)] animate-in fade-in duration-200"
                            : "bg-white dark:bg-[#0a0a0a] border-slate-100 dark:border-white/5 hover:border-blue-300 dark:hover:border-blue-500/30",
                    isFocused && !isSelected && "ring-1 ring-blue-500",
                )}
            >
                <div>
                    <div className="flex justify-between items-center gap-2 mb-0.5">
                        <div className="flex items-center gap-1.5 min-w-0">
                            <h3 className="font-semibold text-slate-900 dark:text-white font-mono text-xs truncate">
                                <HighlightText text={session.ip} highlight={searchQuery} />
                            </h3>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[9.5px] leading-none px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/[0.06] text-slate-600 dark:text-slate-300 font-mono font-medium">
                                {attackCount} ATK
                            </span>
                            {(session.status || "").toLowerCase() === "active" && (
                                <span className="text-[9.5px] leading-none px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 animate-pulse border border-emerald-500/20 font-semibold">
                                    Live
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                        <span className="flex items-center gap-1 truncate max-w-[115px]">
                            <HighlightText text={session.countryName || session.country} highlight={searchQuery} />
                        </span>
                        <span className="flex items-center gap-1"><Clock size={10} /> {formatDurationLive(session, nowMs)}</span>
                        <span className="flex items-center gap-1 font-mono text-[10px] truncate max-w-[100px]"><HighlightText text={session.client || "Unknown"} highlight={searchQuery} /></span>
                    </div>
                </div>
                <div className="mt-1 grid grid-cols-1 gap-0.5 text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                    <span className="truncate">First: {formatSeenTime(session.firstSeenEpochMs ?? session.startedAtEpochMs)}</span>
                    <span className="truncate">Last: {formatSeenTime(session.lastSeenEpochMs ?? session.firstSeenEpochMs ?? session.startedAtEpochMs)}</span>
                </div>
            </div>
        </div>
    );
}
