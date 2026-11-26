import { NextResponse } from "next/server";

export type SourceKind = "clickhouse" | "runtime" | "memory" | "mixed";

export type AdminApiConfig = {
  baseUrl: string;
  headers: Record<string, string>;
};

export function toSafeNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function adminApiConfig(): AdminApiConfig {
  const baseUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN?.trim();
  if (!baseUrl) {
    throw new Error("CLOUDSENTINEL_ADMIN_API_URL is not configured");
  }
  if (!token) {
    throw new Error("CLOUDSENTINEL_ADMIN_TOKEN is not configured");
  }
  return {
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
  };
}

export function adminApiConfigError(): NextResponse | null {
  try {
    adminApiConfig();
    return null;
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "admin API is not configured",
      },
      { status: 503 },
    );
  }
}

export async function proxyAdminGet(
  upstreamPath: string,
  timeoutMs = 8000,
): Promise<NextResponse> {
  const configError = adminApiConfigError();
  if (configError) return configError;
  const { baseUrl, headers } = adminApiConfig();

  try {
    const response = await fetch(new URL(upstreamPath, baseUrl), {
      method: "GET",
      cache: "no-store",
      headers,
      signal: AbortSignal.timeout(timeoutMs),
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

export async function proxyAdminPost(
  request: Request,
  upstreamPath: string,
  timeoutMs = 8000,
): Promise<NextResponse> {
  const configError = adminApiConfigError();
  if (configError) return configError;
  const { baseUrl, headers } = adminApiConfig();

  try {
    const body = await request.json();
    const response = await fetch(new URL(upstreamPath, baseUrl), {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
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
