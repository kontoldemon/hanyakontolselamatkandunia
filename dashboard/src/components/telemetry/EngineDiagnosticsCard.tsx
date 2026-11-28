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

            <div className="p-3 sm:p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                {/* 1. MTTB Metric */}
                <div className="p-3 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between gap-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Zap size={13} className="text-emerald-500" /> Mean-Time-To-Block
                        </span>
                        <span
                            title={mttbMs > 0 ? "Measured" : "Idle (no blocks yet)"}
                            aria-label={mttbMs > 0 ? "Measured" : "Idle"}
                            className={`w-2 h-2 rounded-full shrink-0 ${mttbMs > 0 ? "bg-emerald-500" : "bg-amber-500"}`}
                        />
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                            {mttbMs > 0 ? `${mttbMs.toFixed(2)}ms` : "--"}
                        </span>
                        <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
                            {mttbMs > 0 ? "netfilter" : "idle"}
                        </span>
                    </div>
                </div>

                {/* 2. Active Sessions & Connections */}
                <div className="p-3 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between gap-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Terminal size={13} className="text-blue-500" /> Active Intrusions
                        </span>
                        <span
                            title="Live"
                            aria-label="Live"
                            className={`w-2 h-2 rounded-full shrink-0 ${activeSessions > 0 ? "bg-emerald-500 animate-pulse" : "bg-emerald-500"}`}
                        />
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                            {activeSessions}
                        </span>
                        <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
                            / {totalConnections} total
                        </span>
                    </div>
                </div>

                {/* 3. Firewall Drops */}
                <div className="p-3 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between gap-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Shield size={13} className="text-rose-500" /> Active Block Rules
                        </span>
                        <span
                            title={blockedIpsCurrent > 0 ? "Enforced" : "Standby"}
                            aria-label={blockedIpsCurrent > 0 ? "Enforced" : "Standby"}
                            className={`w-2 h-2 rounded-full shrink-0 ${blockedIpsCurrent > 0 ? "bg-rose-500" : "bg-emerald-500"}`}
                        />
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                            {blockedIpsCurrent}
                        </span>
                        <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
                            / {totalBlocks} historical
                        </span>
                    </div>
                </div>

                {/* 4. Intercepted Commands */}
                <div className="p-3 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/60 dark:bg-white/[0.02] flex flex-col justify-between gap-1.5">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            <Cpu size={13} className="text-purple-500" /> Commands Captured
                        </span>
                        <span
                            title="Intercepted"
                            aria-label="Intercepted"
                            className="w-2 h-2 rounded-full shrink-0 bg-emerald-500"
                        />
                    </div>
                    <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-mono font-bold text-slate-900 dark:text-white tracking-tight">
                            {totalCommands}
                        </span>
                        <span className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
                            {totalAuthFailures} fail &middot; {totalAuthSuccesses} ok
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
