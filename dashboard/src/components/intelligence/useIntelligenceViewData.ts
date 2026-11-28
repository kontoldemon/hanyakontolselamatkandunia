"use client";

import { useEffect, useMemo, useState } from "react";
import {
    toThreatLog,
    useCapturedSessions,
    useDashboardStats,
    useLiveThreatLogs,
    useSensorOperations,
    type CloudSentinelEvent,
    type ThreatLog,
} from "@/lib/liveEvents";
import { useIntelStats } from "@/lib/intelStats";

export type GlobalTimeline = "15m" | "1h" | "6h" | "24h" | "7d" | "all";

export const TIMELINE_OPTIONS: Array<{ label: string; value: GlobalTimeline }> = [
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

// Cap raw-event pulls; long windows are aggregated by the truth/analytics endpoints.
const TIMELINE_FETCH_LIMIT: Record<GlobalTimeline, number> = {
    "15m": 500,
    "1h": 1000,
    "6h": 2000,
    "24h": 3000,
    "7d": 5000,
    "all": 5000,
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

const PAGE_SIZE = 10;

export function useIntelligenceViewData(params: {
    timeline: GlobalTimeline;
    commandMode: "most" | "least";
    commandSearch: string;
    commandPage: number;
}) {
    const { timeline, commandMode, commandSearch, commandPage } = params;
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
        .sort((a, b) => b.count - a.count);

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
    const fingerprints = [...fingerprintsMap.values()].sort((a, b) => b.count - a.count);

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
        .sort((a, b) => b.count - a.count);
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

    const sensorMetrics = operations?.sensor.metrics.data as Record<string, unknown> | null;
    const sensorSessions = operations?.sensor.sessions.data?.sessions ?? [];

    const kpiValues = (() => {
        if (timeline !== "all") {
            return {
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
              action === "already_blocked" ||
              action === "eventgrid_published" ||
              action === "event_published"
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

        return {
            totalEvents,
            uniqueIps: uniqueIpsFromTruth || ipSet.size || stats.uniqueIps,
            totalCountries: uniqueCountriesFromTruth || countrySet.size || stats.totalCountries,
            uniqueCommands: uniqueCommandsFromTruth || uniqueCommandCount,
            avgRisk: clampPercent(avgRiskFromTruth || avgRisk),
            blockRate: clampPercent(blockRateFromTruth || blockRateFromSessions || blockRateFallback),
        };
    })();

    return {
        stats,
        filteredLiveLogs,
        filteredSessions,
        attackTypes,
        totalAttacks,
        mitreData,
        fingerprints,
        pagedCommands,
        uniqueCommandCount,
        commandCurrentPage,
        commandTotalPages,
        pageSize: PAGE_SIZE,
        pageNumbers,
        passwordWords,
        maxPasswordCount,
        kpiValues,
    };
}
