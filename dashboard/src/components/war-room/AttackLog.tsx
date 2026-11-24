"use client";

import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";
import { Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { List, useListRef } from "react-window";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import {
    AttackLogRow,
    COUNTRY_MAP,
    ROW_GAP,
    ROW_HEIGHT,
    type AggregatedLog,
    type RowData,
} from "./AttackLogRow";

interface AttackLogProps {
    selectedRegion?: string | null;
    underAttack?: boolean;
    threatLogs?: ThreatLog[];
}

type SortMode = "newest" | "oldest";

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
    const [lastVisibleRow, setLastVisibleRow] = useState(0);

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
            <div className="sticky top-0 z-20 mb-2 bg-white/90 dark:bg-[#0a0a0a]/90 backdrop-blur border border-slate-200 dark:border-white/10 rounded-lg p-1.5 flex items-center justify-between gap-2 shrink-0">
                <div className="relative flex-1">
                    <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                        type="text"
                        placeholder="Search IP, HASSH..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-8 bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-lg py-1 pl-7 pr-6 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 dark:text-slate-200 placeholder:text-slate-400"
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
                <CustomDropdown
                    value={sortMode}
                    onChange={(value) => setSortMode(value as SortMode)}
                    options={[
                        { label: "Newest", value: "newest" },
                        { label: "Oldest", value: "oldest" },
                    ]}
                    className="w-24 shrink-0"
                />
            </div>

            <div ref={containerRef} className="relative flex-1 min-h-0 overflow-hidden">
                {threatLogs.length === 0 ? (
                    <div className="p-4 rounded-lg border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-xs text-slate-500 dark:text-slate-400">
                        No live sensor events yet. Waiting for Socket.IO stream or backend admin API.
                    </div>
                ) : filteredLogs.length === 0 ? (
                    <div className="p-4 rounded-lg border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-xs text-slate-500 dark:text-slate-400 font-medium">
                        No matching live events found for &quot;{searchQuery}&quot;.
                    </div>
                ) : (
                    <>
                        <List
                            listRef={listRef}
                            rowCount={filteredLogs.length}
                            rowHeight={ROW_HEIGHT + ROW_GAP}
                            rowProps={rowData}
                            rowComponent={AttackLogRow}
                            onRowsRendered={(visibleRows) => setLastVisibleRow(visibleRows.stopIndex)}
                            style={{ height: listHeight }}
                            className="terminal-scrollbar pr-1"
                        />
                        <ScrollDownHint
                            visible={
                                filteredLogs.length * (ROW_HEIGHT + ROW_GAP) > listHeight + 8 &&
                                lastVisibleRow < filteredLogs.length - 1
                            }
                            onScrollDown={() => {
                                const nextIdx = Math.min(filteredLogs.length - 1, lastVisibleRow + 2);
                                listRef.current?.scrollToRow({ index: nextIdx, align: "end", behavior: "smooth" });
                            }}
                        />
                    </>
                )}
            </div>

            {confirmBlockIp && (
                <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
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
