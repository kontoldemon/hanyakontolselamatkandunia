import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Summary = {
  ok: boolean;
  source: "live" | "offline";
  metrics: {
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
  source: "offline",
  metrics: {
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
    const [metricsResponse, sessionsResponse] = await Promise.all([
      fetch(new URL("/metrics/json", baseUrl), {
        cache: "no-store",
        headers,
        signal: AbortSignal.timeout(8000),
      }),
      fetch(new URL("/sessions", baseUrl), {
        cache: "no-store",
        headers,
        signal: AbortSignal.timeout(8000),
      }),
    ]);

    if (!metricsResponse.ok) {
      return NextResponse.json(offline, { status: 200 });
    }

    const data = await metricsResponse.json();
    let activeFromSessions = 0;
    if (sessionsResponse.ok) {
      try {
        const sessionPayload = (await sessionsResponse.json()) as { sessions?: Array<{ status?: string }> };
        activeFromSessions = (sessionPayload.sessions ?? []).filter(
          (session) => (session.status ?? "").toLowerCase() === "active",
        ).length;
      } catch {
        activeFromSessions = 0;
      }
    }
    const activeSessions = Math.max(toNumber(data.active_sessions), activeFromSessions);

    return NextResponse.json({
      ok: true,
      source: "live",
      metrics: {
        activeSessions,
        mttbMs: toNumber(data.mttb_ms),
        totalConnections: toNumber(data.total_connections),
        totalAuthFailures: toNumber(data.total_auth_failures),
        totalCommands: toNumber(data.total_commands),
        totalBlocks: toNumber(data.total_blocks),
        blockedIpsCurrent: toNumber(data.blocked_ips_current),
        uptimeSeconds: toNumber(data.uptime_seconds),
      },
    } satisfies Summary);
  } catch {
    return NextResponse.json(offline, { status: 200 });
  }
}
