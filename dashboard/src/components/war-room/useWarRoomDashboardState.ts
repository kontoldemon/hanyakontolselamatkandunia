"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  useCapturedSessions,
  useDashboardStats,
  useLiveThreatLogs,
  useSensorOperations,
  useWarRoomState,
} from "@/lib/liveEvents";

const LIVE_ACTIVITY_WINDOW_MS = 90 * 1000;
const ONLINE_GRACE_MS = 25 * 1000;
const UNDER_ATTACK_COOLDOWN_MS = 90 * 1000;
const REALTIME_ATTACK_HINT_MS = 20 * 1000;

export function useWarRoomDashboardState() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [displayConnections, setDisplayConnections] = useState(0);
  const [now, setNow] = useState<number>(0);

  const stats = useDashboardStats();
  const threatLogs = useLiveThreatLogs();
  const operations = useSensorOperations();
  const sessions = useCapturedSessions();
  const warRoom = useWarRoomState();
  const liveConnectionCount = stats.activeSessions;

  useEffect(() => {
    const t = setTimeout(() => setNow(Date.now()), 0);
    const interval = setInterval(() => setNow(Date.now()), 5000);
    return () => {
      clearTimeout(t);
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setDisplayConnections((prev) => {
        if (prev === liveConnectionCount) {
          return prev;
        }
        const delta = liveConnectionCount - prev;
        const step = Math.max(1, Math.ceil(Math.abs(delta) / 4));
        return delta > 0 ? prev + step : prev - step;
      });
    }, 120);
    return () => window.clearInterval(timer);
  }, [liveConnectionCount]);

  const combinedLogs = useMemo(() => {
    if (now <= 0) {
      return [];
    }
    const currentEpochMs = now;
    const windowFloor = currentEpochMs - LIVE_ACTIVITY_WINDOW_MS;
    const activeIps = new Set(sessions.filter((s) => s.status === "Active").map((s) => s.ip));
    const knownSessionIps = new Set(sessions.map((s) => s.ip));

    const filteredThreatLogs = threatLogs.filter((log) => {
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
    });

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

  const hasRecentThreatActivity =
    now > 0 &&
    combinedLogs.some((log) => {
      if (log.epochMs < now - LIVE_ACTIVITY_WINDOW_MS) {
        return false;
      }
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
  const hasRecentConnectivityEvidence =
    now > 0 &&
    (threatLogs.some((log) => log.epochMs >= now - ONLINE_GRACE_MS) ||
      sessions.some((session) => {
        const lastSeen =
          session.lastSeenEpochMs ??
          session.firstSeenEpochMs ??
          session.startedAtEpochMs ??
          0;
        return lastSeen >= now - ONLINE_GRACE_MS;
      }));
  const hasRecentAttackEvidence =
    now > 0 &&
    combinedLogs.some((log) => {
      if (log.epochMs < now - UNDER_ATTACK_COOLDOWN_MS) {
        return false;
      }
      return log.type === "SSH_AUTH_FAIL" || log.type === "COMMAND_EXEC" || log.type === "HASSH_DNA";
    });
  const hasRealtimeAttackHint =
    now > 0 &&
    combinedLogs.some((log) => {
      if (log.epochMs < now - REALTIME_ATTACK_HINT_MS) {
        return false;
      }
      return log.type === "SSH_AUTH_FAIL" || log.type === "COMMAND_EXEC" || log.type === "HASSH_DNA";
    });

  const inferredWarRoomOnline = rawOnlineSignal || hasRecentConnectivityEvidence;
  const inferredUnderAttack = inferredWarRoomOnline && (rawAttackSignal || hasRecentAttackEvidence);
  const exposurePaused = warRoom.exposure?.effectiveEnabled === false;
  const backendUnderAttack = warRoom.state === "under_attack";
  const underAttack = exposurePaused
    ? false
    : backendUnderAttack || inferredUnderAttack || hasRealtimeAttackHint;

  const mappedFromGraph = (operations?.sensor.attackGraph.data?.nodes ?? []).filter((node) => {
    if (!node || typeof node !== "object") {
      return false;
    }
    const nodeType = (node as { type?: string }).type ?? "";
    return nodeType === "technique";
  }).length;
  const mappedFromSessions = (() => {
    const sessionRows = operations?.sensor.sessions.data?.sessions ?? [];
    const unique = new Set<string>();
    for (const session of sessionRows) {
      for (const technique of session.mitreTechniques ?? []) {
        if (technique) {
          unique.add(technique);
        }
      }
    }
    return unique.size;
  })();
  const mappedMitreCount = Math.max(mappedFromGraph, mappedFromSessions);

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

  return {
    selectedRegion,
    setSelectedRegion,
    displayConnections,
    stats,
    operations,
    warRoom,
    combinedLogs,
    underAttack,
    mappedMitreCount,
    downloadSensorJson,
  };
}
