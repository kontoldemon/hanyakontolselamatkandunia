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

type SourceKind = "clickhouse" | "runtime" | "memory" | "mixed";

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
      console.warn("[cloudsentinel/operations] upstream request failed", {
        path,
        status: response.status,
        statusText: response.statusText,
        baseUrl,
      });
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
    console.error("[cloudsentinel/operations] request exception", {
      path,
      error: error instanceof Error ? error.message : "request failed",
      baseUrl,
    });
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

  const inferSource = (path: string, result: AdminResult<unknown>): SourceKind => {
    if (!result.ok || !result.data || typeof result.data !== "object") {
      return "runtime";
    }
    const payload = result.data as Record<string, unknown>;
    const explicit = payload.source;
    if (explicit === "clickhouse" || explicit === "runtime" || explicit === "memory" || explicit === "mixed") {
      return explicit;
    }
    if (path === "/events" || path === "/attack-distribution") {
      return "clickhouse";
    }
    if (path === "/metrics/json" || path === "/stats" || path === "/readiness" || path === "/anomaly-stats" || path === "/llm/status") {
      return "runtime";
    }
    return "mixed";
  };

  const sessionsSource = inferSource("/sessions", sessions);
  const graphSource = inferSource("/attack-graph", attackGraph);
  const distributionSource = inferSource("/attack-distribution", distribution);
  const metricsSource = inferSource("/metrics/json", metrics);
  const statsSource = inferSource("/stats", stats);
  const readinessSource = inferSource("/readiness", readiness);
  const anomalySource = inferSource("/anomaly-stats", anomaly);
  const llmSource = inferSource("/llm/status", llm);

  const sourceBreakdown = {
    readiness: readinessSource,
    metrics: metricsSource,
    stats: statsSource,
    sessions: sessionsSource,
    distribution: distributionSource,
    attackGraph: graphSource,
    anomaly: anomalySource,
    llm: llmSource,
  };

  const uniqueSources = new Set<SourceKind>(Object.values(sourceBreakdown));
  const source: SourceKind = uniqueSources.size === 1 ? (Object.values(sourceBreakdown)[0] as SourceKind) : "mixed";
  const authoritative =
    sessionsSource === "clickhouse" &&
    distributionSource === "clickhouse" &&
    graphSource === "clickhouse";

  return NextResponse.json({
    ok: live,
    status: live ? "live" : "offline",
    source,
    authoritative,
    sourceBreakdown,
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
