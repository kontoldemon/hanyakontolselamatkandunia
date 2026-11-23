"use client";

import { Ban, Shield } from "lucide-react";
import clsx from "clsx";
import { type RowComponentProps } from "react-window";

export type AggregatedLog = {
    id: string;
    ip: string;
    country: string;
    countryName?: string;
    isp?: string;
    latestTimestamp: string;
    latestEpochMs: number;
    latestType: string;
    latestPayload: string;
    latestMitreId: string;
    hassh?: string;
    eventCount: number;
    blocked: boolean;
    lastMttb: string | null;
};

export type RowData = {
    logs: AggregatedLog[];
    selectedRegion?: string | null;
    underAttack: boolean;
    blockingIp: string | null;
    onBlock: (ip: string) => void;
    onOpenSession: (ip: string) => void;
};

export const COUNTRY_MAP: Record<string, string> = {
    China: "CN",
    Russia: "RU",
    Brazil: "BR",
    "United States of America": "US",
    USA: "US",
    Iran: "IR",
    Vietnam: "VN",
    Indonesia: "ID",
    India: "IN",
};

export const ROW_HEIGHT = 112;
export const ROW_GAP = 8;

function normalizePreview(payload: string, type: string) {
    const original = (payload || "").trim();
    const normalized = original.toLowerCase();
    if (normalized.startsWith("[auth]")) {
        return { text: original.replace(/^\[auth\]\s*/i, ""), tag: "AUTH" };
    }
    if (normalized.startsWith("cloudsentinel.session.connect")) {
        return { text: "Session opened", tag: "OPEN" };
    }
    if (normalized.startsWith("cloudsentinel.session.closed")) {
        return { text: "Session closed", tag: "CLOSE" };
    }
    if (normalized.startsWith("cloudsentinel.client.version")) {
        return { text: "Client banner observed", tag: "VER" };
    }
    if (
        normalized === "auth-attempt" ||
        normalized.startsWith("cloudsentinel.login.failed") ||
        normalized.startsWith("cloudsentinel.login.success") ||
        type === "SSH_AUTH_FAIL"
    ) {
        return { text: "Authentication attempt", tag: "AUTH" };
    }
    return { text: original, tag: "" };
}

export function AttackLogRow({ index, style, logs, selectedRegion, blockingIp, onBlock, onOpenSession }: RowComponentProps<RowData>) {
    const log = logs[index];
    const target = selectedRegion ? (COUNTRY_MAP[selectedRegion] || selectedRegion) : null;
    const isSelected = !!target && (log.country === target || log.ip === target);
    const isDimmed = !!target && log.country !== target && log.ip !== target;
    const preview = normalizePreview(log.latestPayload, log.latestType);
    const compactPreviewText = (preview.text || "").replace(/\s+/g, " ").trim();

    const typeAccent =
        log.latestType === "SSH_AUTH_FAIL"
            ? { dot: "bg-rose-500", text: "text-rose-600 dark:text-rose-400" }
            : log.latestType === "COMMAND_EXEC"
                ? { dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" }
                : { dot: "bg-blue-500", text: "text-blue-600 dark:text-blue-400" };

    return (
        <div style={{ ...style, paddingBottom: ROW_GAP }}>
            <div
                role="link"
                tabIndex={0}
                onClick={() => onOpenSession(log.ip)}
                onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onOpenSession(log.ip);
                    }
                }}
                className={clsx(
                    "relative overflow-hidden h-full w-full min-w-0 px-3 py-2.5 rounded-xl transition-all duration-200 cursor-pointer group flex flex-col justify-between",
                    isSelected
                        ? "border border-blue-500/70 bg-blue-50/60 dark:bg-blue-500/10 shadow-[0_0_16px_rgba(37,99,235,0.12)]"
                        : "border border-slate-200/80 dark:border-white/[0.07] bg-white dark:bg-white/[0.025] hover:border-slate-300 dark:hover:border-white/15 hover:bg-slate-50/70 dark:hover:bg-white/[0.04]",
                    isDimmed ? "opacity-30 grayscale" : "opacity-100",
                )}
            >
                {/* Row 1: IP + Status Dot + Timestamp + Action */}
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                        <span className={clsx("h-1.5 w-1.5 rounded-full shrink-0", typeAccent.dot)} />
                        <span className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                            {log.ip}
                        </span>
                        <span className="text-[11px] text-slate-500 dark:text-slate-400 truncate hidden sm:inline">
                            {log.countryName ?? log.country}
                        </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        {log.blocked && (
                            <span
                                className="inline-flex items-center gap-0.5 text-[10px] font-mono font-medium text-rose-600 dark:text-rose-400"
                                title={log.lastMttb ? `Blocked in ${log.lastMttb}` : "Blocked"}
                            >
                                <Shield size={10} />
                                <span>{log.lastMttb || "Blocked"}</span>
                            </span>
                        )}
                        <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500">
                            {log.latestTimestamp.split(".")[0]}
                        </span>
                        <button
                            type="button"
                            disabled={blockingIp === log.ip}
                            title="Block IP"
                            onClick={(event) => {
                                event.stopPropagation();
                                onBlock(log.ip);
                            }}
                            className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 disabled:opacity-40 transition-colors"
                        >
                            <Ban size={12} />
                        </button>
                    </div>
                </div>

                {/* Row 2: Clean Inline Metadata Strip (no pill clutter) */}
                <div className="flex items-center justify-between gap-2 text-[10.5px] text-slate-500 dark:text-slate-400">
                    <div className="flex items-center gap-1.5 min-w-0 truncate font-mono">
                        <span>{log.eventCount} {log.eventCount === 1 ? "evt" : "evts"}</span>
                        {log.latestMitreId && (
                            <>
                                <span className="text-slate-300 dark:text-slate-600">&middot;</span>
                                <span className="truncate">{log.latestMitreId}</span>
                            </>
                        )}
                        {log.hassh && (
                            <>
                                <span className="text-slate-300 dark:text-slate-600">&middot;</span>
                                <span className="text-indigo-600/90 dark:text-indigo-400/90 truncate">{log.hassh.slice(0, 8)}</span>
                            </>
                        )}
                    </div>
                    <span className={clsx("shrink-0 font-mono text-[9.5px] font-semibold uppercase tracking-wide", typeAccent.text)}>
                        {log.latestType.replace(/_/g, " ")}
                    </span>
                </div>

                {/* Row 3: Minimalist Single-Line Command Preview */}
                <div className="w-full rounded-md bg-slate-50 dark:bg-black/35 px-2 py-1 border border-slate-200/50 dark:border-white/[0.04] flex items-center gap-1.5 overflow-hidden">
                    {preview.tag ? (
                        <span className="shrink-0 font-mono text-[9px] font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                            {preview.tag}
                        </span>
                    ) : (
                        <span className="shrink-0 font-mono text-[10.5px] text-slate-400 dark:text-slate-500">$</span>
                    )}
                    <span
                        className="text-[11px] font-mono text-slate-600 dark:text-slate-300 truncate"
                        title={compactPreviewText}
                    >
                        {compactPreviewText || "-"}
                    </span>
                </div>
            </div>
        </div>
    );
}
