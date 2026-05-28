"use client";

import { ThreatLog, useLiveThreatLogs } from "@/lib/liveEvents";
import { Ban, Globe, Shield } from "lucide-react";
import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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

export default function AttackLog({ selectedRegion, underAttack = false, threatLogs: externalLogs }: AttackLogProps = {}) {
    const COUNTRY_MAP: Record<string, string> = {
        "China": "CN",
        "Russia": "RU",
        "Brazil": "BR",
        "United States of America": "US",
        "USA": "US",
        "Iran": "IR",
        "Vietnam": "VN"
    };

    const targetCode = selectedRegion ? COUNTRY_MAP[selectedRegion] : null;
    const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});
    const router = useRouter();
    const liveLogs = useLiveThreatLogs(!externalLogs);
    const threatLogs = externalLogs ?? liveLogs;
    const [sortMode, setSortMode] = useState<SortMode>("newest");
    const [visibleCount, setVisibleCount] = useState(40);
    const [blockingIp, setBlockingIp] = useState<string | null>(null);
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
    const filteredLogs = sorted;
    const visibleLogs = filteredLogs.slice(0, visibleCount);

    useEffect(() => {
        if (targetCode) {
            const index = sorted.findIndex((log) => log.country === targetCode);
            if (index >= 0) {
                if (index >= visibleCount) {
                    setVisibleCount(index + 10);
                }
                setTimeout(() => {
                    const firstMatch = sorted[index];
                    if (firstMatch && itemRefs.current[firstMatch.id]) {
                        const el = itemRefs.current[firstMatch.id];
                        if (el) {
                            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }
                }, 50);
            }
        }
    }, [targetCode, sorted, visibleCount]);

    async function blockIp(ip: string) {
        const confirmed = window.confirm(`Block ${ip} at the sensor firewall?`);
        if (!confirmed) {
            return;
        }
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
        }
    }

    return (
        <div className="h-full min-h-[520px] max-h-[720px] overflow-y-auto overflow-x-hidden terminal-scrollbar pr-1 scroll-smooth">
            <div className="sticky top-0 z-20 mb-2 bg-white/90 dark:bg-[#0a0a0a]/90 backdrop-blur border border-slate-200 dark:border-white/10 rounded-lg p-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>{filteredLogs.length} IPs</span>
                    {targetCode && <span className="font-mono">[{targetCode}]</span>}
                </div>
                <CustomDropdown
                    value={sortMode}
                    onChange={(value) => {
                        setSortMode(value as SortMode);
                        setVisibleCount(40);
                    }}
                    options={[
                        { label: "Newest", value: "newest" },
                        { label: "Oldest", value: "oldest" }
                    ]}
                    className="w-24"
                />
            </div>
            <div className="space-y-2 pb-4">
                {filteredLogs.length === 0 && (
                    <div className="p-4 rounded-lg border border-dashed border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-sm text-slate-500 dark:text-slate-400">
                        No live sensor events yet. Waiting for Socket.IO stream or backend admin API.
                    </div>
                )}
                {visibleLogs.map((log) => {
                    const isSelected = targetCode && log.country === targetCode;
                    const isDimmed = targetCode && log.country !== targetCode;
                    return (
                        <div 
                            key={log.id} 
                            ref={(el) => { itemRefs.current[log.id] = el; }}
                            role="link"
                            tabIndex={0}
                            onClick={() => router.push(`/sessions?focusIp=${encodeURIComponent(log.ip)}`)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                    event.preventDefault();
                                    router.push(`/sessions?focusIp=${encodeURIComponent(log.ip)}`);
                                }
                            }}
                            className={clsx(
                            "relative overflow-hidden w-full min-w-0 p-3 bg-white dark:bg-white/5 rounded-lg transition-all duration-300 cursor-pointer group",
                            isSelected ? "border-2 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.15)] bg-blue-50/50 dark:bg-blue-500/10" : "border border-slate-200 dark:border-white/5 hover:bg-slate-50 dark:hover:bg-white/10",
                            underAttack && "border-red-500/60 before:absolute before:inset-0 before:rounded-lg before:border before:border-red-500/50 before:animate-[pulse_1.1s_ease-in-out_infinite] before:pointer-events-none",
                            isDimmed ? "opacity-30 grayscale" : "opacity-100"
                        )}>
                            <div className="flex justify-between items-start mb-1">
                                <span className="text-[10px] font-mono text-slate-400">{log.latestTimestamp}</span>
                            <div className="flex items-center gap-2 shrink-0">
                                {log.blocked && (
                                    <span className="flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded border border-red-500/30 text-red-500 font-bold bg-red-500/10">
                                        <Shield size={10} />
                                        BLOCKED {log.lastMttb ?? ""}
                                    </span>
                                )}
                                <span className={clsx(
                                    "text-[10px] px-1.5 rounded font-bold",
                                    log.latestType === 'SSH_AUTH_FAIL' ? "bg-red-500/20 text-red-500" :
                                        log.latestType === 'COMMAND_EXEC' ? "bg-orange-500/20 text-orange-500" :
                                            "bg-blue-500/20 text-blue-500"
                                )}>{log.latestType}</span>
                            </div>
                        </div>
                        <div className="flex items-start justify-between gap-2 mt-1">
                            <div className="min-w-0 flex flex-wrap items-center gap-2 text-xs font-mono text-slate-700 dark:text-slate-300">
                                <Globe size={12} className="text-slate-500" />
                                <span className="break-all">{log.ip}</span>
                                <span className="opacity-50">({log.countryName ?? log.country})</span>
                                {log.isp && <span className="opacity-60 break-words">{log.isp}</span>}
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-300">
                                    {log.eventCount} events
                                </span>
                                {log.hassh && (
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-500 border border-purple-500/20">
                                        HASSH {log.hassh.slice(0, 8)}
                                    </span>
                                )}
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                                {log.latestMitreId && (
                                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-400 font-mono">
                                        {log.latestMitreId}
                                   </span>
                                )}
                                <button
                                    type="button"
                                    disabled={blockingIp === log.ip}
                                    title="Block IP"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        void blockIp(log.ip);
                                    }}
                                    className="inline-flex h-6 w-6 items-center justify-center rounded border border-red-500/30 text-red-500 hover:bg-red-500/10 disabled:opacity-50"
                                >
                                    <Ban size={12} />
                                </button>
                            </div>
                        </div>
                            <div className="mt-2 max-h-16 overflow-hidden text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-black/30 p-1.5 rounded whitespace-pre-wrap break-words">
                                $ {log.latestPayload}
                            </div>
                        </div>
                    );
                })}
                {visibleCount < filteredLogs.length && (
                    <button
                        type="button"
                        onClick={() => setVisibleCount((value) => value + 40)}
                        className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                        More
                    </button>
                )}
            </div>
        </div>
    );
}
