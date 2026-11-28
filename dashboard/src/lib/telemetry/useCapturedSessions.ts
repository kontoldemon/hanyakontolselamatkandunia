"use client";

import { useEffect, useMemo, useState } from "react";
import { SESSION_ACTIVE_WINDOW_MS, type CapturedSession } from "./types";
import { useLiveThreatLogs } from "./socketClient";
import { useSensorOperations } from "./useDashboardTelemetry";

function toReplayInfoLabel(text: string): string | null {
  const value = (text || "").trim();
  const normalized = value.toLowerCase();
  if (!normalized) {
    return null;
  }
  if (
    normalized.startsWith("[open]") ||
    normalized.startsWith("[close]") ||
    normalized.startsWith("[auth]") ||
    normalized.startsWith("[version]")
  ) {
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
  if (
    normalized === "auth-attempt" ||
    normalized.startsWith("cloudsentinel.login.failed") ||
    normalized.startsWith("cloudsentinel.login.success")
  ) {
    return "[AUTH] Authentication event";
  }
  return null;
}

function isReplayNoise(text: string): boolean {
  const value = (text || "").trim().toLowerCase();
  if (toReplayInfoLabel(text)) {
    return false;
  }
  return !value || value.includes("[redacted]");
}

function normalizeReplay(session: CapturedSession): void {
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

  session.replay = cleaned;
}

export function useCapturedSessions() {
  const operations = useSensorOperations();
  const liveLogs = useLiveThreatLogs();
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const tick = () => setNowMs(Date.now());
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, []);

  return useMemo(() => {
    const activeCutoffMs = nowMs - SESSION_ACTIVE_WINDOW_MS;
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
        input: [...(session.input ?? [])],
        replay: [...(session.replay ?? [])],
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
          riskScore: log.riskScore ?? 0,
          soarAction: log.soarAction || "none",
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
      if ((!current.asn || current.asn === "N/A") && log.asn) current.asn = log.asn;
      if ((!current.isp || current.isp === "N/A") && log.isp) current.isp = log.isp;
      if ((!current.org || current.org === "N/A") && log.org) current.org = log.org;
      if ((!current.services || current.services === "N/A") && log.services) current.services = log.services;
      if ((!current.region || current.region === "Unknown") && log.region) current.region = log.region;
      if ((!current.city || current.city === "Unknown") && log.city) current.city = log.city;
      if ((!current.latitude || current.latitude === "0") && typeof log.latitude === "number") {
        current.latitude = String(log.latitude);
      }
      if ((!current.longitude || current.longitude === "0") && typeof log.longitude === "number") {
        current.longitude = String(log.longitude);
      }
      if ((!current.timezone || current.timezone === "UTC") && log.timezone) current.timezone = log.timezone;
      if (log.hassh && !current.fingerprint) current.fingerprint = log.hassh;
      if ((!current.client || current.client === "unknown") && log.client && log.client !== "unknown") {
        current.client = log.client;
      }

      const replayInfoLabel = toReplayInfoLabel(log.payload ?? "");
      const shouldAppendReplay =
        !!log.payload &&
        (log.type === "COMMAND_EXEC" || log.type === "HONEYPOT_RESPONSE" || !!replayInfoLabel);
      if (shouldAppendReplay && log.payload) {
        const role = replayInfoLabel
          ? "honeypot"
          : (log.role ?? (log.type === "HONEYPOT_RESPONSE" ? "honeypot" : "attacker"));
        current.replay = current.replay ?? [];
        current.replay.push({
          role,
          text: replayInfoLabel ?? log.payload,
          timestamp: log.timestamp,
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
      current.riskScore = Math.max(current.riskScore ?? 0, log.riskScore ?? 0);
      if (log.soarAction) {
        current.soarAction = log.soarAction;
      } else if (!current.soarAction) {
        current.soarAction = "none";
      }
      if (log.action === "Blocked") current.blockEffective = true;
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
        });
      normalizeReplay(current);
      current.input = Array.from(new Set(current.input));
    }

    return [...grouped.values()]
      .sort((a, b) => (b.lastSeenEpochMs ?? 0) - (a.lastSeenEpochMs ?? 0))
      .slice(0, 100);
  }, [operations, liveLogs, nowMs]);
}
