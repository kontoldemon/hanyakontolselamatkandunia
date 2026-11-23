"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import { io } from "socket.io-client";
import {
  LIVE_LOG_BATCH_MS,
  LIVE_LOG_RETENTION_MS,
  type CloudSentinelEvent,
  type SocketTelemetrySnapshot,
  type ThreatLog,
} from "./types";
import { toThreatLog } from "./parsers";

const socketTelemetryState: SocketTelemetrySnapshot = {
  socketUrl: "",
  connected: false,
  reconnectAttempts: 0,
  connectCount: 0,
  disconnectCount: 0,
  lastError: "",
  recent: [],
};

function pushSocketTelemetry(
  event: string,
  level: "info" | "warn" | "error",
  detail?: string,
) {
  const timestamp = new Date().toISOString();
  socketTelemetryState.recent = [{ timestamp, level, event, detail }, ...socketTelemetryState.recent].slice(0, 120);
}

function snapshotSocketTelemetry(): SocketTelemetrySnapshot {
  return {
    ...socketTelemetryState,
    recent: [...socketTelemetryState.recent],
  };
}

function socketUrl(): string | null {
  const configured = process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL?.trim();
  return configured || null;
}

let globalSocket: ReturnType<typeof io> | null = null;
let globalLogs: ThreatLog[] = [];
const subscribers = new Set<(logs: ThreatLog[]) => void>();
let pollInterval: number | null = null;
let isFetchingInitial = false;
let pendingLogs: ThreatLog[] = [];
let flushTimer: number | null = null;
let unauthorizedHandledAt = 0;

function teardownLiveRuntime() {
  if (globalSocket) {
    globalSocket.removeAllListeners();
    globalSocket.disconnect();
    globalSocket = null;
  }
  if (pollInterval !== null) {
    window.clearInterval(pollInterval);
    pollInterval = null;
  }
  if (flushTimer !== null) {
    window.clearTimeout(flushTimer);
    flushTimer = null;
  }
  pendingLogs = [];
  globalLogs = [];
  subscribers.forEach((sub) => {
    startTransition(() => sub([]));
  });
  socketTelemetryState.connected = false;
}

export function handleUnauthorizedApi(source: string) {
  const now = Date.now();
  if (now - unauthorizedHandledAt < 4000) {
    return;
  }
  unauthorizedHandledAt = now;
  pushSocketTelemetry("auth_expired", "warn", source);
  teardownLiveRuntime();
  if (typeof window !== "undefined") {
    const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
    window.location.assign(`/signin?next=${next}`);
  }
}

function addLogs(items: ThreatLog[]) {
  if (items.length === 0) return;
  const cutoff = Date.now() - LIVE_LOG_RETENTION_MS;
  const merged = [...items, ...globalLogs].filter(
    (item) => Number.isFinite(item.epochMs) && item.epochMs >= cutoff,
  );
  const seen = new Set<string>();
  const unique: ThreatLog[] = [];
  for (const item of merged) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    unique.push(item);
  }
  globalLogs = unique.sort((a, b) => b.epochMs - a.epochMs).slice(0, 150);
  subscribers.forEach((sub) => {
    startTransition(() => sub(globalLogs));
  });
}

function flushPendingLogs() {
  flushTimer = null;
  if (pendingLogs.length === 0) {
    return;
  }
  const batch = pendingLogs;
  pendingLogs = [];
  addLogs(batch);
}

function enqueueLogs(items: ThreatLog[]) {
  if (items.length === 0) {
    return;
  }
  pendingLogs.push(...items);
  if (flushTimer !== null) {
    return;
  }
  flushTimer = window.setTimeout(flushPendingLogs, LIVE_LOG_BATCH_MS);
}

async function loadRecentEvents() {
  if (isFetchingInitial) return;
  isFetchingInitial = true;
  try {
    const response = await fetch("/api/cloudsentinel/events", { cache: "no-store" });
    if (response.status === 401) {
      handleUnauthorizedApi("events");
      return;
    }
    if (!response.ok) {
      pushSocketTelemetry("events_fetch_failed", "warn", `status=${response.status}`);
      return;
    }
    const payload = (await response.json()) as {
      events?: CloudSentinelEvent[];
      ok?: boolean;
      error?: string;
    };
    if (payload.ok === false && payload.error) {
      pushSocketTelemetry("events_fetch_upstream_error", "warn", payload.error);
    }
    const mapped = (payload.events ?? []).map(toThreatLog);
    enqueueLogs(mapped);
  } catch (error) {
    pushSocketTelemetry(
      "events_fetch_exception",
      "error",
      error instanceof Error ? error.message : "request failed",
    );
  } finally {
    isFetchingInitial = false;
  }
}

function initSocket(url: string) {
  if (globalSocket) return;
  const socketToken = process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN?.trim();

  globalSocket = io(url, {
    transports: ["polling", "websocket"],
    reconnection: true,
    withCredentials: false,
    query: socketToken ? { token: socketToken } : undefined,
  });
  socketTelemetryState.socketUrl = url;

  globalSocket.on("connect", () => {
    socketTelemetryState.connected = true;
    socketTelemetryState.connectCount += 1;
    pushSocketTelemetry("connect", "info");
  });

  globalSocket.on("disconnect", (reason: string) => {
    socketTelemetryState.connected = false;
    socketTelemetryState.disconnectCount += 1;
    pushSocketTelemetry("disconnect", "warn", reason);
  });

  globalSocket.on("connect_error", (error: Error) => {
    socketTelemetryState.lastError = error.message;
    pushSocketTelemetry("connect_error", "error", error.message);
  });

  globalSocket.io.on("reconnect_attempt", (attempt: number) => {
    socketTelemetryState.reconnectAttempts = attempt;
    pushSocketTelemetry("reconnect_attempt", "warn", `attempt=${attempt}`);
  });

  globalSocket.io.on("reconnect", (attempt: number) => {
    socketTelemetryState.reconnectAttempts = 0;
    pushSocketTelemetry("reconnect", "info", `attempt=${attempt}`);
  });

  globalSocket.io.on("reconnect_error", (error: Error) => {
    socketTelemetryState.lastError = error.message;
    pushSocketTelemetry("reconnect_error", "error", error.message);
  });

  globalSocket.on("cloudsentinel:event", (event: CloudSentinelEvent) => {
    enqueueLogs([toThreatLog(event)]);
  });
}

export function useLiveThreatLogs(enabled = true) {
  const [liveLogs, setLiveLogs] = useState<ThreatLog[]>(globalLogs);
  const url = socketUrl();

  useEffect(() => {
    if (!enabled) return;

    if (!globalSocket) {
      if (url) {
        initSocket(url);
      }
      loadRecentEvents();
      if (!pollInterval) {
        pollInterval = window.setInterval(loadRecentEvents, 3000);
      }
    }

    subscribers.add(setLiveLogs);

    return () => {
      subscribers.delete(setLiveLogs);
    };
  }, [enabled, url]);

  return useMemo(() => liveLogs, [liveLogs]);
}

export function useSocketTelemetry() {
  const [snapshot, setSnapshot] = useState<SocketTelemetrySnapshot>(snapshotSocketTelemetry);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setSnapshot(snapshotSocketTelemetry());
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  return snapshot;
}
