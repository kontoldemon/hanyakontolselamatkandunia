"use client";

import { useEffect, useMemo, useState } from "react";
import { io } from "socket.io-client";

export type ThreatLog = {
  id: string;
  timestamp: string;
  ip: string;
  country: string;
  type: string;
  payload: string;
  mitreId: string;
  action: string;
  timeToBlock: string | null;
  hassh?: string;
  mitreTechniques?: string[];
};

export type DashboardStats = {
  activeSessions: number;
  blockedIPs: number;
  credentialsHarvested: number;
  totalAttacks: number;
  concurrentConnections: number;
  mttb: string;
  mitreCoverage: number;
  systemUptime: string;
  source: "live" | "offline";
};

export type CapturedSession = {
  id: string;
  ip: string;
  country: string;
  startTime: string;
  duration: string;
  client: string;
  fingerprint: string;
  input: string[];
  status: string;
  sessionCount?: number;
  riskScore?: number;
  mitreTechniques?: string[];
};

type SummaryResponse = {
  ok: boolean;
  source: "live" | "fallback";
  metrics?: {
    activeSessions?: number;
    mttbMs?: number;
    totalConnections?: number;
    totalAuthFailures?: number;
    totalCommands?: number;
    totalBlocks?: number;
    blockedIpsCurrent?: number;
    uptimeSeconds?: number;
  };
};

type SensorResult<T> = {
  ok: boolean;
  data: T | null;
  error?: string;
};

export type SensorOperations = {
  ok: boolean;
  source: "live" | "offline";
  sensor: {
    readiness: SensorResult<Record<string, unknown>>;
    metrics: SensorResult<Record<string, unknown>>;
    stats: SensorResult<Record<string, unknown>>;
    sessions: SensorResult<{ sessions?: CapturedSession[] }>;
    distribution: SensorResult<Array<{ name: string; value: number; fill: string }>>;
    attackGraph: SensorResult<{ nodes?: unknown[]; edges?: unknown[] }>;
    anomaly: SensorResult<Record<string, unknown>>;
    llm: SensorResult<Record<string, unknown>>;
  };
};

const EMPTY_STATS: DashboardStats = {
  activeSessions: 0,
  blockedIPs: 0,
  credentialsHarvested: 0,
  totalAttacks: 0,
  concurrentConnections: 0,
  mttb: "offline",
  mitreCoverage: 0,
  systemUptime: "offline",
  source: "offline",
};

type CloudSentinelEvent = {
  eventid?: string;
  timestamp?: string;
  src_ip?: string;
  country_code?: string;
  input?: string;
  username?: string;
  password?: string;
  hassh?: string;
  hassh_md5?: string;
  ja4s?: string;
  country_name?: string;
  mttb_ms?: number;
  block_command?: string;
  cloudsentinel_mitre_techniques?: string[];
  cloudsentinel_soar_action?: string;
  cloudsentinel_risk_score?: number;
};

function eventType(eventid = "") {
  if (eventid.includes("login.failed")) {
    return "SSH_AUTH_FAIL";
  }
  if (eventid.includes("command")) {
    return "COMMAND_EXEC";
  }
  if (eventid.includes("kex")) {
    return "HASSH_DNA";
  }
  return "SENSOR_EVENT";
}

function payloadFor(event: CloudSentinelEvent) {
  if (event.input) {
    return event.input;
  }
  if (event.username || event.password) {
    return `${event.username ?? ""} / [redacted]`;
  }
  const hassh = event.hassh_md5 ?? event.hassh;
  if (hassh) {
    return `hassh=${hassh}`;
  }
  return event.eventid ?? "cloudsentinel.event";
}

function toThreatLog(event: CloudSentinelEvent): ThreatLog {
  const blocked = ["iptables_block", "dry_run_block", "detect_only"].includes(
    event.cloudsentinel_soar_action ?? "",
  );
  const time = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString("en-GB", { hour12: false })
    : new Date().toLocaleTimeString("en-GB", { hour12: false });
  const mttb = typeof event.mttb_ms === "number" ? `${event.mttb_ms.toFixed(1)}ms` : null;

  return {
    id: `${event.eventid ?? "evt"}-${Date.now()}`,
    timestamp: time,
    ip: event.src_ip ?? "0.0.0.0",
    country: event.country_code ?? "??",
    type: eventType(event.eventid),
    payload: payloadFor(event),
    mitreId: event.cloudsentinel_mitre_techniques?.[0] ?? "",
    action: blocked ? "Blocked" : "Active",
    timeToBlock: blocked ? (mttb ?? "<100ms") : null,
    hassh: event.hassh_md5 ?? event.hassh,
    mitreTechniques: event.cloudsentinel_mitre_techniques ?? [],
  };
}

function socketUrl() {
  return process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL ?? "http://localhost:3001";
}

export function useLiveThreatLogs() {
  const [liveLogs, setLiveLogs] = useState<ThreatLog[]>([]);
  const url = socketUrl();

  useEffect(() => {
    const socket = io(url, {
      transports: ["websocket"],
      reconnection: true,
    });

    socket.on("cloudsentinel:event", (event: CloudSentinelEvent) => {
      setLiveLogs((current) => [toThreatLog(event), ...current].slice(0, 100));
    });

    return () => {
      socket.close();
    };
  }, [url]);

  return useMemo(() => liveLogs, [liveLogs]);
}

export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats>(EMPTY_STATS);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      try {
        const response = await fetch("/api/cloudsentinel/summary", { cache: "no-store" });
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as SummaryResponse;
        if (cancelled) {
          return;
        }
        const metrics = data.metrics ?? {};
        setStats({
          ...EMPTY_STATS,
          activeSessions: metrics.activeSessions ?? 0,
          blockedIPs: metrics.blockedIpsCurrent ?? 0,
          totalAttacks:
            (metrics.totalAuthFailures ?? 0) +
            (metrics.totalConnections ?? 0) +
            (metrics.totalCommands ?? 0),
          concurrentConnections: metrics.activeSessions ?? 0,
          mttb:
            typeof metrics.mttbMs === "number" && metrics.mttbMs > 0
              ? `${metrics.mttbMs.toFixed(2)}ms`
              : "offline",
          systemUptime:
            typeof metrics.uptimeSeconds === "number" && metrics.uptimeSeconds > 0
              ? `${Math.floor(metrics.uptimeSeconds / 3600)}h`
              : "offline",
          source: data.ok ? "live" : "offline",
        });
      } catch {
        // Keep visible offline state instead of pretending traffic exists.
      }
    }

    loadStats();
    const interval = window.setInterval(loadStats, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return stats;
}

export function useSensorOperations() {
  const [operations, setOperations] = useState<SensorOperations | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadOperations() {
      try {
        const response = await fetch("/api/cloudsentinel/operations", { cache: "no-store" });
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as SensorOperations;
        if (!cancelled) {
          setOperations(data);
        }
      } catch {
        if (!cancelled) {
          setOperations(null);
        }
      }
    }

    loadOperations();
    const interval = window.setInterval(loadOperations, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return operations;
}

export function useCapturedSessions() {
  const operations = useSensorOperations();
  return operations?.sensor.sessions.data?.sessions ?? [];
}
