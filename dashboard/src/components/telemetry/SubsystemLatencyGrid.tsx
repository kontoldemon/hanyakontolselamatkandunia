"use client";

import { Activity, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface SubsystemLatencyGridProps {
    latencyRows: Array<{ name: string; value: number }>;
    maxLatencyMs?: number;
    sampledAt?: string;
}

export default function SubsystemLatencyGrid({
    latencyRows,
    maxLatencyMs,
    sampledAt,
}: SubsystemLatencyGridProps) {
    const formattedSampledTime = sampledAt
        ? new Date(sampledAt).toLocaleTimeString()
        : null;

    return (
        <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
            <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015] flex items-center justify-between">
                <div>
                    <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                        <Activity size={14} className="text-blue-500" /> Admin API Endpoint Latencies
                    </h3>
                    <p className="text-[10px] font-mono text-slate-400 dark:text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock size={10} /> Dashboard to sensor round-trip{formattedSampledTime ? ` · ${formattedSampledTime}` : ""}
                    </p>
                </div>
                {typeof maxLatencyMs === "number" && (
                    <span className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-white/[0.06] text-slate-700 dark:text-slate-300 font-semibold text-[10.5px] font-mono">
                        Peak: {maxLatencyMs}ms
                    </span>
                )}
            </div>

            <div className="p-4 sm:p-5">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    {latencyRows.map((row) => {
                        const isFast = row.value > 0 && row.value < 25;
                        const isModerate = row.value >= 25 && row.value <= 50;
                        const isHigh = row.value > 50;
                        const isZero = row.value === 0;

                        return (
                            <div
                                key={row.name}
                                className="px-3.5 py-2.5 rounded-xl border border-slate-200/80 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.02] flex items-center justify-between gap-2 transition hover:border-slate-300 dark:hover:border-white/10"
                            >
                                <span className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">
                                    {row.name}
                                </span>
                                <span
                                    className={cn(
                                        "font-mono text-xs font-bold px-1.5 py-0.5 rounded shrink-0",
                                        isFast && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
                                        isModerate && "bg-amber-500/10 text-amber-600 dark:text-amber-400",
                                        isHigh && "bg-rose-500/10 text-rose-600 dark:text-rose-400",
                                        isZero && "text-slate-400 dark:text-slate-500"
                                    )}
                                >
                                    {row.value > 0 ? `${row.value}ms` : "idle"}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
