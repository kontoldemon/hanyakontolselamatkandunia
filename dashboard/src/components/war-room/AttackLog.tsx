"use client";

import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";
import { Ban, Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { List, useListRef } from "react-window";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ScrollDownHint from "@/components/ui/ScrollDownHint";
import { cn } from "@/lib/utils";
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
    threatLogs?: ThreatLog[];
}

type SortMode = "newest" | "oldest";

export default function AttackLog({ selectedRegion, threatLogs: externalLogs }: AttackLogProps = {}) {
    const router = useRouter();
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;
    const [sortMode, setSortMode] = useState<SortMode>("newest");
    const [searchQuery, setSearchQuery] = useState("");
    const [blockingIp, setBlockingIp] = useState<string | null>(null);
    const [confirmBlockIp, setConfirmBlockIp] = useState<string | null>(null);
    const [isClosingBlock, setIsClosingBlock] = useState(false);
    const [activeBlockIp, setActiveBlockIp] = useState<string | null>(null);
    const [nowMs, setNowMs] = useState(0);
    const brandNewAfterMsRef = useRef(Date.now());

    useEffect(() => {
        if (confirmBlockIp) {
            setActiveBlockIp(confirmBlockIp);
            setIsClosingBlock(false);
        }
    }, [confirmBlockIp]);

    const handleCloseBlockModal = useCallback(() => {
        if (isClosingBlock) return;
        setIsClosingBlock(true);
        setTimeout(() => {
            setConfirmBlockIp(null);
            setActiveBlockIp(null);
            setIsClosingBlock(false);
        }, 180);
    }, [isClosingBlock]);

    useEffect(() => {
        setNowMs(Date.now());
        const timer = setInterval(() => setNowMs(Date.now()), 1000);
        return () => clearInterval(timer);
    }, []);
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

    const lastScrolledRegionRef = useRef<string | null>(null);

    useEffect(() => {
        if (!selectedRegion) {
            lastScrolledRegionRef.current = null;
            return;
        }
        // Only auto-scroll when selectedRegion changes to a new target, not on every live log update
        if (lastScrolledRegionRef.current === selectedRegion) {
            return;
        }
        const target = COUNTRY_MAP[selectedRegion] || selectedRegion;
        const index = filteredLogs.findIndex((log) => log.country === target || log.ip === target);
        if (index >= 0) {
            lastScrolledRegionRef.current = selectedRegion;
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
        blockingIp,
        onBlock: setConfirmBlockIp,
        onOpenSession: (ip: string) => router.push(`/sessions?focusIp=${encodeURIComponent(ip)}`),
        nowMs,
        brandNewAfterMs: brandNewAfterMsRef.current,
    };

    return (
        <div className="h-full flex flex-col min-h-0 overflow-hidden">
            <div className="sticky top-0 z-20 mb-2 flex items-center justify-between gap-2 shrink-0 pt-1 px-1">
                <div className="relative flex-1">
                    <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                        type="text"
                        placeholder="Search IP, HASSH..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-10 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg py-1 pl-7 pr-9 text-xs w-full focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-700 dark:text-slate-200 placeholder:text-slate-400 transition-all shadow-sm sm:h-8 sm:pr-6"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-0.5 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center text-slate-400 hover:text-slate-600 sm:right-1 sm:h-auto sm:w-auto"
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

            {activeBlockIp && (
                <div
                    onClick={handleCloseBlockModal}
                    className={cn(
                        "fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-md p-4",
                        isClosingBlock ? "animate-overlay-out" : "animate-overlay-in"
                    )}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        className={cn(
                            "relative max-w-[320px] w-full overflow-hidden rounded-3xl border border-slate-200/80 bg-white/95 p-6 text-center shadow-2xl backdrop-blur-2xl dark:border-white/10 dark:bg-[#0c0c0e] dark:shadow-[0_24px_60px_rgba(0,0,0,0.8)]",
                            isClosingBlock ? "animate-modal-out" : "animate-modal-in"
                        )}
                    >
                        {/* Dismiss Button */}
                        <button
                            type="button"
                            onClick={handleCloseBlockModal}
                            className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition cursor-pointer"
                            aria-label="Close"
                        >
                            <X size={15} />
                        </button>

                        {/* Icon Header */}
                        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200/80 bg-slate-100/80 text-slate-700 shadow-sm dark:border-white/10 dark:bg-white/[0.05] dark:text-slate-200">
                            <Ban size={16} className="text-rose-500 dark:text-rose-400" />
                        </div>

                        {/* Title & Description */}
                        <h3 className="font-display text-base font-bold tracking-tight text-slate-900 sm:text-lg dark:text-white">
                            Block IP
                        </h3>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                            Are you sure you want to block <span className="font-mono bg-slate-100 dark:bg-white/10 px-1.5 py-0.5 rounded text-rose-500 dark:text-rose-400 font-semibold">{activeBlockIp}</span> at the sensor firewall?
                        </p>

                        {/* Action Buttons */}
                        <div className="mt-5 flex items-center gap-2.5">
                            <button
                                type="button"
                                onClick={handleCloseBlockModal}
                                className="inline-flex h-11 flex-1 items-center justify-center rounded-full border border-slate-200/80 bg-white/80 dark:border-white/10 dark:bg-white/[0.04] text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/[0.08] transition active:scale-95 cursor-pointer"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    void executeBlockIp(activeBlockIp);
                                    handleCloseBlockModal();
                                }}
                                disabled={blockingIp === activeBlockIp}
                                className="inline-flex h-11 flex-1 items-center justify-center gap-1.5 rounded-full bg-rose-600 hover:bg-rose-500 px-4 text-xs font-semibold text-white shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
                            >
                                <Ban size={12} />
                                <span>{blockingIp === activeBlockIp ? "Blocking..." : "Confirm"}</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
