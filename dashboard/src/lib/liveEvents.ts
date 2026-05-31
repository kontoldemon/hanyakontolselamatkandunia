"use client";

import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { io } from "socket.io-client";

export type TelemetrySource = "clickhouse" | "runtime" | "memory" | "mixed";

export type ThreatLog = {
  id: string;
  timestamp: string;
  epochMs: number;
  ip: string;
  country: string;
  countryName?: string;
  asn?: string;
  isp?: string;
  org?: string;
  services?: string;
  region?: string;
  city?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
  type: string;
  payload: string;
  mitreId: string;
  action: string;
  timeToBlock: string | null;
  hassh?: string;
  client?: string;
  ja4s?: string;
  mitreTechniques?: string[];
  role?: "attacker" | "honeypot";
  responseMode?: string;
};

export type DashboardStats = {
  activeSessions: number;
  blockedIPs: number;
  credentialsHarvested: number;
  totalAttacks: number;
  totalEvents?: number;
  uniqueIps?: number;
  uniqueCountries?: number;
  uniqueCommands?: number;
  avgRisk?: number;
  blockRate?: number;
  concurrentConnections: number;
  mttb: string;
  mitreCoverage: number;
  systemUptime: string;
  attackActive: boolean;
  source: "live" | "offline";
  totalConnections?: number;
  totalAuthFailures?: number;
  totalCommands?: number;
  totalBlocks?: number;
  telemetrySource?: TelemetrySource;
  authoritative?: boolean;
  sourceBreakdown?: Record<string, TelemetrySource>;
};

export type WarRoomState = {
  ok: boolean;
  state: "offline" | "live" | "under_attack";
  lastOnlineAt: number | null;
  lastAttackAt: number | null;
  cooldownUntil: number | null;
  updatedAt: number;
  degraded: boolean;
  authoritative: boolean;
  source: TelemetrySource;
  sourceBreakdown: Record<string, string | boolean>;
  windows: {
    onlineGraceMs: number;
    attackCooldownMs: number;
    activeFreshnessMs: number;
  };
  stats?: {
    stateTransitions?: number;
    degradedTransitions?: number;
    redisReadLatencyMs?: number;
    redisWriteLatencyMs?: number;
  };
  exposure?: {
    provider?: string;
    desiredEnabled?: boolean;
    effectiveEnabled?: boolean;
    syncing?: boolean;
    updatedAt?: number;
  };
};

export type CapturedSession = {
  id: string;
  ip: string;
  country: string;
  countryCode?: string;
  countryName?: string;
  asn?: string;
  isp?: string;
  org?: string;
  services?: string;
  region?: string;
  city?: string;
  latitude?: string;
  longitude?: string;
  timezone?: string;
  startTime: string;
  duration: string;
  startedAtEpochMs?: number;
  firstSeenEpochMs?: number;
  lastSeenEpochMs?: number;
  client: string;
  fingerprint: string;
  input: string[];
  status: string;
  sessionCount?: number;
  riskScore?: number;
  soarAction?: string;
  mttbMs?: number;
  blockEffective?: boolean;
  mitreTechniques?: string[];
  replay?: Array<{ role: "attacker" | "honeypot"; text: string; timestamp?: string }>;
  source?: TelemetrySource;
};

