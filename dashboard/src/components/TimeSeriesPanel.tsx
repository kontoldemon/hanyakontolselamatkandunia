"use client";

import { useEffect, useState } from "react";
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    LineChart, Line, ComposedChart, Legend,
} from "recharts";
import { Activity } from "lucide-react";
import CollapsiblePanel from "@/components/CollapsiblePanel";
import CustomDropdown from "@/components/CustomDropdown";

interface TimeSeriesPanelProps {
    expanded: boolean;
    onToggle: () => void;
    timelineWindow: "15m" | "1h" | "6h" | "24h" | "7d" | "all";
}

type ChartView = "volume" | "soar" | "tactics" | "mttb" | "ips" | "payload";

type TimeSeriesPoint = {
    time: number;
    timeLabel: string;
    totalEvents: number;
    blockedEvents: number;
    mttbAvg: number;
    sshCount: number;
    cmdCount: number;
    webCount: number;
    otherCount: number;
    uniqueIpCount: number;
    payloadKb: number;
};

type AnalyticsPayload = {
    ok: boolean;
    status?: "live" | "offline";
    source?: "clickhouse" | "runtime" | "memory" | "mixed";
    authoritative?: boolean;
    sampledAt?: string;
    series?: TimeSeriesPoint[];
};

const viewOptions = [
    { label: "Attack Volume", value: "volume" },
    { label: "SOAR Effectiveness", value: "soar" },
    { label: "Tactics Breakdown", value: "tactics" },
    { label: "Response Speed (MTTB)", value: "mttb" },
    { label: "Unique Attackers", value: "ips" },
    { label: "Ingress Payload", value: "payload" },
];

const timelineLabels: Record<TimeSeriesPanelProps["timelineWindow"], string> = {
    "15m": "Last 15m",
    "1h": "Last 1h",
    "6h": "Last 6h",
    "24h": "Last 24h",
    "7d": "Last 7d",
    "all": "All time",
};

export default function TimeSeriesPanel({ expanded, onToggle, timelineWindow }: TimeSeriesPanelProps) {
    const [activeView, setActiveView] = useState<ChartView>("volume");
    const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesPoint[]>([]);
    const [source, setSource] = useState<"live" | "offline">("offline");
    const [lastSync, setLastSync] = useState<string>("n/a");

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const response = await fetch(`/api/cloudsentinel/analytics?window=${timelineWindow}`, { cache: "no-store" });
                if (!response.ok) {
                    return;
                }
                const payload = (await response.json()) as AnalyticsPayload;
                if (cancelled) return;
                setSource(payload.status ?? (payload.ok ? "live" : "offline"));
                setTimeSeriesData(payload.series ?? []);
                if (payload.sampledAt) {
                    setLastSync(new Date(payload.sampledAt).toLocaleTimeString());
                }
            } catch {
                if (!cancelled) {
                    setSource("offline");
                }
            }
        };

        void load();
        const timer = window.setInterval(() => void load(), 10000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, [timelineWindow]);

    const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ color?: string; name?: string; value?: number | string }>; label?: string }) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 p-3 rounded-lg shadow-xl text-xs z-[100]">
                    <p className="font-bold mb-2 text-slate-800 dark:text-slate-200 border-b border-slate-100 dark:border-white/10 pb-1">{label}</p>
                    {payload.map((entry, index) => (
                        <div key={index} className="flex items-center justify-between gap-4 py-0.5">
                            <div className="flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                                <span className="text-slate-500">{entry.name}</span>
                            </div>
                            <span className="font-mono font-medium text-slate-800 dark:text-slate-200">{entry.value}</span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    const renderActiveChart = () => {
        if (timeSeriesData.length === 0) {
            return (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs">
                    <Activity className="mx-auto mb-2 opacity-50" size={24} />
                    Waiting for aggregated threat data...
                </div>
            );
        }

        switch (activeView) {
            case "volume":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="monotone" dataKey="totalEvents" name="Total Events" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorTotal)" />
                        </AreaChart>
                    </ResponsiveContainer>
                );
            case "soar":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend iconType="circle" wrapperStyle={{ fontSize: "10px" }} />
                            <Line type="monotone" dataKey="totalEvents" name="Detected" stroke="#f59e0b" strokeWidth={2} dot={false} />
                            <Line type="stepAfter" dataKey="blockedEvents" name="Blocked" stroke="#10b981" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                );
            case "tactics":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend iconType="circle" wrapperStyle={{ fontSize: "10px" }} />
                            <Area type="monotone" dataKey="sshCount" name="SSH Auth" stackId="1" stroke="#ef4444" fill="#ef4444" fillOpacity={0.6} />
                            <Area type="monotone" dataKey="cmdCount" name="Command Exec" stackId="1" stroke="#f97316" fill="#f97316" fillOpacity={0.6} />
                            <Area type="monotone" dataKey="webCount" name="Web Exploit" stackId="1" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.6} />
                            <Area type="monotone" dataKey="otherCount" name="Other" stackId="1" stroke="#64748b" fill="#64748b" fillOpacity={0.6} />
                        </AreaChart>
                    </ResponsiveContainer>
                );
            case "mttb":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={(val) => `${val}ms`} />
                            <Tooltip content={<CustomTooltip />} />
                            <Line type="monotone" dataKey="mttbAvg" name="MTTB (ms)" stroke="#f59e0b" strokeWidth={2} dot={{ r: 2, fill: "#f59e0b" }} activeDot={{ r: 4 }} />
                        </LineChart>
                    </ResponsiveContainer>
                );
            case "ips":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis yAxisId="left" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend iconType="circle" wrapperStyle={{ fontSize: "10px" }} />
                            <Area yAxisId="left" type="monotone" dataKey="totalEvents" name="Total Events" fill="#3b82f6" stroke="#3b82f6" fillOpacity={0.2} />
                            <Line yAxisId="right" type="monotone" dataKey="uniqueIpCount" name="Unique IPs" stroke="#a855f7" strokeWidth={2} dot={false} />
                        </ComposedChart>
                    </ResponsiveContainer>
                );
            case "payload":
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={timeSeriesData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorPayload" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                            <XAxis dataKey="timeLabel" tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={(val) => `${val}KB`} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="step" dataKey="payloadKb" name="Payload (KB)" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorPayload)" />
                        </AreaChart>
                    </ResponsiveContainer>
                );
            default:
                return null;
        }
    };

    return (
        <CollapsiblePanel
            expanded={expanded}
            onToggle={onToggle}
            icon={Activity}
            iconColor="text-blue-500"
            title="Time-Series Analytics"
            summary={`${timelineLabels[timelineWindow]} | ${source} | sync ${lastSync}`}
        >
            <div className="flex flex-col h-[280px] group-data-[fullscreen=true]/fs:h-[60vh] w-full">
                <div className="flex justify-between items-center mb-4 shrink-0">
                    <span className="text-xs text-slate-500">Server pre-aggregated window: {timelineLabels[timelineWindow]}</span>
                    <CustomDropdown
                        options={viewOptions}
                        value={activeView}
                        onChange={(val) => setActiveView(val as ChartView)}
                        className="w-[180px]"
                    />
                </div>
                <div className="flex-1 min-h-0">
                    {renderActiveChart()}
                </div>
            </div>
        </CollapsiblePanel>
    );
}
