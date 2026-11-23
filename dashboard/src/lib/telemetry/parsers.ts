import type { CloudSentinelEvent, TelemetrySource, ThreatLog } from "./types";

export function normalizeTelemetrySource(value: unknown): TelemetrySource | undefined {
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

export function numberOrUndefined(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed !== 0 ? parsed : undefined;
}

export function parseEventTime(raw: unknown): number {
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

export function formatUptime(seconds: number): string {
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
