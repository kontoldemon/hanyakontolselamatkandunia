import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const envUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const baseUrl = envUrl && envUrl !== "http://localhost:8080" ? envUrl : "https://188.166.184.42.sslip.io";

  try {
    const body = await request.json();
    const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN;
    const response = await fetch(new URL("/llm/chat", baseUrl), {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });

    if (response.status === 401) {
      // Auth token mismatch — try without token as fallback
      const retryResponse = await fetch(new URL("/llm/chat", baseUrl), {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30000),
      });
      if (retryResponse.ok) {
        return NextResponse.json(await retryResponse.json());
      }
      return NextResponse.json(
        { ok: false, error: "auth_failed" },
        { status: 200 },
      );
    }

    if (!response.ok) {
      return NextResponse.json(
        { ok: false, error: `${response.status} ${response.statusText}` },
        { status: 200 },
      );
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "request failed" },
      { status: 200 },
    );
  }
}

