"use client";

import { useMemo } from "react";
import { CapturedSession } from "@/lib/liveEvents";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Timer } from "lucide-react";
import CollapsiblePanel from "@/components/CollapsiblePanel";

interface SessionDepthPanelProps {
    expanded: boolean;
    onToggle: () => void;
    sessions: CapturedSession[];
}

export default function SessionDepthPanel({ expanded, onToggle, sessions }: SessionDepthPanelProps) {
    const depthData = useMemo(() => {
        let totalDwellMs = 0;
        let validDwellCount = 0;
        let totalCommands = 0;

        const buckets = {
            instant: 0, // < 5s
            short: 0,   // 5s - 30s
            medium: 0,  // 30s - 2m
            long: 0     // > 2m
        };

        sessions.forEach(session => {
            const start = session.startedAtEpochMs || 0;
            const end = session.lastSeenEpochMs || start;
            
            // Only count sessions with a valid duration
            if (start > 0 && end >= start) {
                const durationMs = end - start;
                totalDwellMs += durationMs;
                validDwellCount++;

                if (durationMs < 5000) buckets.instant++;
                else if (durationMs < 30000) buckets.short++;
                else if (durationMs < 120000) buckets.medium++;
                else buckets.long++;
            }

            totalCommands += (session.input?.length || 0);
        });

        const avgDwellS = validDwellCount > 0 ? (totalDwellMs / validDwellCount / 1000).toFixed(1) : "0.0";
        const avgCmds = sessions.length > 0 ? (totalCommands / sessions.length).toFixed(1) : "0.0";

        const chartData = [
            { name: "< 5s", count: buckets.instant, fill: "#ef4444" },
            { name: "5s-30s", count: buckets.short, fill: "#f59e0b" },
            { name: "30s-2m", count: buckets.medium, fill: "#3b82f6" },
            { name: "> 2m", count: buckets.long, fill: "#10b981" },
        ];

        return { chartData, avgDwellS, avgCmds, validDwellCount };
    }, [sessions]);

    type SessionDepthTooltipProps = {
        active?: boolean;
        payload?: Array<{ value?: number | string }>;
        label?: string | number;
    };

    const CustomTooltip = ({ active, payload, label }: SessionDepthTooltipProps) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 p-3 rounded-lg shadow-xl text-xs z-[100]">
                    <p className="font-bold mb-1 text-slate-800 dark:text-slate-200 border-b border-slate-100 dark:border-white/10 pb-1">{String(label ?? "")} Dwell Time</p>
                    <div className="flex items-center justify-between gap-4 mt-2">
                        <span className="text-slate-500">Sessions</span>
                        <span className="font-mono font-medium text-slate-800 dark:text-slate-200">{payload[0]?.value ?? 0}</span>
                    </div>
                </div>
            );
        }
        return null;
    };

    return (
        <CollapsiblePanel
            expanded={expanded}
            onToggle={onToggle}
            icon={Timer}
            iconColor="text-orange-500"
            title="Session Depth & Dwell Time"
            summary={`Avg Dwell: ${depthData.avgDwellS}s`}
        >
            <div className="flex flex-col h-[280px] group-data-[fullscreen=true]/fs:h-[60vh] w-full">
                <div className="grid grid-cols-2 gap-4 mb-6 shrink-0">
                    <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-lg border border-slate-100 dark:border-white/5">
                        <p className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1">Average Dwell Time</p>
                        <p className="text-2xl font-bold font-mono text-slate-800 dark:text-slate-200">
                            {depthData.avgDwellS}<span className="text-sm text-slate-500 ml-1">sec</span>
                        </p>
                    </div>
                    <div className="bg-slate-50 dark:bg-white/[0.02] p-3 rounded-lg border border-slate-100 dark:border-white/5">
                        <p className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider mb-1">Avg Commands / Session</p>
                        <p className="text-2xl font-bold font-mono text-slate-800 dark:text-slate-200">
                            {depthData.avgCmds}
                        </p>
                    </div>
                </div>
                
                <div className="flex-1 min-h-0">
                    {depthData.validDwellCount === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs">
                            Waiting for completed sessions...
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={depthData.chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} />
                                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} />
                                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(148, 163, 184, 0.1)' }} />
                                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                                    {depthData.chartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.fill} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>
        </CollapsiblePanel>
    );
}
