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
    const response = await fetch(new URL("/threat-summary", baseUrl), {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
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
