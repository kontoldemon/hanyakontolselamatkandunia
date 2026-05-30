import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type CloudSentinelEvent = {
  timestamp?: number | string;
  src_ip?: string;
  input?: string;
  reason?: string;
  eventid?: string;
  cloudsentinel_soar_action?: string;
  mttb_ms?: number;
};

type TimeBucket = {
  time: number;
  totalEvents: number;
  blockedEvents: number;
  mttbSum: number;
  mttbCount: number;
  sshCount: number;
  cmdCount: number;
  webCount: number;
  otherCount: number;
  uniqueIps: Set<string>;
  payloadSize: number;
};

function parseEpochMs(raw: unknown): number {
  if (typeof raw === "number") {
    return raw > 1_000_000_000_000 ? raw : raw * 1000;
  }
  if (typeof raw === "string" && raw.trim()) {
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) {
      return numeric > 1_000_000_000_000 ? numeric : numeric * 1000;
    }
    const parsed = Date.parse(raw);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return Date.now();
}

function classifyType(eventid = ""): "ssh" | "cmd" | "web" | "other" {
  const normalized = eventid.toLowerCase();
  if (normalized.includes("login.failed")) return "ssh";
  if (normalized.includes("command")) return "cmd";
  if (normalized.includes("web")) return "web";
  return "other";
}

function payloadSize(event: CloudSentinelEvent): number {
  const value = (event.input || event.reason || "").trim();
  return value.length;
}

function resolveWindowMs(raw: string | null): number | null {
  const normalized = (raw || "24h").trim().toLowerCase();
  if (normalized === "all") return null;
  if (normalized === "15m") return 15 * 60 * 1000;
  if (normalized === "1h") return 60 * 60 * 1000;
  if (normalized === "6h") return 6 * 60 * 60 * 1000;
  if (normalized === "7d") return 7 * 24 * 60 * 60 * 1000;
  return 24 * 60 * 60 * 1000;
}

function resolveBucketMs(windowMs: number | null): number {
  if (windowMs === null) return 30 * 60 * 1000;
  if (windowMs <= 60 * 60 * 1000) return 15 * 1000;
  if (windowMs <= 6 * 60 * 60 * 1000) return 60 * 1000;
  if (windowMs <= 24 * 60 * 60 * 1000) return 2 * 60 * 1000;
  if (windowMs <= 3 * 24 * 60 * 60 * 1000) return 5 * 60 * 1000;
  return 15 * 60 * 1000;
}

function resolveEventLimit(windowMs: number | null): number {
  if (windowMs === null) return 20000;
  if (windowMs <= 60 * 60 * 1000) return 1200;
  if (windowMs <= 6 * 60 * 60 * 1000) return 2400;
  if (windowMs <= 24 * 60 * 60 * 1000) return 4000;
  return 8000;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const window = searchParams.get("window");
  const windowMs = resolveWindowMs(window);

  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";
  const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
  const headers: HeadersInit | undefined = token ? { Authorization: `Bearer ${token}` } : undefined;

  try {
    const limit = resolveEventLimit(windowMs);
    const response = await fetch(new URL(`/events?limit=${limit}`, baseUrl), {
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(9000),
    });
    if (!response.ok) {
      return NextResponse.json({
        ok: false,
        status: "offline",
        source: "runtime",
        authoritative: false,
        sourceBreakdown: { series: "runtime" },
        sampledAt: new Date().toISOString(),
        series: [],
      });
    }

    const payload = (await response.json()) as { events?: CloudSentinelEvent[] };
    const events = payload.events ?? [];
    if (events.length === 0) {
      return NextResponse.json({
        ok: true,
        status: "live",
        source: "clickhouse",
        authoritative: true,
        sourceBreakdown: { series: "clickhouse" },
        sampledAt: new Date().toISOString(),
        series: [],
      });
    }

    const now = Date.now();
    const cutoff = windowMs === null ? 0 : now - windowMs;
    const bucketMs = resolveBucketMs(windowMs);
    const buckets = new Map<number, TimeBucket>();

    for (const event of events) {
      const epochMs = parseEpochMs(event.timestamp);
      if (epochMs < cutoff) continue;
      const bucketKey = Math.floor(epochMs / bucketMs) * bucketMs;
      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, {
          time: bucketKey,
          totalEvents: 0,
          blockedEvents: 0,
          mttbSum: 0,
          mttbCount: 0,
          sshCount: 0,
          cmdCount: 0,
          webCount: 0,
          otherCount: 0,
          uniqueIps: new Set<string>(),
          payloadSize: 0,
        });
      }
      const target = buckets.get(bucketKey)!;
      target.totalEvents += 1;
      const action = (event.cloudsentinel_soar_action ?? "").toLowerCase();
      const isBlocked = action.includes("block");
      if (isBlocked) {
        target.blockedEvents += 1;
      }
      const mttb = Number(event.mttb_ms);
      if (Number.isFinite(mttb) && mttb > 0) {
        target.mttbSum += mttb;
        target.mttbCount += 1;
      }
      const cls = classifyType(event.eventid);
      if (cls === "ssh") target.sshCount += 1;
      else if (cls === "cmd") target.cmdCount += 1;
      else if (cls === "web") target.webCount += 1;
      else target.otherCount += 1;
      if (event.src_ip) {
        target.uniqueIps.add(event.src_ip);
      }
      target.payloadSize += payloadSize(event);
    }

    const series = [...buckets.values()]
      .sort((a, b) => a.time - b.time)
      .slice(-400)
      .map((bucket) => ({
        time: bucket.time,
        timeLabel: new Date(bucket.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        totalEvents: bucket.totalEvents,
        blockedEvents: bucket.blockedEvents,
        mttbAvg: bucket.mttbCount > 0 ? Number((bucket.mttbSum / bucket.mttbCount).toFixed(2)) : 0,
        sshCount: bucket.sshCount,
        cmdCount: bucket.cmdCount,
        webCount: bucket.webCount,
        otherCount: bucket.otherCount,
        uniqueIpCount: bucket.uniqueIps.size,
        payloadKb: Number((bucket.payloadSize / 1024).toFixed(2)),
      }));

    return NextResponse.json({
      ok: true,
      status: "live",
      source: "clickhouse",
      authoritative: true,
      sourceBreakdown: { series: "clickhouse" },
      sampledAt: new Date().toISOString(),
      window,
      windowMs: windowMs ?? "all",
      bucketMs,
      series,
    });
  } catch (error) {
    return NextResponse.json({
      ok: false,
      status: "offline",
      source: "runtime",
      authoritative: false,
      sourceBreakdown: { series: "runtime" },
      sampledAt: new Date().toISOString(),
      error: error instanceof Error ? error.message : "request failed",
      series: [],
    });
  }
}
