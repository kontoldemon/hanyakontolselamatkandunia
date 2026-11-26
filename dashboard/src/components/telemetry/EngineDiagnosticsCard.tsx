"use client";

import { Cpu, Gauge, Shield, Terminal, Zap } from "lucide-react";
import type { SensorOperations } from "@/lib/liveEvents";

interface EngineDiagnosticsCardProps {
    operations: SensorOperations | null;
}

export default function EngineDiagnosticsCard({ operations }: EngineDiagnosticsCardProps) {
    const metrics = (operations?.sensor?.metrics?.data ?? {}) as Record<string, unknown>;

    const mttbMs = typeof metrics.mttb_ms === "number" ? metrics.mttb_ms : 0;
    const activeSessions = typeof metrics.active_sessions === "number" ? metrics.active_sessions : 0;
    const totalConnections = typeof metrics.total_connections === "number" ? metrics.total_connections : 0;
    const totalAuthFailures = typeof metrics.total_auth_failures === "number" ? metrics.total_auth_failures : 0;
    const totalAuthSuccesses = typeof metrics.total_auth_successes === "number" ? metrics.total_auth_successes : 0;
    const totalCommands = typeof metrics.total_commands === "number" ? metrics.total_commands : 0;
    const totalBlocks = typeof metrics.total_blocks === "number" ? metrics.total_blocks : 0;
    const blockedIpsCurrent = typeof metrics.blocked_ips_current === "number" ? metrics.blocked_ips_current : 0;
    const uptimeSeconds = typeof metrics.uptime_seconds === "number" ? metrics.uptime_seconds : 0;

    const formatUptime = (sec: number) => {
        if (sec <= 0) return "Starting up";
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        if (h > 0) return `${h}h ${m}m uptime`;
        if (m > 0) return `${m}m ${s}s uptime`;
        return `${s}s uptime`;
    };

    return (
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                    <Gauge size={14} className="text-emerald-500" /> Containment Engine &amp; Performance Telemetry
                </h3>
                <span className="text-[10.5px] font-mono text-slate-500 dark:text-slate-400">
                    {formatUptime(uptimeSeconds)}
                </span>
            </div>

            <div className="p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {/* 1. MTTB Metric */}
                <div className="p-3.5 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] space-y-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Zap size={13} className="text-emerald-500" /> Mean-Time-To-Block
                        </span>
                        <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold border ${mttbMs > 0
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                            : "bg-slate-200 dark:bg-white/10 text-slate-500 dark:text-slate-400 border-slate-300/40 dark:border-white/10"}`}>
                            {mttbMs > 0 ? "MEASURED" : "IDLE"}
                        </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                        {mttbMs > 0 ? `${mttbMs.toFixed(2)}ms` : "No blocks yet"}
                    </div>
                    <p className="text-[10.5px] text-slate-500 dark:text-slate-400">
                        Sensor-side netfilter trigger latency.
                    </p>
                </div>

                {/* 2. Active Sessions & Connections */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] space-y-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Terminal size={13} className="text-blue-500" /> Active Intrusions
                        </span>
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold border border-blue-500/20">
                            LIVE
                        </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                        {activeSessions}
                        <span className="text-xs font-normal text-slate-400 ml-1.5">/ {totalConnections} total</span>
                    </div>
                    <p className="text-[10.5px] text-slate-500 dark:text-slate-400">
                        SSH clients inside honeypot shell.
                    </p>
                </div>

                {/* 3. Firewall Drops */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] space-y-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Shield size={13} className="text-rose-500" /> Active Block Rules
                        </span>
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold border border-rose-500/20">
                            ENFORCED
                        </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                        {blockedIpsCurrent}
                        <span className="text-xs font-normal text-slate-400 ml-1.5">({totalBlocks} historical)</span>
                    </div>
                    <p className="text-[10.5px] text-slate-500 dark:text-slate-400">
                        IP deny rules with auto-expiry TTL.
                    </p>
                </div>

                {/* 4. Intercepted Commands */}
                <div className="p-3.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] space-y-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Cpu size={13} className="text-purple-500" /> Commands Captured
                        </span>
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 font-bold border border-purple-500/20">
                            INTERCEPTED
                        </span>
                    </div>
                    <div className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                        {totalCommands}
                    </div>
                    <div className="flex items-center justify-between text-[10.5px] text-slate-500 dark:text-slate-400 font-mono">
                        <span>Failed Logins: {totalAuthFailures}</span>
                        <span>Accepted: {totalAuthSuccesses}</span>
                    </div>
                </div>
            </div>
        </div>
    );
}
