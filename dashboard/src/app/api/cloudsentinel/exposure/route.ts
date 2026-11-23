import { NextResponse } from "next/server";
import { adminApiConfig, adminApiConfigError } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const configError = adminApiConfigError();
  if (configError) return configError;
  const { baseUrl, headers } = adminApiConfig();

  try {
    const body = await request.json();
    const response = await fetch(new URL("/admin/exposure", baseUrl), {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    });
    const data = await response.json().catch(() => ({}));
    return NextResponse.json(
      response.ok ? data : { ok: false, error: data.detail ?? data.error ?? response.statusText },
      { status: 200 },
    );
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "request failed" },
      { status: 200 },
    );
  }
}
