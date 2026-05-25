"use client";

import { useEffect, useMemo, useState } from "react";
import { io } from "socket.io-client";
import { MOCK_STATS, THREAT_LOGS } from "@/lib/mockData";

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

export type DashboardStats = typeof MOCK_STATS;

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

function adminUrl() {
  return (
    process.env.NEXT_PUBLIC_CLOUDSENTINEL_ADMIN_API_URL ??
    process.env.CLOUDSENTINEL_ADMIN_API_URL ??
    "http://localhost:8080"
  );
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

  return useMemo(() => [...liveLogs, ...(THREAT_LOGS as ThreatLog[])], [liveLogs]);
}

export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats>(MOCK_STATS);
  const url = adminUrl();

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      try {
        const response = await fetch(`${url.replace(/\/$/, "")}/stats`, { cache: "no-store" });
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        if (cancelled) {
          return;
        }
        setStats({
          ...MOCK_STATS,
          activeSessions: data.active_sessions ?? MOCK_STATS.activeSessions,
          blockedIPs: data.blocked_ips_current ?? MOCK_STATS.blockedIPs,
          totalAttacks:
            (data.total_auth_failures ?? 0) +
            (data.total_auth_successes ?? 0) +
            (data.total_commands ?? 0),
          concurrentConnections: data.active_sessions ?? MOCK_STATS.concurrentConnections,
          mttb: typeof data.mttb_ms === "number" ? `${data.mttb_ms.toFixed(1)}ms` : MOCK_STATS.mttb,
        });
      } catch {
        // Mock data remains the offline FYP prototype fallback.
      }
    }

    loadStats();
    const interval = window.setInterval(loadStats, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [url]);

  return stats;
}
