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
      signal: AbortSignal.timeout(15000),
    });

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
