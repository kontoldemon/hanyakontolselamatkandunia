import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type AdminResult<T> = {
  ok: boolean;
  data: T | null;
  error?: string;
  latencyMs: number;
  statusCode?: number;
};

async function fetchAdmin<T>(path: string): Promise<AdminResult<T>> {
  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";

  const startedAt = Date.now();
  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL(path, baseUrl), {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(8000),
    });
    const latencyMs = Date.now() - startedAt;

    if (!response.ok) {
      return {
        ok: false,
        data: null,
        error: `${response.status} ${response.statusText}`,
        latencyMs,
        statusCode: response.status,
      };
    }

    return {
      ok: true,
      data: (await response.json()) as T,
      latencyMs,
      statusCode: response.status,
    };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: error instanceof Error ? error.message : "request failed",
      latencyMs: Date.now() - startedAt,
    };
  }
}

export async function GET() {
  const [readiness, metrics, stats, sessions, distribution, attackGraph, anomaly, llm] =
    await Promise.all([
      fetchAdmin<Record<string, unknown>>("/readiness"),
      fetchAdmin<Record<string, unknown>>("/metrics/json"),
      fetchAdmin<Record<string, unknown>>("/stats"),
      fetchAdmin<{ sessions?: unknown[] }>("/sessions"),
      fetchAdmin<unknown[]>("/attack-distribution"),
      fetchAdmin<{ nodes?: unknown[]; edges?: unknown[] }>("/attack-graph"),
      fetchAdmin<Record<string, unknown>>("/anomaly-stats"),
      fetchAdmin<Record<string, unknown>>("/llm/status"),
    ]);

  const live =
    readiness.ok ||
    metrics.ok ||
    stats.ok ||
    sessions.ok ||
    distribution.ok ||
    attackGraph.ok ||
    anomaly.ok ||
    llm.ok;

  return NextResponse.json({
    ok: live,
    source: live ? "live" : "offline",
    telemetry: {
      upstreamLatencyMs: {
        readiness: readiness.latencyMs,
        metrics: metrics.latencyMs,
        stats: stats.latencyMs,
        sessions: sessions.latencyMs,
        distribution: distribution.latencyMs,
        attackGraph: attackGraph.latencyMs,
        anomaly: anomaly.latencyMs,
        llm: llm.latencyMs,
      },
      maxLatencyMs: Math.max(
        readiness.latencyMs,
        metrics.latencyMs,
        stats.latencyMs,
        sessions.latencyMs,
        distribution.latencyMs,
        attackGraph.latencyMs,
        anomaly.latencyMs,
        llm.latencyMs,
      ),
      sampledAt: new Date().toISOString(),
    },
    sensor: {
      readiness,
      metrics,
      stats,
      sessions,
      distribution,
      attackGraph,
      anomaly,
      llm,
    },
  });
}
