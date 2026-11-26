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
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                    <Server size={14} className="text-blue-500" /> Sensor Engine &amp; Storage Bus
                </h3>
                <div className="flex items-center gap-2">
                    <span className={cn(
                        "text-[10px] font-mono px-2 py-0.5 rounded-full border shrink-0 flex items-center gap-1.5",
                        authoritative
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                            : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                    )}>
                        <span className={cn(
                            "w-1.5 h-1.5 rounded-full",
                            authoritative ? "bg-emerald-500 animate-pulse" : "bg-blue-500"
                        )} />
                        {authoritative ? "ClickHouse Authoritative" : `Storage: ${telemetrySource}`}
                    </span>
                </div>
            </div>

            <div className="p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {/* 1. Sensor Daemon Node */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-2.5">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <Radio size={13} className="text-blue-500" /> AsyncSSH Sensor
                        </span>
                        <span className={cn(
                            "text-[9.5px] font-mono px-1.5 py-0.5 rounded font-semibold",
                            isLive
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20"
                        )}>
                            {isLive ? "ONLINE" : "OFFLINE"}
                        </span>
                    </div>
                    <div className="space-y-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex justify-between">
                            <span>Ingress Port:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">{sshPort ? `${sshPort} / TCP` : "Unavailable"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>VFS Mode:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">{deceptionLabel}{deceptionMode ? ` / ${deceptionMode}` : ""}</span>
                        </div>
                    </div>
                </div>

                {/* 2. Pipeline Message Bus */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-2.5">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <HardDrive size={13} className="text-amber-500" /> Event Pipeline
                        </span>
                        <span className={cn(
                            "text-[9.5px] font-mono px-1.5 py-0.5 rounded font-semibold",
                            redisConnected
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                        )}>
                            {redisConnected ? "CONNECTED" : "IN-MEMORY QUEUE"}
                        </span>
                    </div>
                    <div className="space-y-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex justify-between">
                            <span>Bus Engine:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">{redisConnected ? "Redis / NATS" : "Memory Ring"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>Pending In Queue:</span>
                            <span className={cn("font-semibold", pendingEvents > 0 ? "text-amber-500" : "text-slate-700 dark:text-slate-300")}>
                                {pendingEvents} events
                            </span>
                        </div>
                    </div>
                </div>

                {/* 3. ClickHouse Columnar Store */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-2.5">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <Database size={13} className="text-purple-500" /> ClickHouse Store
                        </span>
                        <span className={cn(
                            "text-[9.5px] font-mono px-1.5 py-0.5 rounded font-semibold",
                            clickhouseOk
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                : clickhouseEnabled
                                    ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                                    : "bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-400"
                        )}>
                            {clickhouseOk ? "HEALTHY" : clickhouseEnabled ? "DEGRADED" : "DISABLED"}
                        </span>
                    </div>
                    <div className="space-y-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex justify-between">
                            <span>Persistence:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">{clickhouseOk ? "Columnar Fast" : "Local State"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>Deduplication:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">Active Hash</span>
                        </div>
                    </div>
                </div>

                {/* 4. Live Stream Socket */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between space-y-2.5">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <ShieldCheck size={13} className="text-emerald-500" /> Stream Gateway
                        </span>
                        <span className={cn(
                            "text-[9.5px] font-mono px-1.5 py-0.5 rounded font-semibold",
                            streamEnabled
                                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                                : "bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-400"
                        )}>
                            {streamEnabled ? "ACTIVE" : "STANDBY"}
                        </span>
                    </div>
                    <div className="space-y-1 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        <div className="flex justify-between">
                            <span>Socket Port:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">{streamPort ? `${streamPort} / TCP` : "Disabled"}</span>
                        </div>
                        <div className="flex justify-between">
                            <span>Stream Mode:</span>
                            <span className="text-slate-700 dark:text-slate-300 font-semibold">Socket.IO Push</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
