import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type AdminResult<T> = {
  ok: boolean;
  data: T | null;
  error?: string;
};

async function fetchAdmin<T>(path: string): Promise<AdminResult<T>> {
  const baseUrl =
    process.env.CLOUDSENTINEL_ADMIN_API_URL ||
    process.env.NEXT_PUBLIC_CLOUDSENTINEL_ADMIN_API_URL;

  if (!baseUrl) {
    return { ok: false, data: null, error: "admin api url not configured" };
  }

  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL(path, baseUrl), {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(3500),
    });

    if (!response.ok) {
      return { ok: false, data: null, error: `${response.status} ${response.statusText}` };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch (error) {
    return {
      ok: false,
      data: null,
      error: error instanceof Error ? error.message : "request failed",
    };
  }
}

export async function GET() {
  const [readiness, metrics, stats, sessions, distribution, attackGraph, anomaly] =
    await Promise.all([
      fetchAdmin<Record<string, unknown>>("/readiness"),
      fetchAdmin<Record<string, unknown>>("/metrics/json"),
      fetchAdmin<Record<string, unknown>>("/stats"),
      fetchAdmin<{ sessions?: unknown[] }>("/sessions"),
      fetchAdmin<unknown[]>("/attack-distribution"),
      fetchAdmin<{ nodes?: unknown[]; edges?: unknown[] }>("/attack-graph"),
      fetchAdmin<Record<string, unknown>>("/anomaly-stats"),
    ]);

  const live =
    readiness.ok ||
    metrics.ok ||
    stats.ok ||
    sessions.ok ||
    distribution.ok ||
    attackGraph.ok ||
    anomaly.ok;

  return NextResponse.json({
    ok: live,
    source: live ? "live" : "offline",
    sensor: {
      readiness,
      metrics,
      stats,
      sessions,
      distribution,
      attackGraph,
      anomaly,
    },
  });
}
