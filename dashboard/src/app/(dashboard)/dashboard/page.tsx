"use client";

import { Activity, Globe, Download } from "lucide-react";
import ThreatMap from "@/components/ThreatMap";
import AttackLog from "@/components/AttackLog";
import { useDashboardStats, useLiveThreatLogs, useSensorOperations, useCapturedSessions, useWarRoomState } from "@/lib/liveEvents";
import { useMemo, useState, useEffect, useCallback } from "react";

const LIVE_ACTIVITY_WINDOW_MS = 90 * 1000;
const ONLINE_GRACE_MS = 25 * 1000;
const UNDER_ATTACK_COOLDOWN_MS = 90 * 1000;

export default function Dashboard() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

  const stats = useDashboardStats();
  const threatLogs = useLiveThreatLogs();
  const operations = useSensorOperations();
  const sessions = useCapturedSessions();
  const warRoom = useWarRoomState();
  const liveConnectionCount = stats.activeSessions;
  const [now, setNow] = useState<number>(0);

  useEffect(() => {
    const t = setTimeout(() => setNow(Date.now()), 0);
    const interval = setInterval(() => setNow(Date.now()), 5000);
    return () => {
      clearTimeout(t);
      clearInterval(interval);
    };
  }, []);

  const combinedLogs = useMemo(() => {
    if (now <= 0) {
      return [];
    }
    const currentEpochMs = now;
    const windowFloor = currentEpochMs - LIVE_ACTIVITY_WINDOW_MS;
    const activeIps = new Set(sessions.filter(s => s.status === "Active").map(s => s.ip));
    const knownSessionIps = new Set(sessions.map((s) => s.ip));
    
    // Keep only recent logs for active IPs, plus very recent unseen IPs.
    const filteredThreatLogs = threatLogs.filter(
      (log) => {
        if (log.epochMs < windowFloor) {
          return false;
        }
        const payload = (log.payload || "").toLowerCase();
        const isRelevantInfoEvent =
          payload.startsWith("cloudsentinel.session.connect") ||
          payload.startsWith("cloudsentinel.session.closed") ||
          payload.startsWith("cloudsentinel.client.version") ||
          payload === "auth-attempt" ||
          log.type === "SSH_AUTH_FAIL" ||
          log.type === "COMMAND_EXEC" ||
          log.type === "HASSH_DNA";
        if (activeIps.has(log.ip)) {
          return true;
        }
        return !knownSessionIps.has(log.ip) || isRelevantInfoEvent;
      }
    );
    
    const combined = [...filteredThreatLogs];
    const existingIps = new Set(combined.map((log) => log.ip));

    for (const s of sessions) {
      if (s.status === "Active" && !existingIps.has(s.ip)) {
        combined.push({
          id: s.id,
          timestamp: s.startTime,
          epochMs: s.startedAtEpochMs ?? 0,
          ip: s.ip,
          country: s.country,
          countryName: s.countryName,
          asn: s.asn,
          isp: s.isp,
          org: s.org,
          services: s.services,
          region: s.region,
          city: s.city,
          latitude: s.latitude ? parseFloat(s.latitude) : undefined,
          longitude: s.longitude ? parseFloat(s.longitude) : undefined,
          timezone: s.timezone,
          type: "SENSOR_EVENT",
          payload: "Active Connection",
          mitreId: s.mitreTechniques?.[0] ?? "",
          action: "Active",
          timeToBlock: null,
          hassh: s.fingerprint,
          client: s.client,
          mitreTechniques: s.mitreTechniques,
        });
      }
    }
    return combined.sort((a, b) => b.epochMs - a.epochMs);
  }, [threatLogs, sessions, now]);

  const hasRecentThreatActivity = now > 0 && combinedLogs.some((log) => {
    if (log.epochMs < now - LIVE_ACTIVITY_WINDOW_MS) {
      return false;
    }
    // Ignore non-attack noise that can create fake "under attack" state.
    if (log.type === "SENSOR_EVENT") {
      const payload = (log.payload || "").toLowerCase();
      if (
        payload.startsWith("cloudsentinel.session.connect") ||
        payload.startsWith("cloudsentinel.session.closed") ||
        payload.startsWith("cloudsentinel.client.version") ||
        payload.startsWith("cloudsentinel.event")
      ) {
        return false;
      }
    }
    return log.type === "SSH_AUTH_FAIL" || log.type === "COMMAND_EXEC" || log.type === "HASSH_DNA";
  });
  const bridgeLive = operations?.source === "live";
  const summaryLive = stats.source === "live";
  const rawOnlineSignal = summaryLive || bridgeLive;
  const rawAttackSignal = stats.attackActive || liveConnectionCount > 0 || hasRecentThreatActivity;
  const hasRecentConnectivityEvidence = now > 0 && (
    threatLogs.some((log) => log.epochMs >= now - ONLINE_GRACE_MS) ||
    sessions.some((session) => {
      const lastSeen =
        session.lastSeenEpochMs ??
        session.firstSeenEpochMs ??
        session.startedAtEpochMs ??
        0;
      return lastSeen >= now - ONLINE_GRACE_MS;
    })
  );
  const hasRecentAttackEvidence = now > 0 && combinedLogs.some((log) => {
    if (log.epochMs < now - UNDER_ATTACK_COOLDOWN_MS) {
      return false;
    }
    return log.type === "SSH_AUTH_FAIL" || log.type === "COMMAND_EXEC" || log.type === "HASSH_DNA";
  });

  const inferredWarRoomOnline = rawOnlineSignal || hasRecentConnectivityEvidence;
  const inferredUnderAttack = inferredWarRoomOnline && (rawAttackSignal || hasRecentAttackEvidence);
  const inferredWarRoomState: "OFFLINE" | "LIVE" | "UNDER ATTACK" = !inferredWarRoomOnline && !hasRecentThreatActivity
    ? "OFFLINE"
    : inferredUnderAttack
      ? "UNDER ATTACK"
      : "LIVE";
  const backendWarRoomState: "OFFLINE" | "LIVE" | "UNDER ATTACK" = warRoom.state === "under_attack"
    ? "UNDER ATTACK"
    : warRoom.state === "live"
      ? "LIVE"
      : "OFFLINE";
  const backendUnderAttack = warRoom.state === "under_attack";
  const backendStateStale = now > 0 && warRoom.updatedAt > 0 && (now - warRoom.updatedAt) > 60_000;
  const useEmergencyFallback = !warRoom.ok || (warRoom.degraded && backendStateStale);
  const warRoomState: "OFFLINE" | "LIVE" | "UNDER ATTACK" = useEmergencyFallback ? inferredWarRoomState : backendWarRoomState;
  const underAttack = useEmergencyFallback ? inferredUnderAttack : backendUnderAttack;
  const mappedFromGraph = (operations?.sensor.attackGraph.data?.nodes ?? []).filter((node) => {
    if (!node || typeof node !== "object") {
      return false;
    }
    const nodeType = (node as { type?: string }).type ?? "";
    return nodeType === "technique";
  }).length;
  const mappedFromSessions = (() => {
    const sessions = operations?.sensor.sessions.data?.sessions ?? [];
    const unique = new Set<string>();
    for (const session of sessions) {
      for (const technique of session.mitreTechniques ?? []) {
        if (technique) {
          unique.add(technique);
        }
      }
    }
    return unique.size;
  })();
  const mappedMitreCount = Math.max(stats.mitreCoverage, mappedFromGraph, mappedFromSessions);

  const downloadSensorJson = useCallback(() => {
    if (!operations) {
      return;
    }
    const payload = {
      exportedAt: new Date().toISOString(),
      source: operations.source,
      sensor: operations.sensor,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `cloudsentinel-export-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [operations]);

  useEffect(() => {
    const handleExport = () => downloadSensorJson();
    window.addEventListener("agent:export", handleExport);
    return () => window.removeEventListener("agent:export", handleExport);
  }, [downloadSensorJson]);

  return (
    <div className="flex flex-col gap-4 lg:h-full">
      {/* Header & Compact Stats */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">War Room</h2>
          <p className="text-slate-500 text-xs mt-0.5">Real-time Threat Intelligence Monitor</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex bg-white dark:bg-[#0a0a0a] border border-slate-200 dark:border-white/5 rounded-lg shadow-sm text-sm overflow-x-auto w-full md:w-auto scrollbar-hide">
            <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5">
              <span className="text-slate-500 text-xs mr-2">Connections</span>
              <span className="font-semibold text-slate-900 dark:text-white">{liveConnectionCount.toLocaleString()}</span>
            </div>
            <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5">
              <span className="text-slate-500 text-xs mr-2">MTTB</span>
              <span className="font-semibold text-slate-900 dark:text-white">{stats.mttb}</span>
            </div>
            <div className="px-3 py-1.5 border-r border-slate-200 dark:border-white/5">
              <span className="text-slate-500 text-xs mr-2">MITRE TTPs</span>
              <span className="font-semibold text-slate-900 dark:text-white">{mappedMitreCount}</span>
            </div>
            <div className="px-3 py-1.5">
              <span className="text-slate-500 text-xs mr-2">Uptime</span>
              <span className="font-semibold text-slate-900 dark:text-white">{stats.systemUptime}</span>
            </div>
          </div>

          <button
            onClick={downloadSensorJson}
            disabled={!operations}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/5 bg-white dark:bg-[#0a0a0a] hover:bg-slate-50 dark:hover:bg-white/5 text-xs font-medium text-slate-700 dark:text-slate-300 disabled:opacity-50 transition-colors shadow-sm"
          >
            <Download size={14} />
            <span className="hidden sm:inline">Export</span>
          </button>

          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border shadow-sm ${warRoomState === "OFFLINE" ? "bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-500" : warRoomState === "UNDER ATTACK" ? "bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-500" : "bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-500"}`}>
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${warRoomState === "OFFLINE" ? "bg-amber-400" : warRoomState === "UNDER ATTACK" ? "bg-red-400" : "bg-emerald-400"}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${warRoomState === "OFFLINE" ? "bg-amber-500" : warRoomState === "UNDER ATTACK" ? "bg-red-500" : "bg-emerald-500"}`}></span>
            </span>
            <span className="text-xs font-semibold tracking-wide">
              {warRoomState}
            </span>
            {warRoom.degraded && (
              <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400">
                degraded
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#0a0a0a] shadow-sm">
            <span className={`text-[10px] uppercase font-bold tracking-wide ${warRoom.authoritative ? "text-emerald-500" : "text-amber-500"}`}>
              {warRoom.authoritative ? "Authoritative" : "Partial"}
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              source: {warRoom.source ?? stats.telemetrySource ?? "mixed"}
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Grid - Flex-1 to fill remaining height */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Map Section */}
        <div className="lg:col-span-2 flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden min-h-[400px] lg:min-h-0">
          <div className="flex justify-between items-center px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
            <h3 className="font-medium text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Globe size={16} className="text-blue-500" />
              Global Threat Map
            </h3>
            <div className="flex gap-3">
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span>Auth Fail</span>
              <span className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]"></span>Command</span>
            </div>
          </div>
          <div className="flex-1 min-h-0 relative flex flex-col">
            <ThreatMap
              onRegionClick={setSelectedRegion}
              selectedRegion={selectedRegion}
              underAttack={underAttack}
              threatLogs={combinedLogs}
            />
          </div>
        </div>

        {/* Live Feed Section */}
        <div className="lg:col-span-1 flex flex-col bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-sm overflow-hidden min-h-[500px] lg:min-h-0">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-white/5 shrink-0 bg-slate-50/50 dark:bg-white/[0.02]">
            <h3 className="font-medium text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <Activity size={16} className="text-emerald-500" />
              Live Activity
            </h3>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden p-2">
            <AttackLog selectedRegion={selectedRegion} underAttack={underAttack} threatLogs={combinedLogs} />
          </div>
        </div>
      </div>
    </div>
  );
}