type SummaryResponse = {
  ok: boolean;
  status?: "live" | "offline";
  source?: TelemetrySource;
  authoritative?: boolean;
  sourceBreakdown?: Record<string, TelemetrySource>;
  metrics?: {
    totalEvents?: number;
    uniqueIps?: number;
    uniqueCountries?: number;
    uniqueCommands?: number;
    avgRisk?: number;
    blockRate?: number;
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
  status?: "live" | "offline";
  source: "live" | "offline";
  telemetrySource?: TelemetrySource;
  authoritative?: boolean;
  sourceBreakdown?: Record<string, TelemetrySource>;
  telemetry?: {
    upstreamLatencyMs?: {
      readiness?: number;
      metrics?: number;
      stats?: number;
      sessions?: number;
      distribution?: number;
      attackGraph?: number;
      anomaly?: number;
      llm?: number;
    };
    maxLatencyMs?: number;
    sampledAt?: string;
  };
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

export type SocketTelemetryEvent = {
  timestamp: string;
  level: "info" | "warn" | "error";
  event: string;
  detail?: string;
};

export type SocketTelemetrySnapshot = {
  socketUrl: string;
  connected: boolean;
  reconnectAttempts: number;
  connectCount: number;
  disconnectCount: number;
  lastError: string;
  recent: SocketTelemetryEvent[];
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
  attackActive: false,
  source: "offline",
};

const EMPTY_WAR_ROOM_STATE: WarRoomState = {
  ok: false,
  state: "offline",
  lastOnlineAt: null,
  lastAttackAt: null,
  cooldownUntil: null,
  updatedAt: 0,
  degraded: true,
  authoritative: false,
  source: "runtime",
  sourceBreakdown: {
    state: "runtime",
    onlineEvidence: "runtime",
    attackEvidence: "runtime",
    storage: "memory",
  },
  windows: {
    onlineGraceMs: 25_000,
    attackCooldownMs: 90_000,
    activeFreshnessMs: 90_000,
  },
  exposure: {
    provider: "runtime",
    desiredEnabled: true,
    effectiveEnabled: true,
    syncing: false,
    updatedAt: 0,
  },
};

const LIVE_LOG_RETENTION_MS = 24 * 60 * 60 * 1000;
const LIVE_LOG_BATCH_MS = 250;
const SESSION_ACTIVE_WINDOW_MS = 90 * 1000;
const OFFLINE_GRACE_MS = 20_000;
const OFFLINE_FAILURE_THRESHOLD = 2;
let WAR_ROOM_SNAPSHOT_CACHE: WarRoomState | null = null;
const WAR_ROOM_STATE_STORAGE_KEY = "cloudsentinel.war_room_state";

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

export type CloudSentinelEvent = {
  eventid?: string;
  timestamp?: string;
  id?: string;
  src_ip?: string;
  country_code?: string;
  country?: string;
  input?: string;
  username?: string;
  password?: string;
  hassh?: string;
  hassh_md5?: string;
  ja4s?: string;
  country_name?: string;
  asn?: string;
  isp?: string;
  org?: string;
  services?: string;
  region?: string;
  city?: string;
  latitude?: string | number;
  longitude?: string | number;
  timezone?: string;
  mttb_ms?: number;
  block_command?: string;
  cloudsentinel_mitre_techniques?: string[];
  cloudsentinel_soar_action?: string;
  cloudsentinel_risk_score?: number;
  version?: string;
  client?: string;
  output?: string;
  reason?: string;
  hassh_algorithms?: string;
  response_mode?: string;
};

function normalizeTelemetrySource(value: unknown): TelemetrySource | undefined {
  if (value === "clickhouse" || value === "runtime" || value === "memory" || value === "mixed") {
    return value;
  }
  return undefined;
}

function eventType(eventid = "") {
  if (eventid.includes("command.output")) {
    return "HONEYPOT_RESPONSE";
  }
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
  const user = (event.username || "").trim();
  const pass = (event.password || "").trim();
  const hasCredential = !!user || !!pass;
  const safeUser = user || "unknown";
  const safePass = pass || "unknown";

  if (hasCredential && event.eventid?.includes("login.failed")) {
    return `[AUTH] Failed login for ${safeUser} / ${safePass}`;
  }
  if (hasCredential && event.eventid?.includes("login.success")) {
    return `[AUTH] Login success for ${safeUser} / ${safePass}`;
  }

  if (event.eventid?.includes("command.output")) {
    const response = (event.output || event.reason || "").trim();
    if (response) {
      return response;
    }
  }
  if (event.input) {
    return event.input;
  }
  if (hasCredential) {
    return `[AUTH] Authentication event for ${safeUser} / ${safePass}`;
  }
  const hassh = event.hassh_md5 ?? event.hassh;
  if (hassh) {
    return `hassh=${hassh}`;
  }
  return event.eventid ?? "cloudsentinel.event";
}

function deriveFallbackFingerprint(hasshAlgorithms?: string): string {
  const input = (hasshAlgorithms ?? "").trim();
  if (!input) {
    return "";
  }
  let a = 0x811c9dc5;
  let b = 0x01000193;
  for (let i = 0; i < input.length; i += 1) {
    const code = input.charCodeAt(i);
    a ^= code;
    a = Math.imul(a, 16777619);
    b ^= code;
    b = Math.imul(b, 1099511627);
  }
  const hex = `${(a >>> 0).toString(16).padStart(8, "0")}${(b >>> 0).toString(16).padStart(8, "0")}`;
  return `${hex}${hex}`;
}

function resolveFingerprint(event: CloudSentinelEvent): string {
  const direct = (event.hassh_md5 ?? event.hassh ?? "").trim();
  if (direct) {
    return direct;
  }
  return deriveFallbackFingerprint(event.hassh_algorithms);
}

function resolveClientLabel(event: CloudSentinelEvent, fingerprint: string): string {
  const normalizeVersion = (raw: string): string => {
    const value = raw.trim();
    if (!value || value.toLowerCase().includes("unknown")) {
      return "";
    }
    const lower = value.toLowerCase();
    if (lower.includes("paramiko")) return "Paramiko";
    if (lower.includes("libssh2")) return "libssh2";
    if (lower.includes("libssh")) return "libssh";
    if (lower.includes("dropbear")) return "Dropbear";
    if (lower.includes("openssh")) return "OpenSSH";
    if (lower.includes("putty")) return "PuTTY";
    if (lower.includes("ssh-2.0-go")) return "Go crypto/ssh";
    return value;
  };

  const explicitClient = (event.client ?? "").trim();
  if (explicitClient && explicitClient.toLowerCase() !== "unknown") {
    return explicitClient;
  }
  const normalizedVersion = normalizeVersion(event.version ?? "");
  if (normalizedVersion) {
    return normalizedVersion;
  }
  if (fingerprint) {
    return `hassh:${fingerprint.slice(0, 8)}`;
  }
  return "unknown";
}

function normalizeCountryCode(
  countryCode?: string,
  countryName?: string,
  fallback?: string,
): { code: string; name: string | undefined } {
  const raw = (countryCode ?? fallback ?? "").trim().toUpperCase();
  if (raw && raw !== "UNKNOWN" && raw !== "??") {
    if (raw.length === 2) {
      return { code: raw, name: countryName };
    }
    if (raw.length > 2 && raw !== "XX") {
      return { code: "XX", name: raw };
    }
  }
  const name = (countryName ?? "").trim();
  if (name && name.toLowerCase() !== "unknown") {
    return { code: "XX", name };
  }
  return { code: "XX", name: undefined };
}

export function toThreatLog(event: CloudSentinelEvent): ThreatLog {
  const ts = parseEventTime(event.timestamp);
  const country = normalizeCountryCode(event.country_code, event.country_name, event.country);
  const blocked = ["iptables_block", "dry_run_block"].includes(
    event.cloudsentinel_soar_action ?? "",
  );
  const detected = event.cloudsentinel_soar_action === "detect_only";
  const dt = new Date(ts);
  const time = `${dt.toLocaleTimeString("en-GB", { hour12: false })}.${String(dt.getMilliseconds()).padStart(3, "0")}`;
  const mttb = typeof event.mttb_ms === "number" ? `${event.mttb_ms.toFixed(1)}ms` : null;
  const stableId =
    event.id ??
    `${event.eventid ?? "evt"}-${event.src_ip ?? "0.0.0.0"}-${ts}-${event.input ?? ""}-${event.username ?? ""}`;

  const fingerprint = resolveFingerprint(event);
  const client = resolveClientLabel(event, fingerprint);
  return {
    id: stableId,
    timestamp: time,
    epochMs: ts,
    ip: event.src_ip ?? "0.0.0.0",
    country: country.code,
    countryName: country.name,
    asn: event.asn,
    isp: event.isp,
    org: event.org,
    services: event.services,
    region: event.region,
    city: event.city,
    latitude: numberOrUndefined(event.latitude),
    longitude: numberOrUndefined(event.longitude),
    timezone: event.timezone,
    type: eventType(event.eventid),
    payload: payloadFor(event),
    mitreId: event.cloudsentinel_mitre_techniques?.[0] ?? "",
    action: blocked ? "Blocked" : detected ? "Detected" : "Active",
    timeToBlock: blocked ? (mttb ?? "<100ms") : null,
    hassh: fingerprint,
    client,
    ja4s: event.ja4s,
    mitreTechniques: event.cloudsentinel_mitre_techniques ?? [],
    role: event.eventid?.includes("command.output") ? "honeypot" : "attacker",
    responseMode: event.response_mode,
  };
}

function socketUrl() {
  const configured = process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL?.trim();
  if (configured && configured !== "http://localhost:3001") {
    return configured;
  }
  return "https://188.166.184.42.sslip.io";
}

function numberOrUndefined(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed !== 0 ? parsed : undefined;
}

function parseEventTime(raw: unknown): number {
  if (typeof raw === "number") {
    return raw > 1_000_000_000_000 ? raw : raw * 1000;
  }
  if (typeof raw === "string" && raw.trim()) {
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) {
      return numeric > 1_000_000_000_000 ? numeric : numeric * 1000;
    }
    const parsed = Date.parse(raw);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return Date.now();
}

function formatUptime(seconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${totalSeconds}s`;
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

function handleUnauthorizedApi(source: string) {
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
      initSocket(url);
      loadRecentEvents();
      if (!pollInterval) {
        pollInterval = window.setInterval(loadRecentEvents, 12000);
      }
    }

    subscribers.add(setLiveLogs);

    return () => {
      subscribers.delete(setLiveLogs);
    };
  }, [enabled, url]);

  return useMemo(() => liveLogs, [liveLogs]);
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
    if (WAR_ROOM_SNAPSHOT_CACHE) {
      return WAR_ROOM_SNAPSHOT_CACHE;
    }
    const persisted = loadPersistedWarRoomState();
    if (persisted) {
      WAR_ROOM_SNAPSHOT_CACHE = persisted;
      return persisted;
    }
    return EMPTY_WAR_ROOM_STATE;
  });
  const lastSuccessAtRef = useRef(
    WAR_ROOM_SNAPSHOT_CACHE?.updatedAt && WAR_ROOM_SNAPSHOT_CACHE.updatedAt > 0
      ? WAR_ROOM_SNAPSHOT_CACHE.updatedAt
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
          WAR_ROOM_SNAPSHOT_CACHE = next;
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
        WAR_ROOM_SNAPSHOT_CACHE = nextState;
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

export function useCapturedSessions() {
  const operations = useSensorOperations();
  const liveLogs = useLiveThreatLogs();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const tick = () => setNowMs(Date.now());
    tick();
    const timer = window.setInterval(tick, 5000);
    return () => window.clearInterval(timer);
  }, []);

  return useMemo(() => {
    const activeCutoffMs = nowMs - SESSION_ACTIVE_WINDOW_MS;

    const toReplayInfoLabel = (text: string) => {
      const value = (text || "").trim();
      const normalized = value.toLowerCase();
      if (!normalized) {
        return null;
      }
      if (normalized.startsWith("[open]") || normalized.startsWith("[close]") || normalized.startsWith("[auth]") || normalized.startsWith("[version]")) {
        return value;
      }
      if (normalized.startsWith("cloudsentinel.session.connect")) {
        return "[OPEN] Session opened";
      }
      if (normalized.startsWith("cloudsentinel.session.closed")) {
        return "[CLOSE] Session closed";
      }
      if (normalized.startsWith("cloudsentinel.client.version")) {
        return "[VERSION] Client banner observed";
      }
      if (normalized === "auth-attempt" || normalized.startsWith("cloudsentinel.login.failed") || normalized.startsWith("cloudsentinel.login.success")) {
        return "[AUTH] Authentication event";
      }
      return null;
    };

    const isReplayNoise = (text: string) => {
      const value = (text || "").trim().toLowerCase();
      if (toReplayInfoLabel(text)) {
        return false;
      }
      return (
        !value ||
        value.includes("[redacted]")
      );
    };

    const normalizeReplay = (session: CapturedSession) => {
      const cleaned: Array<{ role: "attacker" | "honeypot"; text: string; timestamp?: string }> = [];
      const seen = new Set<string>();
      let lastAttacker = "";

      for (const entry of session.replay ?? []) {
        const rawText = (entry.text || "").trim();
        const text = toReplayInfoLabel(rawText) ?? rawText;
        if (isReplayNoise(text)) {
          continue;
        }
        if (entry.role === "attacker") {
          lastAttacker = text;
        } else if (entry.role === "honeypot" && lastAttacker && text === lastAttacker) {
          continue;
        }
        const key = `${entry.role}|${text}|${entry.timestamp ?? ""}`;
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        cleaned.push({ role: entry.role, text, timestamp: entry.timestamp });
      }

      session.replay = cleaned.slice(-600);
    };

    const grouped = new Map<string, CapturedSession>();
    const latestSessionByIp = new Map<string, string>();
    const sessions = operations?.sensor.sessions.data?.sessions ?? [];
    const recentLiveByIp = new Map<string, number>();

    for (const log of liveLogs) {
      if (!log.ip) continue;
      const current = recentLiveByIp.get(log.ip) ?? 0;
      if (log.epochMs > current) {
        recentLiveByIp.set(log.ip, log.epochMs);
      }
    }

    for (const session of sessions) {
      if (!session.ip) {
        continue;
      }
      const backendLastSeen =
        session.lastSeenEpochMs ??
        session.firstSeenEpochMs ??
        session.startedAtEpochMs ??
        0;
      const liveLastSeen = recentLiveByIp.get(session.ip) ?? 0;
      const effectiveLastSeen = Math.max(backendLastSeen, liveLastSeen);
      const incomingStatus = (session.status || "").trim().toLowerCase();
      const forceClosed =
        incomingStatus === "active" &&
        (effectiveLastSeen === 0 || effectiveLastSeen < activeCutoffMs);

      const syntheticId = `sess-live-${session.ip}`;
      if (grouped.has(syntheticId) && session.id !== syntheticId) {
        grouped.delete(syntheticId);
      }
      const key = session.id || `sess-${session.ip}-${session.startedAtEpochMs ?? session.startTime}`;
      grouped.set(key, {
        ...session,
        status: forceClosed ? "Closed" : session.status,
        input: [...(session.input ?? [])].slice(-300),
        replay: [...(session.replay ?? [])].slice(-600),
        lastSeenEpochMs: effectiveLastSeen || session.lastSeenEpochMs,
      });
      const prepared = grouped.get(key);
      if (prepared) {
        normalizeReplay(prepared);
        const lastSeen = prepared.lastSeenEpochMs ?? prepared.firstSeenEpochMs ?? 0;
        const currentKey = latestSessionByIp.get(prepared.ip);
        if (!currentKey) {
          latestSessionByIp.set(prepared.ip, key);
        } else {
          const current = grouped.get(currentKey);
          const currentSeen = current?.lastSeenEpochMs ?? current?.firstSeenEpochMs ?? 0;
          if (lastSeen >= currentSeen) {
            latestSessionByIp.set(prepared.ip, key);
          }
        }
      }
    }

    for (const log of liveLogs) {
      if (log.epochMs < activeCutoffMs) {
        continue;
      }
      const targetId = latestSessionByIp.get(log.ip);
      const existing = targetId ? grouped.get(targetId) : undefined;
      if (!existing) {
        const syntheticId = `sess-live-${log.ip}`;
        grouped.set(syntheticId, {
          id: syntheticId,
          ip: log.ip,
          country: log.country,
          countryCode: log.country,
          countryName: log.countryName ?? log.country,
          asn: log.asn ?? "",
          isp: log.isp ?? "",
          org: log.org ?? "",
          services: log.services ?? "",
          region: log.region ?? "",
          city: log.city ?? "",
          latitude: log.latitude ? String(log.latitude) : "0",
          longitude: log.longitude ? String(log.longitude) : "0",
          timezone: log.timezone ?? "UTC",
          startTime: log.timestamp,
          duration: "live",
          startedAtEpochMs: log.epochMs,
          firstSeenEpochMs: log.epochMs,
          lastSeenEpochMs: log.epochMs,
          client: log.client ?? "unknown",
          fingerprint: log.hassh ?? "",
          input: [],
          status: "Active",
          sessionCount: 1,
          riskScore: 0,
          soarAction: log.action === "Blocked" ? "detect_only" : "none",
          mttbMs: 0,
          blockEffective: log.action === "Blocked",
          mitreTechniques: log.mitreTechniques ?? [],
          replay: [],
          source: "mixed",
        });
        latestSessionByIp.set(log.ip, syntheticId);
      }
      const resolvedId = latestSessionByIp.get(log.ip);
      const current = resolvedId ? grouped.get(resolvedId) : undefined;
      if (!current) {
        continue;
      }
      if ((!current.asn || current.asn === "N/A") && log.asn) {
        current.asn = log.asn;
      }
      if ((!current.isp || current.isp === "N/A") && log.isp) {
        current.isp = log.isp;
      }
      if ((!current.org || current.org === "N/A") && log.org) {
        current.org = log.org;
      }
      if ((!current.services || current.services === "N/A") && log.services) {
        current.services = log.services;
      }
      if ((!current.region || current.region === "Unknown") && log.region) {
        current.region = log.region;
      }
      if ((!current.city || current.city === "Unknown") && log.city) {
        current.city = log.city;
      }
      if ((!current.latitude || current.latitude === "0") && typeof log.latitude === "number") {
        current.latitude = String(log.latitude);
      }
      if ((!current.longitude || current.longitude === "0") && typeof log.longitude === "number") {
        current.longitude = String(log.longitude);
      }
      if ((!current.timezone || current.timezone === "UTC") && log.timezone) {
        current.timezone = log.timezone;
      }
      if (log.hassh && !current.fingerprint) {
        current.fingerprint = log.hassh;
      }
      if (
        (!current.client || current.client === "unknown") &&
        log.client &&
        log.client !== "unknown"
      ) {
        current.client = log.client;
      }
      // Append live events to replay so the terminal updates instantly without waiting for backend sync
      const replayInfoLabel = toReplayInfoLabel(log.payload ?? "");
      const shouldAppendReplay =
        !!log.payload &&
        (
          log.type === "COMMAND_EXEC" ||
          log.type === "HONEYPOT_RESPONSE" ||
          !!replayInfoLabel
        );
      if (shouldAppendReplay && log.payload) {
        const role = replayInfoLabel
          ? "honeypot"
          : (log.role ?? (log.type === "HONEYPOT_RESPONSE" ? "honeypot" : "attacker"));
        current.replay = current.replay ?? [];
        current.replay.push({
          role,
          text: replayInfoLabel ?? log.payload,
          timestamp: log.timestamp
        });
      }

      if (log.mitreTechniques?.length) {
        current.mitreTechniques = Array.from(
          new Set([...(current.mitreTechniques ?? []), ...log.mitreTechniques]),
        );
      }
      current.status = "Active";
      current.startTime = current.startTime || log.timestamp;
      current.startedAtEpochMs = current.startedAtEpochMs ?? log.epochMs;
      current.firstSeenEpochMs = current.firstSeenEpochMs ?? log.epochMs;
      current.lastSeenEpochMs = Math.max(current.lastSeenEpochMs ?? 0, log.epochMs);
      current.country = current.country || log.country;
      current.countryCode = current.countryCode || log.country;
      current.countryName = current.countryName || log.countryName || log.country;
      current.riskScore = Math.max(current.riskScore ?? 0, log.action === "Blocked" ? 70 : 0);
      if (!current.soarAction || current.soarAction === "none") {
        current.soarAction = log.action === "Blocked" ? "detect_only" : "none";
      }
      if (log.action === "Blocked") {
        current.blockEffective = true;
      }
      if (current.blockEffective !== true && current.soarAction === "iptables_block") {
        current.blockEffective = true;
      }
      if ((current.mttbMs ?? 0) <= 0 && log.timeToBlock) {
        const parsed = Number(log.timeToBlock.replace("ms", ""));
        if (Number.isFinite(parsed) && parsed > 0) {
          current.mttbMs = parsed;
        }
      }
      current.sessionCount = Math.max(current.sessionCount ?? 1, 1);
      current.source = current.source ?? "clickhouse";
      const replaySeen = new Set<string>();
      current.replay = (current.replay ?? [])
        .map((entry) => ({
          ...entry,
          text: toReplayInfoLabel((entry.text || "").trim()) ?? (entry.text || "").trim(),
        }))
        .filter((entry) => {
          if (isReplayNoise(entry.text)) {
            return false;
          }
          const key = `${entry.role}|${entry.text}|${entry.timestamp ?? ""}`;
          if (replaySeen.has(key)) {
            return false;
          }
          replaySeen.add(key);
          return true;
        })
        .slice(-600);
      normalizeReplay(current);
      current.input = Array.from(new Set(current.input)).slice(-300);
    }

    return [...grouped.values()]
      .sort((a, b) => (b.lastSeenEpochMs ?? 0) - (a.lastSeenEpochMs ?? 0))
      .slice(0, 100);
  }, [operations, liveLogs, nowMs]);
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
