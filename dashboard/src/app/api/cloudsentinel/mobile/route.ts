import { NextResponse } from "next/server";
import { adminApiConfig, adminApiConfigError } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(path: string, init: RequestInit): Promise<NextResponse> {
  const configError = adminApiConfigError();
  if (configError) return configError;
  const { baseUrl, headers } = adminApiConfig();
  try {
    const response = await fetch(new URL(path, baseUrl), {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...headers },
      signal: AbortSignal.timeout(6000),
    });
    const data = await response.json().catch(() => ({}));
    return NextResponse.json(
      response.ok ? data : { ok: false, error: data.detail ?? data.error ?? response.statusText },
      { status: 200 },
    );
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "sensor admin API unreachable" },
      { status: 200 },
    );
  }
}

function defaultSensorUrl(): string {
  const configured = process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_URL?.trim()
    || process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim()
    || "";
  if (!configured) return "";
  try {
    const url = new URL(configured);
    return `${url.protocol}//${url.host}`;
  } catch {
    return "";
  }
}

export async function GET() {
  const response = await proxy("/mobile/config", { method: "GET" });
  const payload = await response.json().catch(() => ({}));
  return NextResponse.json(
    { ...payload, serverUrl: defaultSensorUrl() },
    { status: response.status },
  );
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const action = String(body.action || "config");

  if (action === "pairing-token") {
    return proxy("/mobile/pairing-token", {
      method: "POST",
      body: JSON.stringify({ serverUrl: String(body.serverUrl || "").trim() }),
    });
  }

  if (action === "test-alert") {
    const alert: Record<string, unknown> = {};
    if (body.ip) alert.ip = body.ip;
    if (body.country) alert.country = body.country;
    if (typeof body.riskScore === "number") alert.riskScore = body.riskScore;
    if (body.summary) alert.summary = body.summary;
    return proxy("/mobile/test-alert", {
      method: "POST",
      body: JSON.stringify(alert),
    });
  }

  return proxy("/mobile/config", {
    method: "POST",
    body: JSON.stringify(body.policy ?? body),
  });
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const deviceId = (searchParams.get("deviceId") || "").trim();
  if (!deviceId) {
    return NextResponse.json({ ok: false, error: "deviceId is required" }, { status: 400 });
  }
  return proxy(`/mobile/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" });
}
