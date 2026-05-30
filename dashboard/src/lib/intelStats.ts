"use client";
import { useMemo } from "react";
import type { ThreatLog, CapturedSession } from "./liveEvents";

const INTEL_WINDOW_MS = 24 * 60 * 60 * 1000;

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

function normalizeSessionRisk(session: CapturedSession): number {
  const raw = Number(session.riskScore ?? 0);
  if (!Number.isFinite(raw) || raw <= 0) {
    return 0;
  }
  const weight = Math.max(1, Number(session.sessionCount ?? 1));
  const normalized = raw > 100 ? raw / weight : raw;
  return clampPercent(normalized);
}

export function useIntelStats(liveLogs: ThreatLog[], sessions: CapturedSession[], windowMs = INTEL_WINDOW_MS) {
  return useMemo(() => {
    const newestLogEpoch = liveLogs.reduce((latest, log) => Math.max(latest, log.epochMs || 0), 0);
    const newestSessionEpoch = sessions.reduce((latest, session) => {
      const sessionEpoch =
        session.lastSeenEpochMs ??
        session.firstSeenEpochMs ??
        session.startedAtEpochMs ??
        Date.parse(session.startTime);
      return Math.max(latest, Number.isFinite(sessionEpoch) ? sessionEpoch : 0);
    }, 0);
    const newestEpoch = Math.max(newestLogEpoch, newestSessionEpoch);
    const cutoff = Math.max(0, newestEpoch - windowMs);
    const logs24h = liveLogs.filter((log) => log.epochMs >= cutoff);
    const sessions24h = sessions.filter((session) => {
      const ts =
        session.lastSeenEpochMs ??
        session.firstSeenEpochMs ??
        session.startedAtEpochMs ??
        Date.parse(session.startTime);
      return Number.isFinite(ts) && ts >= cutoff;
    });

    // Country stats
    const countryMap = new Map<string, { code: string; name: string; count: number }>();
    const addCountry = (code: string, name?: string, n = 1) => {
      if (!code || code === "XX") return;
      const e = countryMap.get(code);
      if (e) { e.count += n; if (name && e.name === code) e.name = name; }
      else countryMap.set(code, { code, name: name || code, count: n });
    };
    for (const l of logs24h) addCountry(l.country, l.countryName);
    for (const s of sessions24h) addCountry(s.countryCode || s.country, s.countryName, s.sessionCount ?? 1);
    const countries = [...countryMap.values()].sort((a, b) => b.count - a.count);

    // Timing heatmap: 7 days x 24 hours
    const grid: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
    const addTs = (val: number | string | undefined) => {
      if (!val) return;
      let ms = typeof val === 'string' ? Number(val) : val;
      if (isNaN(ms)) ms = Date.parse(val as string);
      if (!ms || isNaN(ms)) return;
      // if it's in seconds instead of ms
      if (ms < 100000000000) ms *= 1000;
      const d = new Date(ms);
      const day = d.getDay() === 0 ? 6 : d.getDay() - 1;
      grid[day][d.getHours()]++;
    };
    for (const l of logs24h) addTs(l.epochMs);
    for (const s of sessions24h) addTs(s.startedAtEpochMs || s.firstSeenEpochMs || s.startTime);
    const heatmapMax = Math.max(1, ...grid.flat());

    // Peak hour
    const hourTotals = Array(24).fill(0);
    for (const row of grid) row.forEach((v, h) => { hourTotals[h] += v; });
    const peakHour = hourTotals.indexOf(Math.max(...hourTotals));

    // ISP / Org stats
    const ispMap = new Map<string, number>();
    const addIsp = (val?: string, n = 1) => {
      const k = (val ?? "").trim();
      if (!k || k === "N/A" || k === "unknown") return;
      ispMap.set(k, (ispMap.get(k) ?? 0) + n);
    };
    for (const l of logs24h) { addIsp(l.org); addIsp(l.isp); }
    for (const s of sessions24h) { addIsp(s.org, s.sessionCount ?? 1); addIsp(s.isp, s.sessionCount ?? 1); }
    const isps = [...ispMap.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count).slice(0, 10);

    // Risk score distribution
    const riskBuckets = [0, 0, 0, 0, 0]; // 0-20, 20-40, 40-60, 60-80, 80-100
    let riskTotal = 0, riskCount = 0;
    for (const s of sessions24h) {
      const r = normalizeSessionRisk(s);
      if (r > 0) { riskTotal += r; riskCount++; }
      const idx = Math.min(4, Math.floor(r / 20));
      riskBuckets[idx]++;
    }
    const avgRisk = clampPercent(riskCount > 0 ? riskTotal / riskCount : 0);

    // SOAR breakdown
    const soarMap = new Map<string, number>();
    let blockedCount = 0;
    for (const s of sessions24h) {
      const action = (s.soarAction ?? "none").trim().toLowerCase() || "none";
      soarMap.set(action, (soarMap.get(action) ?? 0) + 1);
      if (s.blockEffective || action === "iptables_block" || action === "already_blocked") blockedCount++;
    }
    const soarData = [...soarMap.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
    const blockRate = sessions24h.length > 0 ? clampPercent(Math.round((blockedCount / sessions24h.length) * 100)) : 0;

    // Unique IPs
    const uniqueIps = new Set<string>();
    for (const l of logs24h) uniqueIps.add(l.ip);
    for (const s of sessions24h) uniqueIps.add(s.ip);

    return {
      countries,
      heatmap: { grid, max: heatmapMax, peakHour },
      isps,
      risk: { buckets: riskBuckets, avg: avgRisk },
      soar: { data: soarData, blockRate, blockedCount },
      uniqueIps: uniqueIps.size,
      totalCountries: countryMap.size,
    };
  }, [liveLogs, sessions, windowMs]);
}
