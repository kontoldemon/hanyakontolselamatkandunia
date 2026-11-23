import { NextResponse } from "next/server";
import {
  adminApiConfig,
  adminApiConfigError,
  toSafeNumber,
  type SourceKind,
} from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Summary = {
  ok: boolean;
  status: "live" | "offline";
  source: SourceKind;
  authoritative: boolean;
  sourceBreakdown: {
    totalEvents: SourceKind;
    uniqueIps: SourceKind;
    uniqueCountries: SourceKind;
    uniqueCommands: SourceKind;
    avgRisk: SourceKind;
    blockRate: SourceKind;
    activeSessions: SourceKind;
    mttbMs: SourceKind;
    totalConnections: SourceKind;
    totalAuthFailures: SourceKind;
    totalCommands: SourceKind;
    totalBlocks: SourceKind;
    blockedIpsCurrent: SourceKind;
    uptimeSeconds: SourceKind;
  };
  metrics: {
    totalEvents: number;
    uniqueIps: number;
    uniqueCountries: number;
    uniqueCommands: number;
    avgRisk: number;
    blockRate: number;
    activeSessions: number;
    mttbMs: number;
    totalConnections: number;
    totalAuthFailures: number;
    totalCommands: number;
    totalBlocks: number;
    blockedIpsCurrent: number;
    uptimeSeconds: number;
  };
};

const offline: Summary = {
  ok: false,
  status: "offline",
  source: "runtime",
  authoritative: false,
  sourceBreakdown: {
    totalEvents: "runtime",
    uniqueIps: "runtime",
    uniqueCountries: "runtime",
    uniqueCommands: "runtime",
    avgRisk: "runtime",
    blockRate: "runtime",
    activeSessions: "runtime",
    mttbMs: "runtime",
    totalConnections: "runtime",
    totalAuthFailures: "runtime",
    totalCommands: "runtime",
    totalBlocks: "runtime",
    blockedIpsCurrent: "runtime",
    uptimeSeconds: "runtime",
  },
  metrics: {
    totalEvents: 0,
    uniqueIps: 0,
    uniqueCountries: 0,
    uniqueCommands: 0,
    avgRisk: 0,
    blockRate: 0,
    activeSessions: 0,
    mttbMs: 0,
    totalConnections: 0,
    totalAuthFailures: 0,
    totalCommands: 0,
    totalBlocks: 0,
    blockedIpsCurrent: 0,
    uptimeSeconds: 0,
  },
};

export async function GET() {
  const configError = adminApiConfigError();
  if (configError) return configError;
  const { baseUrl, headers } = adminApiConfig();

  try {
    const [truthResponse, metricsResponse] = await Promise.all([
      fetch(new URL("/truth-summary", baseUrl), {
        cache: "no-store",
        headers,
        signal: AbortSignal.timeout(9000),
      }),
      fetch(new URL("/metrics/json", baseUrl), {
        cache: "no-store",
        headers,
        signal: AbortSignal.timeout(9000),
      }),
    ]);

    const metricsPayload = metricsResponse.ok ? await metricsResponse.json() as Record<string, unknown> : {};
    const uptimeSeconds = toSafeNumber(metricsPayload.uptime_seconds);

    if (!truthResponse.ok) {
      return NextResponse.json(
        {
          ...offline,
          metrics: {
            ...offline.metrics,
            uptimeSeconds,
          },
          sourceBreakdown: {
            ...offline.sourceBreakdown,
            uptimeSeconds: "runtime",
          },
        } satisfies Summary,
        { status: 200 },
      );
    }

    const truthPayload = await truthResponse.json() as {
      ok?: boolean;
      authoritative?: boolean;
      source?: SourceKind;
      metrics?: Record<string, unknown>;
    };

    const truthMetrics = truthPayload.metrics ?? {};
    const truthOk = truthPayload.ok === true;
    const authoritative = truthOk && truthPayload.authoritative !== false;
    const source: SourceKind = authoritative ? "clickhouse" : "runtime";

    const summary: Summary = {
      ok: truthOk,
      status: truthOk ? "live" : "offline",
      source,
      authoritative,
      sourceBreakdown: {
        totalEvents: authoritative ? "clickhouse" : "runtime",
        uniqueIps: authoritative ? "clickhouse" : "runtime",
        uniqueCountries: authoritative ? "clickhouse" : "runtime",
        uniqueCommands: authoritative ? "clickhouse" : "runtime",
        avgRisk: authoritative ? "clickhouse" : "runtime",
        blockRate: authoritative ? "clickhouse" : "runtime",
        activeSessions: authoritative ? "clickhouse" : "runtime",
        mttbMs: authoritative ? "clickhouse" : "runtime",
        totalConnections: authoritative ? "clickhouse" : "runtime",
        totalAuthFailures: authoritative ? "clickhouse" : "runtime",
        totalCommands: authoritative ? "clickhouse" : "runtime",
        totalBlocks: authoritative ? "clickhouse" : "runtime",
        blockedIpsCurrent: authoritative ? "clickhouse" : "runtime",
        uptimeSeconds: "runtime",
      },
      metrics: {
        totalEvents: toSafeNumber(truthMetrics.total_events),
        uniqueIps: toSafeNumber(truthMetrics.unique_ips),
        uniqueCountries: toSafeNumber(truthMetrics.unique_countries),
        uniqueCommands: toSafeNumber(truthMetrics.unique_commands),
        avgRisk: toSafeNumber(truthMetrics.avg_risk),
        blockRate: toSafeNumber(truthMetrics.block_rate),
        activeSessions: toSafeNumber(truthMetrics.active_sessions),
        mttbMs: toSafeNumber(truthMetrics.mttb_ms),
        totalConnections: toSafeNumber(truthMetrics.total_connections),
        totalAuthFailures: toSafeNumber(truthMetrics.total_auth_failures),
        totalCommands: toSafeNumber(truthMetrics.total_commands),
        totalBlocks: toSafeNumber(truthMetrics.total_blocks),
        blockedIpsCurrent: toSafeNumber(truthMetrics.blocked_ips_current),
        uptimeSeconds,
      },
    };

    return NextResponse.json(summary satisfies Summary);
  } catch (error) {
    console.error("[cloudsentinel/summary] request exception", error);
    return NextResponse.json(offline, { status: 200 });
  }
}
