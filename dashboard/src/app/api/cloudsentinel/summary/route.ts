import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Summary = {
  ok: boolean;
  source: "live" | "fallback";
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

const fallback: Summary = {
  ok: false,
  source: "fallback",
  metrics: {
    activeSessions: 24,
    mttbMs: 0.96,
    totalConnections: 1248,
    totalAuthFailures: 884,
    totalCommands: 312,
    totalBlocks: 138,
    blockedIpsCurrent: 18,
    uptimeSeconds: 0,
  },
};

function toNumber(value: unknown, fallbackValue = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallbackValue;
}

export async function GET() {
  const baseUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL
    || process.env.NEXT_PUBLIC_CLOUDSENTINEL_ADMIN_API_URL;

  if (!baseUrl) {
    return NextResponse.json(fallback);
  }

  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL("/metrics/json", baseUrl), {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(3500),
    });

    if (!response.ok) {
      return NextResponse.json(fallback, { status: 200 });
    }

    const data = await response.json();
    return NextResponse.json({
      ok: true,
      source: "live",
      metrics: {
        activeSessions: toNumber(data.active_sessions),
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
    return NextResponse.json(fallback, { status: 200 });
  }
}
