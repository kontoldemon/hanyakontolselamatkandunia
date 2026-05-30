"use client";

import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";
import { Ban, Globe, Shield, Search, X } from "lucide-react";
import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { List, type RowComponentProps, useListRef } from "react-window";
import CustomDropdown from "./CustomDropdown";

interface AttackLogProps {
    selectedRegion?: string | null;
    underAttack?: boolean;
    threatLogs?: ThreatLog[];
}

type SortMode = "newest" | "oldest";
type AggregatedLog = {
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

type RowData = {
    logs: AggregatedLog[];
    selectedRegion?: string | null;
    underAttack: boolean;
    blockingIp: string | null;
    onBlock: (ip: string) => void;
    onOpenSession: (ip: string) => void;
};

const COUNTRY_MAP: Record<string, string> = {
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

const ROW_HEIGHT = 160;
const ROW_GAP = 8;

function AttackLogRow({ index, style, logs, selectedRegion, underAttack, blockingIp, onBlock, onOpenSession }: RowComponentProps<RowData>) {
    const log = logs[index];
    const target = selectedRegion ? (COUNTRY_MAP[selectedRegion] || selectedRegion) : null;
    const isSelected = !!target && (log.country === target || log.ip === target);
    const isDimmed = !!target && log.country !== target && log.ip !== target;
    const normalizePreview = (payload: string, type: string) => {
        const normalized = (payload || "").trim().toLowerCase();
        if (normalized.startsWith("cloudsentinel.session.connect")) {
            return { text: "Session opened", tag: "OPEN" };
        }
        if (normalized.startsWith("cloudsentinel.session.closed")) {
            return { text: "Session closed", tag: "CLOSE" };
        }
        if (normalized.startsWith("cloudsentinel.client.version")) {
            return { text: "Client banner observed", tag: "VERSION" };
        }
        if (
            normalized === "auth-attempt" ||
            normalized.startsWith("cloudsentinel.login.failed") ||
            normalized.startsWith("cloudsentinel.login.success") ||
            type === "SSH_AUTH_FAIL"
        ) {
            return { text: "Authentication event", tag: "AUTH" };
        }
        return { text: payload, tag: "" };
    };
    const preview = normalizePreview(log.latestPayload, log.latestType);
    const compactPreviewText = (preview.text || "").replace(/\s+/g, " ").trim();

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
                    "relative overflow-hidden h-full w-full min-w-0 p-3 bg-white dark:bg-white/5 rounded-xl transition-all duration-300 cursor-pointer group flex flex-col justify-between",
                    isSelected ? "border-2 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.15)] bg-blue-50/50 dark:bg-blue-500/10" : "border border-slate-200 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/10",
                    underAttack && "border-red-500/60 before:absolute before:inset-0 before:rounded-xl before:border before:border-red-500/50 before:animate-[pulse_1.1s_ease-in-out_infinite] before:pointer-events-none",
                    isDimmed ? "opacity-30 grayscale" : "opacity-100",
                )}
            >
                <div className="flex justify-between items-center mb-2">
                    <span className="text-[11px] font-medium tracking-wide text-slate-400">{log.latestTimestamp}</span>
                    <div className="flex items-center gap-2 shrink-0">
                        {log.blocked && (
                            <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border border-red-500/30 text-red-500 font-bold bg-red-500/10">
                                <Shield size={12} />
                                BLOCKED {log.lastMttb ?? ""}
                            </span>
                        )}
                        <span
                            className={clsx(
                                "text-[10px] px-2 py-0.5 rounded-full font-bold",
                                log.latestType === "SSH_AUTH_FAIL" ? "bg-red-500/10 border border-red-500/20 text-red-500" :
                                    log.latestType === "COMMAND_EXEC" ? "bg-orange-500/10 border border-orange-500/20 text-orange-500" :
                                        "bg-blue-500/10 border border-blue-500/20 text-blue-500",
                            )}
                        >
                            {log.latestType}
                        </span>
                    </div>
                </div>

                <div className="flex justify-between items-start gap-3 mb-2">
                    <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-1.5">
                            <Globe size={14} className="text-slate-400 shrink-0" />
                            <span className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 break-all">{log.ip}</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5 text-xs text-slate-500 dark:text-slate-400 truncate">
                            <span className="truncate">{log.countryName ?? log.country}</span>
                            {log.isp && (
                                <>
                                    <span className="text-slate-300 dark:text-slate-600">&bull;</span>
                                    <span className="truncate" title={log.isp}>{log.isp}</span>
                                </>
                            )}
                        </div>
                    </div>
                    <button
                        type="button"
                        disabled={blockingIp === log.ip}
                        title="Block IP"
                        onClick={(event) => {
                            event.stopPropagation();
                            onBlock(log.ip);
                        }}
                        className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/30 text-red-500 hover:bg-red-500/10 disabled:opacity-50 transition-colors"
                    >
                        <Ban size={14} />
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300 font-medium">
                        {log.eventCount} events
                    </span>
                    {log.hassh && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 font-medium font-mono">
                            HASSH {log.hassh.slice(0, 8)}
                        </span>
                    )}
                    {log.latestMitreId && (
                        <span
                            className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 font-mono font-medium truncate max-w-[100px]"
                            title={log.latestMitreId}
                        >
                            {log.latestMitreId}
                        </span>
                    )}
                </div>

                <div className="flex-1 w-full bg-slate-50 dark:bg-black/40 rounded-lg p-2.5 border border-slate-200/50 dark:border-white/5 flex items-center overflow-hidden min-h-[44px] max-h-[44px] mb-1">
                    {preview.tag ? (
                        <div className="flex items-center gap-2 w-full">
                            <span className="shrink-0 rounded border border-blue-500/30 bg-blue-500/10 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-blue-600 dark:text-blue-400">
                                {preview.tag}
                            </span>
                            <span
                                className="text-xs font-mono text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-1 break-all"
                                title={compactPreviewText}
                            >
                                {compactPreviewText || "-"}
                            </span>
                        </div>
                    ) : (
                        <span
                            className="text-xs font-mono text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-1 break-all w-full"
                            title={compactPreviewText}
                        >
                            <span className="text-slate-400 dark:text-slate-500 mr-1.5">$</span>
                            {compactPreviewText || "-"}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function AttackLog({ selectedRegion, underAttack = false, threatLogs: externalLogs }: AttackLogProps = {}) {
    const router = useRouter();
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;
    const [sortMode, setSortMode] = useState<SortMode>("newest");
    const [searchQuery, setSearchQuery] = useState("");
    const [blockingIp, setBlockingIp] = useState<string | null>(null);
    const [confirmBlockIp, setConfirmBlockIp] = useState<string | null>(null);
    const listRef = useListRef(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [listHeight, setListHeight] = useState(480);

    const aggregatedLogs = useMemo(() => {
        const grouped = new Map<string, AggregatedLog>();
        for (const log of threatLogs) {
            const current = grouped.get(log.ip);
            if (!current) {
                grouped.set(log.ip, {
                    id: `ip-${log.ip}`,
                    ip: log.ip,
                    country: log.country,
                    countryName: log.countryName,
                    isp: log.isp,
                    latestTimestamp: log.timestamp,
                    latestEpochMs: log.epochMs,
                    latestType: log.type,
                    latestPayload: log.payload,
                    latestMitreId: log.mitreId,
                    hassh: log.hassh,
                    eventCount: 1,
                    blocked: log.action === "Blocked",
                    lastMttb: log.timeToBlock,
                });
                continue;
            }
            current.eventCount += 1;
            current.blocked = current.blocked || log.action === "Blocked";
            if (!current.lastMttb && log.timeToBlock) {
                current.lastMttb = log.timeToBlock;
            }
            if (!current.hassh && log.hassh) {
                current.hassh = log.hassh;
            }
            if (log.epochMs > current.latestEpochMs) {
                current.latestTimestamp = log.timestamp;
                current.latestEpochMs = log.epochMs;
                current.latestType = log.type;
                current.latestPayload = log.payload;
                current.latestMitreId = log.mitreId;
                current.country = log.country;
                current.countryName = log.countryName;
                current.isp = log.isp;
                current.hassh = current.hassh || log.hassh;
                if (log.timeToBlock) {
                    current.lastMttb = log.timeToBlock;
                }
            }
        }
        return [...grouped.values()];
    }, [threatLogs]);

    const sorted = [...aggregatedLogs].sort((a, b) =>
        sortMode === "newest" ? b.latestEpochMs - a.latestEpochMs : a.latestEpochMs - b.latestEpochMs,
    );
    const filteredLogs = sorted.filter((log) => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return (
            log.ip.includes(q) ||
            log.countryName?.toLowerCase().includes(q) ||
            log.country.toLowerCase().includes(q) ||
            log.hassh?.toLowerCase().includes(q)
        );
    });

    useEffect(() => {
        const el = containerRef.current;
        if (!el) {
            return;
        }
        const update = () => setListHeight(Math.max(200, el.clientHeight));
        update();
        const observer = new ResizeObserver(update);
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!selectedRegion) {
            return;
        }
        const target = COUNTRY_MAP[selectedRegion] || selectedRegion;
        const index = filteredLogs.findIndex((log) => log.country === target || log.ip === target);
        if (index >= 0) {
            listRef.current?.scrollToRow({ index, align: "center", behavior: "smooth" });
        }
    }, [selectedRegion, filteredLogs, listRef]);

    async function executeBlockIp(ip: string) {
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
            setConfirmBlockIp(null);
        }
    }

    const rowData: RowData = {
        logs: filteredLogs,
        selectedRegion,
        underAttack,
        blockingIp,
        onBlock: setConfirmBlockIp,
        onOpenSession: (ip: string) => router.push(`/sessions?focusIp=${encodeURIComponent(ip)}`),
    };

    return (
        <div className="h-full flex flex-col min-h-0 overflow-hidden">
            <div className="sticky top-0 z-20 mb-2 bg-white/90 dark:bg-[#0a0a0a]/90 backdrop-blur border border-slate-200 dark:border-white/10 rounded-lg p-2 flex items-center justify-between gap-2 shrink-0">
                <div className="flex flex-1 items-center gap-2">
                    <span className="text-xs text-slate-500 whitespace-nowrap">{filteredLogs.length} IPs</span>
                    <div className="relative flex-1 max-w-[200px]">
                        <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search IP, HASSH..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded py-1 pl-7 pr-6 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 dark:text-slate-200"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                            >
                                <X size={12} />
                            </button>
                        )}
                    </div>
                </div>
                <CustomDropdown
                    value={sortMode}
                    onChange={(value) => setSortMode(value as SortMode)}
                    options={[
                        { label: "Newest", value: "newest" },
                        { label: "Oldest", value: "oldest" },
                    ]}
                    className="w-24"
                />
            </div>

            <div ref={containerRef} className="flex-1 min-h-0 overflow-hidden">
                {threatLogs.length === 0 ? (
                    <div className="p-4 rounded-lg border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-slate-500 dark:text-slate-400">
                        No live sensor events yet. Waiting for Socket.IO stream or backend admin API.
                    </div>
                ) : filteredLogs.length === 0 ? (
                    <div className="p-4 rounded-lg border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-slate-500 dark:text-slate-400 font-medium">
                        No matching live events found for &quot;{searchQuery}&quot;.
                    </div>
                ) : (
                    <List
                        listRef={listRef}
                        rowCount={filteredLogs.length}
                        rowHeight={ROW_HEIGHT + ROW_GAP}
                        rowProps={rowData}
                        rowComponent={AttackLogRow}
                        style={{ height: listHeight }}
                        className="terminal-scrollbar pr-1"
                    />
                )}
            </div>

            {confirmBlockIp && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white dark:bg-[#0a0a0a] p-6 rounded-2xl border border-slate-200 dark:border-white/10 shadow-2xl max-w-sm w-full mx-4 animate-in zoom-in-95 duration-200" onClick={(e) => e.stopPropagation()}>
                        <h3 className="text-lg font-bold mb-2">Block IP</h3>
                        <p className="text-slate-500 dark:text-slate-400 text-sm mb-6">Are you sure you want to block <span className="font-mono bg-slate-100 dark:bg-white/10 px-1 rounded">{confirmBlockIp}</span> at the sensor firewall?</p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setConfirmBlockIp(null);
                                }}
                                className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    void executeBlockIp(confirmBlockIp);
                                }}
                                disabled={blockingIp === confirmBlockIp}
                                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-bold shadow-lg shadow-red-500/20 hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {blockingIp === confirmBlockIp ? "Blocking..." : "Confirm"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
