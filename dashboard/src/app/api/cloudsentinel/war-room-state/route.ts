import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type SourceKind = "clickhouse" | "runtime" | "memory" | "mixed";
type WarRoomStateKind = "offline" | "live" | "under_attack";

type WarRoomStatePayload = {
  ok: boolean;
  state: WarRoomStateKind;
  lastOnlineAt: number | null;
  lastAttackAt: number | null;
  cooldownUntil: number | null;
  updatedAt: number;
  degraded: boolean;
  authoritative: boolean;
  source: SourceKind;
  sourceBreakdown: Record<string, SourceKind | string | boolean>;
  windows: {
    onlineGraceMs: number;
    attackCooldownMs: number;
    activeFreshnessMs: number;
  };
  stats?: {
    stateTransitions?: number;
    degradedTransitions?: number;
    redisReadLatencyMs?: number;
    redisWriteLatencyMs?: number;
  };
};

const offlineFallback: WarRoomStatePayload = {
  ok: false,
  state: "offline",
  lastOnlineAt: null,
  lastAttackAt: null,
  cooldownUntil: null,
  updatedAt: Date.now(),
  degraded: true,
  authoritative: false,
  source: "runtime",
  sourceBreakdown: {
    state: "runtime",
    onlineEvidence: "runtime",
    attackEvidence: "runtime",
    storage: "memory",
  },
  windows: {
    onlineGraceMs: 25_000,
    attackCooldownMs: 90_000,
    activeFreshnessMs: 90_000,
  },
};

export async function GET() {
  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";

  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL("/war-room-state", baseUrl), {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      console.warn("[cloudsentinel/war-room-state] upstream request failed", {
        status: response.status,
        statusText: response.statusText,
        baseUrl,
      });
      return NextResponse.json(
        {
          ...offlineFallback,
          updatedAt: Date.now(),
        },
        { status: 200 },
      );
    }

    const payload = (await response.json()) as WarRoomStatePayload;
    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    console.error("[cloudsentinel/war-room-state] request exception", error);
    return NextResponse.json(
      {
        ...offlineFallback,
        updatedAt: Date.now(),
      },
      { status: 200 },
    );
  }
}
