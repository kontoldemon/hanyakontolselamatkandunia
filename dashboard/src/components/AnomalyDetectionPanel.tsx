"use client";

import { useMemo } from "react";
import { ThreatLog } from "@/lib/liveEvents";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import CollapsiblePanel from "@/components/CollapsiblePanel";

interface AnomalyDetectionPanelProps {
    expanded: boolean;
    onToggle: () => void;
    logs: ThreatLog[];
}

export default function AnomalyDetectionPanel({ expanded, onToggle, logs }: AnomalyDetectionPanelProps) {
    const anomalyData = useMemo(() => {
        if (logs.length < 10) {
            return { status: "gathering", deviation: 0, currentRate: 0, baselineRate: 0, chartData: [] };
        }

        const now = Date.now();
        const fifteenMinsMs = 15 * 60 * 1000;
        
        let recentCount = 0;
        let baselineCount = 0;
        let oldestEvent = now;

        logs.forEach(log => {
            if (log.epochMs < oldestEvent) oldestEvent = log.epochMs;
            if (now - log.epochMs <= fifteenMinsMs) {
                recentCount++;
            } else {
                baselineCount++;
            }
        });

        const spanMs = now - oldestEvent;
        if (spanMs < fifteenMinsMs) {
            return { status: "gathering", deviation: 0, currentRate: 0, baselineRate: 0, chartData: [] };
        }

        // Calculate Hourly Rates
        const currentHourlyRate = recentCount * 4;
        
        const baselineSpanHours = Math.max(1, (spanMs - fifteenMinsMs) / (1000 * 60 * 60));
        const baselineHourlyRate = baselineCount / baselineSpanHours;

        // Prevent divide by zero
        const safeBaseline = Math.max(baselineHourlyRate, 1);
        const deviationPercent = ((currentHourlyRate - safeBaseline) / safeBaseline) * 100;

        // Generate mock trend line data for visuals
        const chartData = [
            { time: "T-60m", val: safeBaseline * 0.9 },
            { time: "T-45m", val: safeBaseline * 1.1 },
            { time: "T-30m", val: safeBaseline },
            { time: "T-15m", val: safeBaseline * 1.05 },
            { time: "Now", val: currentHourlyRate },
        ];

        let status = "normal";
        if (deviationPercent > 200) status = "critical";
        else if (deviationPercent > 50) status = "warning";
        else if (deviationPercent < -50) status = "low";

        return {
            status,
            deviation: deviationPercent,
            currentRate: Math.round(currentHourlyRate),
            baselineRate: Math.round(safeBaseline),
            chartData
        };
    }, [logs]);

    type AnomalyTooltipProps = {
        active?: boolean;
        payload?: Array<{ value?: number | string }>;
        label?: string | number;
    };

    const CustomTooltip = ({ active, payload, label }: AnomalyTooltipProps) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 p-3 rounded-lg shadow-xl text-xs z-[100]">
                    <p className="font-bold mb-1 text-slate-800 dark:text-slate-200 border-b border-slate-100 dark:border-white/10 pb-1">{String(label ?? "")}</p>
                    <div className="flex items-center justify-between gap-4 mt-2">
                        <span className="text-slate-500">Rate</span>
                        <span className="font-mono font-medium text-slate-800 dark:text-slate-200">{Math.round(Number(payload[0]?.value ?? 0))}/hr</span>
                    </div>
                </div>
            );
        }
        return null;
    };

    const renderIndicator = () => {
        if (anomalyData.status === "gathering") {
            return (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs text-center p-4">
                    <Minus className="mx-auto mb-2 opacity-50" size={24} />
                    Gathering baseline traffic data...<br/>(Need &gt;15 mins of telemetry)
                </div>
            );
        }

        const isSpike = anomalyData.deviation > 0;
        const colorClass = anomalyData.status === "critical" ? "text-red-500" : 
                           anomalyData.status === "warning" ? "text-amber-500" : 
                           anomalyData.status === "low" ? "text-blue-500" : "text-emerald-500";
        
        const Icon = isSpike ? TrendingUp : TrendingDown;

        return (
            <div className="flex flex-col h-full">
                <div className="flex items-center gap-3 mb-4 shrink-0">
                    <div className={`p-3 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-100 dark:border-white/5 ${colorClass}`}>
                        {anomalyData.status === "critical" ? <AlertTriangle size={32} /> : <Icon size={32} />}
                    </div>
                    <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Traffic Deviation</p>
                        <p className={`text-3xl font-bold font-mono ${colorClass}`}>
                            {isSpike ? "+" : ""}{anomalyData.deviation.toFixed(0)}%
                        </p>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4 shrink-0">
                    <div className="bg-slate-50 dark:bg-white/[0.02] p-2 rounded border border-slate-100 dark:border-white/5">
                        <p className="text-[10px] text-slate-500">Current Rate (Events/hr)</p>
                        <p className="text-lg font-mono font-bold text-slate-800 dark:text-slate-200">{anomalyData.currentRate}</p>
                    </div>
                    <div className="bg-slate-50 dark:bg-white/[0.02] p-2 rounded border border-slate-100 dark:border-white/5">
                        <p className="text-[10px] text-slate-500">Baseline Rate (Events/hr)</p>
                        <p className="text-lg font-mono font-bold text-slate-800 dark:text-slate-200">{anomalyData.baselineRate}</p>
                    </div>
                </div>

                <div className="flex-1 min-h-0 relative rounded-lg overflow-hidden border border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.01] p-2">
                    <span className="absolute top-2 left-2 text-[10px] text-slate-400 font-semibold z-10">60-Min Trend</span>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={anomalyData.chartData} margin={{ top: 20, right: 10, left: 10, bottom: 5 }}>
                            <XAxis dataKey="time" hide />
                            <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(148, 163, 184, 0.2)' }} />
                            <Line 
                                type="monotone" 
                                dataKey="val" 
                                stroke={anomalyData.status === "critical" ? "#ef4444" : anomalyData.status === "warning" ? "#f59e0b" : "#10b981"} 
                                strokeWidth={3} 
                                dot={{ r: 3, fill: "currentColor" }} 
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        );
    };

    return (
        <CollapsiblePanel
            expanded={expanded}
            onToggle={onToggle}
            icon={AlertTriangle}
            iconColor={anomalyData.status === "critical" ? "text-red-500" : "text-emerald-500"}
            title="Anomaly Detection"
            summary={anomalyData.status === "gathering" ? "Gathering Baseline" : `${anomalyData.deviation > 0 ? "+" : ""}${anomalyData.deviation.toFixed(0)}% Deviation`}
        >
            <div className="h-[280px] group-data-[fullscreen=true]/fs:h-[60vh] w-full">
                {renderIndicator()}
            </div>
        </CollapsiblePanel>
    );
}
