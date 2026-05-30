import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";

  try {
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL("/events?limit=100", baseUrl), {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      console.warn("[cloudsentinel/events] upstream request failed", {
        status: response.status,
        statusText: response.statusText,
        baseUrl,
      });
      return NextResponse.json(
        {
          ok: false,
          status: "offline",
          source: "runtime",
          authoritative: false,
          sourceBreakdown: { events: "runtime" },
          events: [],
          error: `upstream ${response.status} ${response.statusText}`,
        },
        { status: 200 },
      );
    }

    const data = await response.json() as {
      events?: unknown[];
      source?: string;
      authoritative?: boolean;
      sourceBreakdown?: Record<string, unknown>;
      ok?: boolean;
    };
    return NextResponse.json(
      {
        ok: data.ok ?? true,
        status: "live",
        source: data.source ?? "clickhouse",
        authoritative: data.authoritative ?? true,
        sourceBreakdown: data.sourceBreakdown ?? { events: "clickhouse" },
        events: data.events ?? [],
      },
      { status: 200 },
    );
  } catch (error) {
    console.error("[cloudsentinel/events] request exception", error);
    return NextResponse.json(
      {
        ok: false,
        status: "offline",
        source: "runtime",
        authoritative: false,
        sourceBreakdown: { events: "runtime" },
        events: [],
        error: error instanceof Error ? error.message : "request failed",
      },
      { status: 200 },
    );
  }
}
