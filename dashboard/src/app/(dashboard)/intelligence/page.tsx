"use client";

import { BrainCircuit, ShieldAlert, Fingerprint, ChevronDown, ChevronUp } from "lucide-react";
import { useLiveThreatLogs, useSensorOperations, useCapturedSessions, useDashboardStats, toThreatLog, type CloudSentinelEvent, type ThreatLog } from "@/lib/liveEvents";
import { useState, useCallback, useEffect, useMemo } from "react";
import { useAgentCommand } from "@/lib/AgentContext";
import { useIntelStats } from "@/lib/intelStats";
import CustomDropdown from "@/components/CustomDropdown";
import CollapsiblePanel from "@/components/CollapsiblePanel";
import CountryStatsPanel from "@/components/CountryStatsPanel";
import TimingHeatmapPanel from "@/components/TimingHeatmapPanel";
import NetworkStatsPanel from "@/components/NetworkStatsPanel";
import RiskScorePanel from "@/components/RiskScorePanel";
import SoarBreakdownPanel from "@/components/SoarBreakdownPanel";
import KpiStrip from "@/components/KpiStrip";
import TimeSeriesPanel from "@/components/TimeSeriesPanel";
import SessionDepthPanel from "@/components/SessionDepthPanel";
import AnomalyDetectionPanel from "@/components/AnomalyDetectionPanel";

type GlobalTimeline = "15m" | "1h" | "6h" | "24h" | "7d" | "all";

const TIMELINE_OPTIONS: Array<{ label: string; value: GlobalTimeline }> = [
    { label: "Last 15m", value: "15m" },
    { label: "Last 1h", value: "1h" },
    { label: "Last 6h", value: "6h" },
    { label: "Last 24h", value: "24h" },
    { label: "Last 7d", value: "7d" },
    { label: "All time", value: "all" },
];

const TIMELINE_TO_MS: Record<Exclude<GlobalTimeline, "all">, number> = {
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
};

const TIMELINE_FETCH_LIMIT: Record<GlobalTimeline, number> = {
    "15m": 500,
    "1h": 1500,
    "6h": 5000,
    "24h": 10000,
    "7d": 20000,
    "all": 20000,
};

function toNumber(value: unknown): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function clampPercent(value: number): number {
    return Math.min(100, Math.max(0, value));
}

function normalizeRiskScore(rawRisk: number, sessionWeight: number): number {
    if (!Number.isFinite(rawRisk) || rawRisk <= 0) {
        return 0;
    }
    if (rawRisk <= 100) {
        return clampPercent(rawRisk);
    }
    return clampPercent(rawRisk / Math.max(1, sessionWeight));
}

type EventsApiResponse = {
    ok?: boolean;
    events?: CloudSentinelEvent[];
};

