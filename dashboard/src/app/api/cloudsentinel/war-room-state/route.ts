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
    onlineGraceMs: 45_000,
    attackCooldownMs: 90_000,
    activeFreshnessMs: 90_000,
  },
};

function isAttackEventId(eventid: string): boolean {
  const value = (eventid || "").toLowerCase();
  return (
    value.includes("login.failed") ||
    value.includes("command.input") ||
    value.includes("command.failed") ||
    value.includes("client.version") ||
    value.includes("http.request")
  );
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

async function loadCompatibilityWarRoomState(baseUrl: string, token?: string): Promise<WarRoomStatePayload> {
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const [truthRes, eventsRes] = await Promise.all([
    fetch(new URL("/truth-summary", baseUrl), {
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(8000),
    }),
    fetch(new URL("/events?limit=200", baseUrl), {
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(8000),
    }),
  ]);

  if (!truthRes.ok || !eventsRes.ok) {
    throw new Error(`compat upstream failed truth=${truthRes.status} events=${eventsRes.status}`);
  }

  const now = Date.now();
  const truth = (await truthRes.json()) as {
    ok?: boolean;
    source?: SourceKind;
    authoritative?: boolean;
  };
  const eventsPayload = (await eventsRes.json()) as {
    events?: Array<{ timestamp?: number; eventid?: string }>;
  };

  const events = eventsPayload.events ?? [];
  let lastOnlineAt = 0;
  let lastAttackAt = 0;
  for (const evt of events) {
    const ts = asNumber(evt.timestamp, 0) * 1000;
    if (ts > lastOnlineAt) {
      lastOnlineAt = ts;
    }
    if (isAttackEventId(String(evt.eventid ?? "")) && ts > lastAttackAt) {
      lastAttackAt = ts;
    }
  }

  const onlineGraceMs = 45_000;
  const attackCooldownMs = 90_000;
  const activeFreshnessMs = 90_000;
  const cooldownUntil = lastAttackAt > 0 ? lastAttackAt + attackCooldownMs : 0;
  const online = lastOnlineAt > 0 && (now - lastOnlineAt) <= onlineGraceMs;
  const underAttack = online && cooldownUntil > 0 && now <= cooldownUntil;
  const state: WarRoomStateKind = !online ? "offline" : (underAttack ? "under_attack" : "live");
  const source: SourceKind = truth.authoritative === false ? "runtime" : "clickhouse";

  return {
    ok: truth.ok ?? true,
    state,
    lastOnlineAt: lastOnlineAt || null,
    lastAttackAt: lastAttackAt || null,
    cooldownUntil: cooldownUntil || null,
    updatedAt: now,
    degraded: false,
    authoritative: truth.authoritative ?? false,
    source,
    sourceBreakdown: {
      state: source,
      onlineEvidence: "clickhouse",
      attackEvidence: "clickhouse",
      storage: "compat",
    },
    windows: {
      onlineGraceMs,
      attackCooldownMs,
      activeFreshnessMs,
    },
  };
}

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
      if (response.status === 404 || response.status === 405) {
        try {
          const compat = await loadCompatibilityWarRoomState(baseUrl, token);
          return NextResponse.json(compat, { status: 200 });
        } catch (compatError) {
          console.warn("[cloudsentinel/war-room-state] compatibility fallback failed", {
            error: compatError instanceof Error ? compatError.message : "fallback failed",
            baseUrl,
          });
        }
      }
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
