import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SourceKind = "clickhouse" | "runtime" | "memory" | "mixed";

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

function toNumber(value: unknown, fallbackValue = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallbackValue;
}

export async function GET() {
  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";

  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
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
    const uptimeSeconds = toNumber(metricsPayload.uptime_seconds);

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
    const source: SourceKind = authoritative ? "clickhouse" : (truthPayload.source ?? "mixed");

    const summary: Summary = {
      ok: truthOk,
      status: truthOk ? "live" : "offline",
      source,
      authoritative,
      sourceBreakdown: {
        totalEvents: authoritative ? "clickhouse" : "mixed",
        uniqueIps: authoritative ? "clickhouse" : "mixed",
        uniqueCountries: authoritative ? "clickhouse" : "mixed",
        uniqueCommands: authoritative ? "clickhouse" : "mixed",
        avgRisk: authoritative ? "clickhouse" : "mixed",
        blockRate: authoritative ? "clickhouse" : "mixed",
        activeSessions: authoritative ? "clickhouse" : "mixed",
        mttbMs: authoritative ? "clickhouse" : "mixed",
        totalConnections: authoritative ? "clickhouse" : "mixed",
        totalAuthFailures: authoritative ? "clickhouse" : "mixed",
        totalCommands: authoritative ? "clickhouse" : "mixed",
        totalBlocks: authoritative ? "clickhouse" : "mixed",
        blockedIpsCurrent: authoritative ? "clickhouse" : "mixed",
        uptimeSeconds: "runtime",
      },
      metrics: {
        totalEvents: toNumber(truthMetrics.total_events),
        uniqueIps: toNumber(truthMetrics.unique_ips),
        uniqueCountries: toNumber(truthMetrics.unique_countries),
        uniqueCommands: toNumber(truthMetrics.unique_commands),
        avgRisk: toNumber(truthMetrics.avg_risk),
        blockRate: toNumber(truthMetrics.block_rate),
        activeSessions: toNumber(truthMetrics.active_sessions),
        mttbMs: toNumber(truthMetrics.mttb_ms),
        totalConnections: toNumber(truthMetrics.total_connections),
        totalAuthFailures: toNumber(truthMetrics.total_auth_failures),
        totalCommands: toNumber(truthMetrics.total_commands),
        totalBlocks: toNumber(truthMetrics.total_blocks),
        blockedIpsCurrent: toNumber(truthMetrics.blocked_ips_current),
        uptimeSeconds,
      },
    };

    return NextResponse.json(summary satisfies Summary);
  } catch (error) {
    console.error("[cloudsentinel/summary] request exception", error);
    return NextResponse.json(offline, { status: 200 });
  }
}