export default function IntelligencePage() {
    const [commandMode, setCommandMode] = useState<"most" | "least">("most");
    const [commandSearch, setCommandSearch] = useState("");
    const [commandPage, setCommandPage] = useState(1);
    const [timeline, setTimeline] = useState<GlobalTimeline>("24h");
    
    // 1. Core State
    const [hoveredAttack, setHoveredAttack] = useState<{name: string, count: number, x: number, y: number, alignRight: boolean} | null>(null);
    const [hoveredMitre, setHoveredMitre] = useState<{name: string, count: number, x: number, y: number, alignRight: boolean} | null>(null);
    const [panels, setPanels] = useState<Record<string, boolean>>({
        attackTypes: false,
        mitre: false,
        countries: false,
        timing: false,
        network: false,
        commands: false,
        passwords: false,
        fingerprints: false,
        risk: false,
        soar: false,
        timeSeries: false,
        sessionDepth: false,
        anomaly: false
    });
    const PAGE_SIZE = 10;

    const toggleAllPanels = (expand: boolean) => {
        setPanels({
            attackTypes: expand,
            mitre: expand,
            countries: expand,
            timing: expand,
            network: expand,
            commands: expand,
            passwords: expand,
            fingerprints: expand,
            risk: expand,
            soar: expand,
            timeSeries: expand,
            sessionDepth: expand,
            anomaly: expand
        });
    };

    const togglePanel = (panelId: string) => {
        setPanels((prev) => ({
            ...prev,
            [panelId]: !prev[panelId]
        }));
    };

    // ── Agent command handlers ──
    useAgentCommand("intel.sort", useCallback((v: string) => { setCommandMode(v as "most" | "least"); setCommandPage(1); }, []));
    useAgentCommand("intel.search", useCallback((v: string) => { setCommandSearch(v); setCommandPage(1); }, []));
    useAgentCommand("intel.page", useCallback((v: string) => setCommandPage(Math.max(1, parseInt(v) || 1)), []));

    const operations = useSensorOperations();
    const dashboardStats = useDashboardStats();
    const liveLogs = useLiveThreatLogs();
    const sessions = useCapturedSessions();
    const [nowMs, setNowMs] = useState(0);
    const [timelineEvents, setTimelineEvents] = useState<ThreatLog[] | null>(null);
    const windowMs = timeline === "all" ? Number.MAX_SAFE_INTEGER : TIMELINE_TO_MS[timeline];
    const cutoffMs = nowMs - windowMs;

    useEffect(() => {
        const tick = () => setNowMs(Date.now());
        tick();
        const timer = window.setInterval(tick, 5000);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        let cancelled = false;

        const loadTimelineEvents = async () => {
            try {
                const limit = TIMELINE_FETCH_LIMIT[timeline];
                const response = await fetch(`/api/cloudsentinel/events?limit=${limit}`, { cache: "no-store" });
                if (!response.ok) {
                    if (!cancelled) {
                        setTimelineEvents(null);
                    }
                    return;
                }
                const payload = (await response.json()) as EventsApiResponse;
                const mapped = (payload.events ?? []).map(toThreatLog);
                if (!cancelled) {
                    setTimelineEvents(mapped);
                }
            } catch {
                if (!cancelled) {
                    setTimelineEvents(null);
                }
            }
        };

        void loadTimelineEvents();
        const timer = window.setInterval(() => void loadTimelineEvents(), 12000);
        return () => {
            cancelled = true;
            window.clearInterval(timer);
        };
    }, [timeline]);

    const baseLogs = useMemo(() => {
        if (!timelineEvents) {
            return liveLogs;
        }
        const deduped = new Map<string, ThreatLog>();
        for (const item of [...timelineEvents, ...liveLogs]) {
            deduped.set(item.id, item);
        }
        return [...deduped.values()].sort((a, b) => b.epochMs - a.epochMs);
    }, [timelineEvents, liveLogs]);

    const filteredLiveLogs = timeline === "all"
        ? baseLogs
        : baseLogs.filter((log) => log.epochMs >= cutoffMs);
    const filteredSessions = timeline === "all"
        ? sessions
        : sessions.filter((session) => {
        const lastSeen = session.lastSeenEpochMs ??
            session.firstSeenEpochMs ??
            session.startedAtEpochMs ??
            Date.parse(session.startTime);
        return Number.isFinite(lastSeen) && lastSeen >= cutoffMs;
    });

    const stats = useIntelStats(filteredLiveLogs, filteredSessions, windowMs);
    
    const attackTypeMap = new Map<string, { name: string; value: number; fill: string }>();
    const attackMeta: Record<string, { name: string; fill: string }> = {
        SSH_AUTH_FAIL: { name: "Auth Fail", fill: "#ef4444" },
        COMMAND_EXEC: { name: "Command Exec", fill: "#f59e0b" },
        HONEYPOT_RESPONSE: { name: "Honeypot Response", fill: "#3b82f6" },
    };
    for (const log of filteredLiveLogs) {
        const meta = attackMeta[log.type] ?? { name: log.type || "Other", fill: "#64748b" };
        const bucket = attackTypeMap.get(meta.name) ?? { name: meta.name, value: 0, fill: meta.fill };
        bucket.value += 1;
        attackTypeMap.set(meta.name, bucket);
    }
    const attackTypes = [...attackTypeMap.values()].sort((a, b) => b.value - a.value);
    const totalAttacks = attackTypes.reduce((acc, item) => acc + Number(item.value || 0), 0);

    const mitreCounts = new Map<string, number>();
    for (const session of filteredSessions) {
        for (const tech of session.mitreTechniques ?? []) {
            mitreCounts.set(tech, (mitreCounts.get(tech) ?? 0) + 1);
        }
    }
    for (const log of filteredLiveLogs) {
        for (const tech of log.mitreTechniques ?? []) {
            mitreCounts.set(tech, (mitreCounts.get(tech) ?? 0) + 1);
        }
    }
    const mitreData = [...mitreCounts.entries()]
        .map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 14);

    const fingerprintsMap = new Map<string, { hash: string; client: string; count: number }>();
    for (const session of filteredSessions) {
        const hash = (session.fingerprint ?? "").trim();
        if (!hash) continue;
        const current = fingerprintsMap.get(hash) ?? { hash, client: session.client || "unknown", count: 0 };
        current.count += session.sessionCount ?? 1;
        if (!current.client || current.client === "unknown") current.client = session.client || "unknown";
        fingerprintsMap.set(hash, current);
    }
    for (const log of filteredLiveLogs) {
        const hash = (log.hassh ?? "").trim();
        if (!hash) continue;
        const current = fingerprintsMap.get(hash) ?? { hash, client: "unknown", count: 0 };
        current.count += 1;
        fingerprintsMap.set(hash, current);
    }
    const fingerprints = [...fingerprintsMap.values()].sort((a, b) => b.count - a.count).slice(0, 20);

    const commandCounts = new Map<string, number>();
    const incrementCommand = (raw: string) => {
        const cmd = raw.trim();
        if (!cmd || cmd.startsWith("cloudsentinel.") || cmd.includes("[redacted]")) return;
        commandCounts.set(cmd, (commandCounts.get(cmd) ?? 0) + 1);
    };
    for (const session of filteredSessions) {
        for (const cmd of session.input ?? []) incrementCommand(cmd);
    }
    for (const log of filteredLiveLogs) {
        if (log.role === "attacker") incrementCommand(log.payload ?? "");
    }
    const topCommands = [...commandCounts.entries()]
        .map(([command, count]) => ({ command, count }))
        .sort((a, b) => (b.count - a.count) || a.command.localeCompare(b.command));
    const leastCommands = [...commandCounts.entries()]
        .map(([command, count]) => ({ command, count }))
        .sort((a, b) => (a.count - b.count) || a.command.localeCompare(b.command));
    const uniqueCommandCount = commandCounts.size;
    const passwordCounts = new Map<string, number>();
    for (const log of filteredLiveLogs) {
        const payload = String(log.payload || "").trim();
        if (!payload.toLowerCase().startsWith("[auth]")) continue;
        const match = payload.match(/\/\s*([^\s]+)\s*(?:attempt\s+\d+)?$/i);
        if (!match) continue;
        const word = match[1]?.trim();
        if (!word || word.toLowerCase() === "unknown") continue;
        passwordCounts.set(word, (passwordCounts.get(word) ?? 0) + 1);
    }
    const passwordWords = [...passwordCounts.entries()]
        .map(([word, count]) => ({ word, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 60);
    const maxPasswordCount = Math.max(1, ...passwordWords.map((item) => item.count));

    const sourceCommands = commandMode === "most" ? topCommands : leastCommands;
    const commandQuery = commandSearch.trim().toLowerCase();
    const commandRows = sourceCommands.filter((item) => {
        if (!commandQuery) return true;
        return item.command.toLowerCase().includes(commandQuery);
    });
    const commandTotalPages = Math.max(1, Math.ceil(commandRows.length / PAGE_SIZE));
    const commandCurrentPage = Math.min(commandPage, commandTotalPages);
    const pagedCommands = commandRows.slice((commandCurrentPage - 1) * PAGE_SIZE, commandCurrentPage * PAGE_SIZE);
    const pageNumbers = Array.from({ length: commandTotalPages }, (_, index) => index + 1);

    const isAllExpanded = Object.values(panels).every(Boolean);
    const sensorMetrics = operations?.sensor.metrics.data as Record<string, unknown> | null;
    const sensorSessions = operations?.sensor.sessions.data?.sessions ?? [];

    const kpiValues = (() => {
        if (timeline !== "all") {
            return {
                // Session rows represent grouped actors, not discrete events.
                // Total Events in non-all windows should come from event stream only.
                totalEvents: filteredLiveLogs.length,
                uniqueIps: stats.uniqueIps,
                totalCountries: stats.totalCountries,
                uniqueCommands: uniqueCommandCount,
                avgRisk: clampPercent(stats.risk.avg),
                blockRate: clampPercent(stats.soar.blockRate),
            };
        }

        const totalConnections = toNumber(dashboardStats.totalConnections ?? sensorMetrics?.total_connections);
        const totalAuthFailures = toNumber(dashboardStats.totalAuthFailures ?? sensorMetrics?.total_auth_failures);
        const totalCommands = toNumber(dashboardStats.totalCommands ?? sensorMetrics?.total_commands);
        const totalBlocks = toNumber(dashboardStats.totalBlocks ?? sensorMetrics?.total_blocks);
        const totalEvents = toNumber(dashboardStats.totalEvents ?? Math.round(totalConnections + totalAuthFailures + totalCommands));
        const uniqueIpsFromTruth = toNumber(dashboardStats.uniqueIps ?? 0);
        const uniqueCountriesFromTruth = toNumber(dashboardStats.uniqueCountries ?? 0);
        const uniqueCommandsFromTruth = toNumber(dashboardStats.uniqueCommands ?? uniqueCommandCount);
        const avgRiskFromTruth = toNumber(dashboardStats.avgRisk ?? 0);
        const blockRateFromTruth = toNumber(dashboardStats.blockRate ?? 0);

        const ipSet = new Set<string>();
        const countrySet = new Set<string>();
        let riskWeightedSum = 0;
        let riskWeight = 0;
        let blockedSessionWeight = 0;
        let totalSessionWeight = 0;

        for (const session of sensorSessions) {
            if (session.ip) ipSet.add(session.ip);
            const countryKey = (session.countryCode || session.country || "").trim();
            if (countryKey) countrySet.add(countryKey);
            const sessionWeight = Math.max(1, session.sessionCount ?? 1);
            totalSessionWeight += sessionWeight;
            if (typeof session.riskScore === "number" && session.riskScore > 0) {
                riskWeightedSum += normalizeRiskScore(session.riskScore, sessionWeight) * sessionWeight;
                riskWeight += sessionWeight;
            }
            const action = (session.soarAction ?? "").trim().toLowerCase();
            if (
                session.blockEffective ||
                action === "iptables_block" ||
                action === "already_blocked"
            ) {
                blockedSessionWeight += sessionWeight;
            }
        }

        const avgRiskRaw = riskWeight > 0 ? (riskWeightedSum / riskWeight) : 0;
        const avgRisk = clampPercent(avgRiskRaw);
        const blockRateFromSessions = totalSessionWeight > 0
            ? Math.round((blockedSessionWeight / totalSessionWeight) * 100)
            : 0;
        const blockRateFallback = totalConnections > 0
            ? Math.round((totalBlocks / totalConnections) * 100)
            : 0;
        const blockRate = clampPercent(blockRateFromTruth || blockRateFromSessions || blockRateFallback);
        const effectiveAvgRisk = clampPercent(avgRiskFromTruth || avgRisk);

        return {
            totalEvents,
            uniqueIps: uniqueIpsFromTruth || ipSet.size || stats.uniqueIps,
            totalCountries: uniqueCountriesFromTruth || countrySet.size || stats.totalCountries,
            uniqueCommands: uniqueCommandsFromTruth || uniqueCommandCount,
            avgRisk: effectiveAvgRisk,
            blockRate,
        };
    })();

    return (
        <div className="h-full flex flex-col gap-4 overflow-hidden">
            <div className="flex justify-between items-center shrink-0">
                <div>
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">Threat Intelligence</h2>
                    <p className="text-slate-500 text-xs mt-0.5">Advanced TTP Analytics & Fingerprinting</p>
                </div>
                <div className="flex items-center gap-2">
                    <CustomDropdown
                        options={TIMELINE_OPTIONS}
                        value={timeline}
                        onChange={(value) => setTimeline(value as GlobalTimeline)}
                        className="w-28"
                    />
                    <button
                        onClick={() => toggleAllPanels(!isAllExpanded)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/10 rounded-lg text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 transition-colors shadow-sm"
                    >
                        {isAllExpanded ? (
                            <><ChevronUp size={14} /> Collapse All</>
                        ) : (
                            <><ChevronDown size={14} /> Expand All</>
                        )}
                    </button>
                </div>
            </div>

            <KpiStrip 
                totalEvents={kpiValues.totalEvents}
                uniqueIps={kpiValues.uniqueIps}
                totalCountries={kpiValues.totalCountries}
                uniqueCommands={kpiValues.uniqueCommands}
                avgRisk={kpiValues.avgRisk}
                blockRate={kpiValues.blockRate}
            />

            <div className="flex-1 overflow-y-auto terminal-scrollbar min-h-0 pb-6 pr-2 space-y-4">
                
                {/* Row 1: Top Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <CollapsiblePanel
                        expanded={panels.attackTypes}
                        onToggle={() => togglePanel("attackTypes")}
                        icon={ShieldAlert}
                        iconColor="text-red-500"
                        title="Attack Types Distribution"
                        summary={`${totalAttacks} Events`}
                    >
                        <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full flex flex-col items-center justify-center gap-4 relative" onMouseLeave={() => setHoveredAttack(null)}>
                            <div className="relative h-32 w-32 group-data-[fullscreen=true]/fs:h-64 group-data-[fullscreen=true]/fs:w-64 transition-all duration-300 shrink-0">
                                <svg viewBox="-1 -1 2 2" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
                                    {totalAttacks > 0 ? (() => {
                                        let cumulativePercent = 0;
                                        return attackTypes.map((item) => {
                                            const slicePercent = Number(item.value || 0) / totalAttacks;
                                            if (slicePercent === 0) return null;
                                            const handleMouseMove = (e: React.MouseEvent) => {
                                                setHoveredAttack({ 
                                                    name: item.name, 
                                                    count: Number(item.value), 
                                                    x: e.clientX, 
                                                    y: e.clientY,
                                                    alignRight: e.clientX > window.innerWidth / 2 
                                                });
                                            };
                                            if (slicePercent === 1) {
                                                return <circle key={item.name} r="1" cx="0" cy="0" fill={item.fill} onMouseMove={handleMouseMove} className="hover:opacity-80 transition-opacity cursor-crosshair" />;
                                            }
                                            const startX = Math.cos(2 * Math.PI * cumulativePercent);
                                            const startY = Math.sin(2 * Math.PI * cumulativePercent);
                                            cumulativePercent += slicePercent;
                                            const endX = Math.cos(2 * Math.PI * cumulativePercent);
                                            const endY = Math.sin(2 * Math.PI * cumulativePercent);
                                            const largeArcFlag = slicePercent > 0.5 ? 1 : 0;
                                            const pathData = `M ${startX} ${startY} A 1 1 0 ${largeArcFlag} 1 ${endX} ${endY} L 0 0`;
                                            return <path key={item.name} d={pathData} fill={item.fill} className="hover:opacity-80 transition-opacity cursor-crosshair" onMouseMove={handleMouseMove} />;
                                        });
                                    })() : <circle r="1" cx="0" cy="0" fill="#334155" />}
                                </svg>
                                <div className="absolute inset-[24%] rounded-full bg-white dark:bg-[#0a0a0a] flex flex-col items-center justify-center pointer-events-none transition-all duration-300">
                                    <span className="text-xl group-data-[fullscreen=true]/fs:text-4xl font-bold text-slate-900 dark:text-white leading-none transition-all duration-300">{totalAttacks}</span>
                                </div>
                            </div>
                            <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
                                {attackTypes.map((item) => (
                                    <div key={item.name} className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                                        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: item.fill }} />
                                        <span>{item.name}</span>
                                    </div>
                                ))}
                            </div>
                            {hoveredAttack && (
                                <div 
                                    className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
                                    style={{ 
                                        left: hoveredAttack.alignRight ? undefined : hoveredAttack.x + 15,
                                        right: hoveredAttack.alignRight ? (window.innerWidth - hoveredAttack.x + 15) : undefined,
                                        top: hoveredAttack.y + 15 
                                    }}
                                >
                                    <span className="text-slate-400 font-medium">{hoveredAttack.name}</span>
                                    <span className="font-bold text-red-400">{hoveredAttack.count} Attacks</span>
                                </div>
                            )}
                        </div>
                    </CollapsiblePanel>

                    <CollapsiblePanel
                        expanded={panels.mitre}
                        onToggle={() => togglePanel("mitre")}
                        icon={BrainCircuit}
                        iconColor="text-blue-500"
                        title="MITRE ATT&CK Mapping"
                        summary={`${mitreData.length} Techniques Mapped`}
                    >
                        <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full space-y-3 overflow-y-auto pr-2 terminal-scrollbar relative" onMouseLeave={() => setHoveredMitre(null)}>
                            {mitreData.length === 0 ? (
                                <div className="text-xs text-slate-500 text-center h-full flex items-center justify-center">No MITRE techniques in selected window.</div>
                            ) : mitreData.map((item) => {
                                const width = `${Math.round((item.count / Math.max(1, mitreData.length)) * 100)}%`;
                                return (
                                    <div 
                                        key={item.name} 
                                        className="grid grid-cols-[100px_1fr_30px] items-center gap-2 text-xs hover:bg-slate-50 dark:hover:bg-white/5 p-1 rounded-sm cursor-crosshair transition-colors"
                                        onMouseMove={(e) => {
                                            setHoveredMitre({ 
                                                name: item.name, 
                                                count: item.count, 
                                                x: e.clientX, 
                                                y: e.clientY,
                                                alignRight: e.clientX > window.innerWidth / 2
                                            });
                                        }}
                                    >
                                        <span className="text-[10px] text-slate-500 truncate">{item.name}</span>
                                        <div className="h-2 rounded bg-slate-100 dark:bg-white/10 overflow-hidden pointer-events-none">
                                            <div className="h-full rounded bg-blue-500" style={{ width }} />
                                        </div>
                                        <span className="font-mono text-[10px] text-slate-700 dark:text-slate-300 text-right pointer-events-none">{item.count}</span>
                                    </div>
                                );
                            })}
                            {hoveredMitre && (
                                <div 
                                    className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
                                    style={{ 
                                        left: hoveredMitre.alignRight ? undefined : hoveredMitre.x + 15,
                                        right: hoveredMitre.alignRight ? (window.innerWidth - hoveredMitre.x + 15) : undefined,
                                        top: hoveredMitre.y + 15 
                                    }}
                                >
                                    <span className="text-slate-400 font-medium">{hoveredMitre.name}</span>
                                    <span className="font-bold text-blue-400">{hoveredMitre.count} Hits</span>
                                </div>
                            )}
                        </div>
                    </CollapsiblePanel>
                </div>

                {/* Row 2: NEW Analytics */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <CountryStatsPanel expanded={panels.countries} onToggle={() => togglePanel("countries")} countries={stats.countries} />
                    <TimingHeatmapPanel expanded={panels.timing} onToggle={() => togglePanel("timing")} heatmap={stats.heatmap} />
                </div>

                {/* Row 3: Network + Fingerprints */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <NetworkStatsPanel expanded={panels.network} onToggle={() => togglePanel("network")} isps={stats.isps} />
                    <CollapsiblePanel
                        expanded={panels.fingerprints}
                        onToggle={() => togglePanel("fingerprints")}
                        icon={Fingerprint}
                        iconColor="text-purple-500"
                        title="HASSH Fingerprints"
                        summary={`${fingerprints.length} Signatures`}
                    >
                        <div className="h-[300px] overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md">
                            <table className="w-full text-left">
                                <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
                                    <tr>
                                        <th className="px-4 py-2 font-medium">Hash</th>
                                        <th className="px-4 py-2 font-medium">Client Info</th>
                                        <th className="px-4 py-2 font-medium w-16 text-right">Count</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                                    {fingerprints.length === 0 ? (
                                        <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No fingerprints captured.</td></tr>
                                    ) : fingerprints.map((item) => (
                                        <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={item.hash}>
                                            <td className="px-4 py-2 font-mono text-[10px] text-slate-500">{item.hash}</td>
                                            <td className="px-4 py-2 text-blue-500 font-mono text-[10px] truncate max-w-[120px]" title={item.client}>{item.client}</td>
                                            <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CollapsiblePanel>
                </div>

                {/* Row 4: Tables */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <CollapsiblePanel
                        expanded={panels.commands}
                        onToggle={() => togglePanel("commands")}
                        icon={ShieldAlert}
                        iconColor="text-amber-500"
                        title="Attacker Commands"
                        summary={`${uniqueCommandCount} Unique`}
                    >
                        <div className="flex flex-col h-[300px]">
                            <div className="flex gap-2 items-center mb-3">
                                <CustomDropdown
                                    options={[{ label: "Most Used", value: "most" }, { label: "Least Used", value: "least" }]}
                                    value={commandMode}
                                    onChange={(val) => { setCommandMode(val as "most" | "least"); setCommandPage(1); }}
                                    className="w-28 shrink-0"
                                />
                                <input type="text" value={commandSearch} onChange={(e) => { setCommandSearch(e.target.value); setCommandPage(1); }} placeholder="Search..." className="w-full bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                            </div>
                            <div className="flex-1 overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md">
                                <table className="w-full text-left">
                                    <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
                                        <tr>
                                            <th className="px-4 py-2 font-medium w-12">No.</th>
                                            <th className="px-4 py-2 font-medium">Command</th>
                                            <th className="px-4 py-2 font-medium w-16 text-right">Freq</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                                        {pagedCommands.length === 0 ? (
                                            <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No commands yet.</td></tr>
                                        ) : pagedCommands.map((item, index) => (
                                            <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={`${commandMode}-${item.command}`}>
                                                <td className="px-4 py-2 text-slate-400 font-mono">{(commandCurrentPage - 1) * PAGE_SIZE + index + 1}</td>
                                                <td className="px-4 py-2 text-slate-700 dark:text-slate-300 font-mono break-all leading-tight">{item.command}</td>
                                                <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <div className="mt-3 flex items-center justify-between">
                                <span className="text-[10px] text-slate-500">Page {commandCurrentPage} of {commandTotalPages}</span>
                                <div className="flex gap-1">
                                    {pageNumbers.map(page => (
                                        <button key={page} onClick={() => setCommandPage(page)} className={`w-5 h-5 rounded text-[10px] font-medium ${page === commandCurrentPage ? "bg-blue-600 text-white" : "bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 text-slate-500"}`}>{page}</button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </CollapsiblePanel>

                    <CollapsiblePanel
                        expanded={panels.passwords}
                        onToggle={() => togglePanel("passwords")}
                        icon={ShieldAlert}
                        iconColor="text-fuchsia-500"
                        title="Password Word Cloud"
                        summary={`${passwordWords.length} Tokens`}
                    >
                        <div className="h-[300px] overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md p-3">
                            {passwordWords.length === 0 ? (
                                <div className="text-xs text-slate-500 text-center h-full flex items-center justify-center">
                                    No captured password words in selected window.
                                </div>
                            ) : (
                                <div className="flex flex-wrap gap-2 items-center">
                                    {passwordWords.map((item) => {
                                        const scale = item.count / maxPasswordCount;
                                        const fontSize = Math.round(12 + scale * 20);
                                        const opacity = 0.55 + scale * 0.45;
                                        return (
                                            <span
                                                key={item.word}
                                                title={`${item.word} (${item.count})`}
                                                className="font-mono leading-none px-2 py-1 rounded border border-fuchsia-500/20 bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300"
                                                style={{ fontSize: `${fontSize}px`, opacity }}
                                            >
                                                {item.word}
                                            </span>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </CollapsiblePanel>
                </div>

                {/* Row 5: NEW Deep Analytics */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <RiskScorePanel expanded={panels.risk} onToggle={() => togglePanel("risk")} risk={stats.risk} />
                    <SoarBreakdownPanel expanded={panels.soar} onToggle={() => togglePanel("soar")} soar={stats.soar} />
                </div>

                {/* Row 6: Advanced Time-Series Analytics */}
                <div className="grid grid-cols-1 gap-4 items-start">
                    <TimeSeriesPanel 
                        expanded={panels.timeSeries} 
                        onToggle={() => togglePanel("timeSeries")}
                        timelineWindow={timeline}
                    />
                </div>

                {/* Row 7: Behavioral & Anomaly Analytics */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                    <SessionDepthPanel 
                        expanded={panels.sessionDepth} 
                        onToggle={() => togglePanel("sessionDepth")} 
                        sessions={filteredSessions} 
                    />
                    <AnomalyDetectionPanel 
                        expanded={panels.anomaly} 
                        onToggle={() => togglePanel("anomaly")} 
                        logs={filteredLiveLogs} 
                    />
                </div>
            </div>
        </div>
    );
}
