"use client";

import { useEffect, useRef, useState } from "react";
import {
  EMPTY_STATS,
  EMPTY_WAR_ROOM_STATE,
  OFFLINE_FAILURE_THRESHOLD,
  OFFLINE_GRACE_MS,
  WAR_ROOM_STATE_STORAGE_KEY,
  type DashboardStats,
  type SensorOperations,
  type SummaryResponse,
  type WarRoomState,
} from "./types";
import { formatUptime, normalizeTelemetrySource } from "./parsers";
import { handleUnauthorizedApi } from "./socketClient";

let warRoomSnapshotCache: WarRoomState | null = null;

function loadPersistedWarRoomState(): WarRoomState | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(WAR_ROOM_STATE_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<WarRoomState>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return {
      ...EMPTY_WAR_ROOM_STATE,
      ...parsed,
      source: normalizeTelemetrySource(parsed.source) ?? "runtime",
    };
  } catch {
    return null;
  }
}

function persistWarRoomState(value: WarRoomState): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(WAR_ROOM_STATE_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // ignore persistence errors
  }
}

export function useDashboardStats() {
  const [stats, setStats] = useState<DashboardStats>(EMPTY_STATS);
  const lastTotalsRef = useRef({ auth: 0, commands: 0, blocks: 0, conns: 0 });
  const initializedRef = useRef(false);
  const activeUntilRef = useRef(0);
  const lastSuccessAtRef = useRef(0);
  const consecutiveFailuresRef = useRef(0);
  const uptimeBaseSecondsRef = useRef<number | null>(null);
  const uptimeBaseAtMsRef = useRef<number>(0);

  useEffect(() => {
    let cancelled = false;

    const maybeSetOffline = () => {
      const now = Date.now();
      const staleFor = now - lastSuccessAtRef.current;
      if (
        lastSuccessAtRef.current > 0 &&
        staleFor < OFFLINE_GRACE_MS &&
        consecutiveFailuresRef.current < OFFLINE_FAILURE_THRESHOLD
      ) {
        return;
      }
      if (!cancelled) {
        setStats((prev) => ({
          ...prev,
          source: "offline",
          attackActive: false,
          authoritative: false,
        }));
      }
    };

    async function loadStats() {
      try {
        const response = await fetch("/api/cloudsentinel/summary", { cache: "no-store" });
        if (response.status === 401) {
          handleUnauthorizedApi("summary");
          return;
        }
        if (!response.ok) {
          consecutiveFailuresRef.current += 1;
          maybeSetOffline();
          return;
        }
        const data = (await response.json()) as SummaryResponse;
        if (cancelled) {
          return;
        }
        consecutiveFailuresRef.current = 0;
        lastSuccessAtRef.current = Date.now();
        const metrics = data.metrics ?? {};
        const totalAuthFailures = metrics.totalAuthFailures ?? 0;
        const totalConnections = metrics.totalConnections ?? 0;
        const totalCommands = metrics.totalCommands ?? 0;
        const totalBlocks = metrics.totalBlocks ?? 0;
        const hasIncrease =
          initializedRef.current &&
          (
            totalAuthFailures > lastTotalsRef.current.auth ||
            totalCommands > lastTotalsRef.current.commands ||
            totalBlocks > lastTotalsRef.current.blocks ||
            totalConnections > lastTotalsRef.current.conns
          );
        if (hasIncrease) {
          activeUntilRef.current = Date.now() + 20_000;
        }
        initializedRef.current = true;
        lastTotalsRef.current = {
          auth: totalAuthFailures,
          commands: totalCommands,
          blocks: totalBlocks,
          conns: totalConnections,
        };
        const activeSessions = metrics.activeSessions ?? 0;
        const totalEvents = metrics.totalEvents ?? 0;
        const uniqueIps = metrics.uniqueIps ?? 0;
        const uniqueCountries = metrics.uniqueCountries ?? 0;
        const uniqueCommands = metrics.uniqueCommands ?? 0;
        const avgRisk = metrics.avgRisk ?? 0;
        const blockRate = metrics.blockRate ?? 0;
        setStats({
          ...EMPTY_STATS,
          activeSessions,
          blockedIPs: metrics.blockedIpsCurrent ?? 0,
          totalAttacks:
            totalAuthFailures +
            totalConnections +
            totalCommands,
          totalEvents,
          uniqueIps,
          uniqueCountries,
          uniqueCommands,
          avgRisk,
          blockRate,
          totalConnections,
          totalAuthFailures,
          totalCommands,
          totalBlocks,
          concurrentConnections: activeSessions,
          mttb:
            typeof metrics.mttbMs === "number" && metrics.mttbMs > 0
              ? `${metrics.mttbMs.toFixed(2)}ms`
              : "No blocks yet",
          systemUptime:
            typeof metrics.uptimeSeconds === "number" && metrics.uptimeSeconds > 0
              ? formatUptime(metrics.uptimeSeconds)
              : "offline",
          attackActive: data.ok && Date.now() < activeUntilRef.current,
          source: data.status ?? (data.ok ? "live" : "offline"),
          telemetrySource: data.source,
          authoritative: data.authoritative,
          sourceBreakdown: data.sourceBreakdown,
        });
        if (typeof metrics.uptimeSeconds === "number" && metrics.uptimeSeconds > 0) {
          uptimeBaseSecondsRef.current = metrics.uptimeSeconds;
          uptimeBaseAtMsRef.current = Date.now();
        } else {
          uptimeBaseSecondsRef.current = null;
          uptimeBaseAtMsRef.current = 0;
        }
      } catch {
        consecutiveFailuresRef.current += 1;
        maybeSetOffline();
      }
    }

    loadStats();
    const interval = window.setInterval(loadStats, 4000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const base = uptimeBaseSecondsRef.current;
      const baseAt = uptimeBaseAtMsRef.current;
      if (base == null || baseAt <= 0) {
        return;
      }
      const elapsed = Math.max(0, Math.floor((Date.now() - baseAt) / 1000));
      const next = formatUptime(base + elapsed);
      setStats((prev) => {
        if (prev.source === "offline" || prev.systemUptime === next) {
          return prev;
        }
        return { ...prev, systemUptime: next };
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return stats;
}

export function useSensorOperations() {
  const [operations, setOperations] = useState<SensorOperations | null>(null);
  const lastSuccessAtRef = useRef(0);
  const consecutiveFailuresRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const maybeSetOffline = () => {
      const now = Date.now();
      const staleFor = now - lastSuccessAtRef.current;
      if (
        lastSuccessAtRef.current > 0 &&
        staleFor < OFFLINE_GRACE_MS &&
        consecutiveFailuresRef.current < OFFLINE_FAILURE_THRESHOLD
      ) {
        return;
      }
      if (!cancelled) {
        setOperations((prev) =>
          prev
            ? {
                ...prev,
                source: "offline",
                status: "offline",
                authoritative: false,
              }
            : null,
        );
      }
    };

    async function loadOperations() {
      try {
        const response = await fetch("/api/cloudsentinel/operations", { cache: "no-store" });
        if (response.status === 401) {
          handleUnauthorizedApi("operations");
          return;
        }
        if (!response.ok) {
          consecutiveFailuresRef.current += 1;
          maybeSetOffline();
          return;
        }
        const data = (await response.json()) as SensorOperations;
        if (!cancelled) {
          consecutiveFailuresRef.current = 0;
          lastSuccessAtRef.current = Date.now();
          const payload = data as unknown as Record<string, unknown>;
          const telemetrySource = normalizeTelemetrySource(payload.telemetrySource ?? payload.source);
          setOperations({
            ...data,
            source: (data as SensorOperations & { status?: "live" | "offline" }).status ?? data.source,
            telemetrySource,
          });
        }
      } catch {
        consecutiveFailuresRef.current += 1;
        maybeSetOffline();
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

export function useWarRoomState() {
  const [warRoomState, setWarRoomState] = useState<WarRoomState>(() => {
    if (warRoomSnapshotCache) {
      return warRoomSnapshotCache;
    }
    const persisted = loadPersistedWarRoomState();
    if (persisted) {
      warRoomSnapshotCache = persisted;
      return persisted;
    }
    return EMPTY_WAR_ROOM_STATE;
  });
  const lastSuccessAtRef = useRef(
    warRoomSnapshotCache?.updatedAt && warRoomSnapshotCache.updatedAt > 0
      ? warRoomSnapshotCache.updatedAt
      : 0,
  );
  const consecutiveFailuresRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const keepLastState = () => {
      const now = Date.now();
      const staleFor = now - lastSuccessAtRef.current;
      if (
        lastSuccessAtRef.current > 0 &&
        staleFor < OFFLINE_GRACE_MS &&
        consecutiveFailuresRef.current < OFFLINE_FAILURE_THRESHOLD
      ) {
        return;
      }
      if (!cancelled) {
        setWarRoomState((prev) => {
          const next = {
            ...prev,
            ok: false,
            degraded: true,
            authoritative: false,
            source: "runtime",
            updatedAt: Date.now(),
          } as WarRoomState;
          warRoomSnapshotCache = next;
          persistWarRoomState(next);
          return next;
        });
      }
    };

    async function loadWarRoomState() {
      try {
        const response = await fetch("/api/cloudsentinel/war-room-state", { cache: "no-store" });
        if (response.status === 401) {
          handleUnauthorizedApi("war-room-state");
          return;
        }
        if (!response.ok) {
          consecutiveFailuresRef.current += 1;
          keepLastState();
          return;
        }
        const data = (await response.json()) as WarRoomState;
        if (cancelled) {
          return;
        }
        consecutiveFailuresRef.current = 0;
        lastSuccessAtRef.current = Date.now();
        const nextState: WarRoomState = {
          ...EMPTY_WAR_ROOM_STATE,
          ...data,
          source: normalizeTelemetrySource(data.source) ?? "runtime",
        };
        warRoomSnapshotCache = nextState;
        persistWarRoomState(nextState);
        setWarRoomState(nextState);
      } catch {
        consecutiveFailuresRef.current += 1;
        keepLastState();
      }
    }

    loadWarRoomState();
    const interval = window.setInterval(loadWarRoomState, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  return warRoomState;
}
