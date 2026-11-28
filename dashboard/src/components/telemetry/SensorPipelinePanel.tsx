"use client";

import { Database, HardDrive, Radio, Server, ShieldCheck } from "lucide-react";
import type { SensorOperations } from "@/lib/liveEvents";
import { cn } from "@/lib/utils";

interface SensorPipelinePanelProps {
    operations: SensorOperations | null;
}

export default function SensorPipelinePanel({ operations }: SensorPipelinePanelProps) {
    const isLive = operations?.status === "live";
    const readiness = (operations?.sensor?.readiness?.data ?? {}) as Record<string, unknown>;
    const redisConnected = readiness.redis_connected === true;
    const clickhouseEnabled = readiness.clickhouse_enabled === true;
    const clickhouseOk = readiness.clickhouse_ok === true;
    const streamEnabled = readiness.stream_enabled === true;
    const pendingEvents = typeof readiness.pending_events === "number" ? readiness.pending_events : 0;
    const sshPort = typeof readiness.ssh_port === "number" ? readiness.ssh_port : null;
    const streamPort = typeof readiness.stream_port === "number" && readiness.stream_port > 0 ? readiness.stream_port : null;
    const deceptionLevel = typeof readiness.deception_level === "string" ? readiness.deception_level : "";
    const deceptionMode = readiness.deception_mode === "deterministic" ? "Deterministic" : readiness.deception_mode === "dynamic" ? "Dynamic" : "";
    const authoritative = operations?.authoritative === true;
    const telemetrySource = operations?.telemetrySource ?? "runtime";
    const deceptionLabel = deceptionLevel === "full"
        ? "Full VFS"
        : deceptionLevel === "restricted"
            ? "Restricted VFS"
            : deceptionLevel === "listener"
                ? "Port listener"
                : "Unknown";

    return (
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex items-center justify-between gap-2">
                <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                    <Server size={14} className="text-blue-500" /> Sensor Engine &amp; Storage Bus
                </h3>
                <span
                    title={authoritative ? "ClickHouse Authoritative" : `Storage: ${telemetrySource}`}
                    aria-label={authoritative ? "ClickHouse Authoritative" : `Storage: ${telemetrySource}`}
                    className="inline-flex items-center justify-center p-1"
                >
                    <span className={cn(
                        "w-2 h-2 rounded-full",
                        authoritative ? "bg-emerald-500 animate-pulse" : isLive ? "bg-amber-500" : "bg-rose-500"
                    )} />
                </span>
            </div>

            <div className="p-3 sm:p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {/* 1. Sensor Daemon Node */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <Radio size={13} className="text-blue-500" /> AsyncSSH Sensor
                        </span>
                        <span
                            title={isLive ? "Online" : "Offline"}
                            aria-label={isLive ? "Online" : "Offline"}
                            className={cn(
                                "w-2 h-2 rounded-full shrink-0",
                                isLive ? "bg-emerald-500" : "bg-rose-500"
                            )}
                        />
                    </div>
                    <div className="space-y-0.5 leading-tight text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Port:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">{sshPort ? `${sshPort} / TCP` : "Unavailable"}</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">VFS:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">{deceptionLabel}{deceptionMode ? ` / ${deceptionMode}` : ""}</span>
                        </div>
                    </div>
                </div>

                {/* 2. Pipeline Message Bus */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <HardDrive size={13} className="text-amber-500" /> Event Pipeline
                        </span>
                        <span
                            title={redisConnected ? "Redis Streams Connected" : "In-Memory Queue Fallback"}
                            aria-label={redisConnected ? "Redis Streams Connected" : "In-Memory Queue Fallback"}
                            className={cn(
                                "w-2 h-2 rounded-full shrink-0",
                                redisConnected ? "bg-emerald-500" : "bg-amber-500"
                            )}
                        />
                    </div>
                    <div className="space-y-0.5 leading-tight text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Engine:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">{redisConnected ? "Redis Streams" : "Memory Ring"}</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Queue:</span>
                            <span className={cn("font-semibold truncate", pendingEvents > 0 ? "text-amber-500" : "text-slate-700 dark:text-slate-300")}>
                                {pendingEvents} events
                            </span>
                        </div>
                    </div>
                </div>

                {/* 3. ClickHouse Columnar Store */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <Database size={13} className="text-purple-500" /> ClickHouse Store
                        </span>
                        <span
                            title={clickhouseOk ? "Healthy" : clickhouseEnabled ? "Degraded" : "Disabled"}
                            aria-label={clickhouseOk ? "Healthy" : clickhouseEnabled ? "Degraded" : "Disabled"}
                            className={cn(
                                "w-2 h-2 rounded-full shrink-0",
                                clickhouseOk ? "bg-emerald-500" : clickhouseEnabled ? "bg-amber-500" : "bg-rose-500"
                            )}
                        />
                    </div>
                    <div className="space-y-0.5 leading-tight text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Store:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">{clickhouseOk ? "Columnar Fast" : "Local State"}</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Dedup:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">ClickHouse Token</span>
                        </div>
                    </div>
                </div>

                {/* 4. Live Stream Socket */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <ShieldCheck size={13} className="text-emerald-500" /> Stream Gateway
                        </span>
                        <span
                            title={streamEnabled ? "Active" : "Standby"}
                            aria-label={streamEnabled ? "Active" : "Standby"}
                            className={cn(
                                "w-2 h-2 rounded-full shrink-0",
                                streamEnabled ? "bg-emerald-500" : "bg-amber-500"
                            )}
                        />
                    </div>
                    <div className="space-y-0.5 leading-tight text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Port:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">{streamPort ? `${streamPort} / TCP` : "Disabled"}</span>
                        </div>
                        <div className="flex items-baseline gap-2">
                            <span className="shrink-0">Mode:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold truncate">Socket.IO Push</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
