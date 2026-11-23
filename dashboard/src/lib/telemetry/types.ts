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

export type SummaryResponse = {
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

export type SensorResult<T> = {
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

export const EMPTY_STATS: DashboardStats = {
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

export const EMPTY_WAR_ROOM_STATE: WarRoomState = {
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

export const LIVE_LOG_RETENTION_MS = 24 * 60 * 60 * 1000;
export const LIVE_LOG_BATCH_MS = 250;
export const SESSION_ACTIVE_WINDOW_MS = 90 * 1000;
export const OFFLINE_GRACE_MS = 20_000;
export const OFFLINE_FAILURE_THRESHOLD = 2;
export const WAR_ROOM_STATE_STORAGE_KEY = "cloudsentinel.war_room_state";
