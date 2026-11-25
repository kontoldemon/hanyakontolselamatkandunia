import { NextResponse } from "next/server";
import { randomBytes, randomInt } from "crypto";
import { adminApiConfig, adminApiConfigError } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type MobilePolicy = {
  enabled: boolean;
  minRiskScore: number;
  cooldownSeconds: number;
  notifyBruteForce: boolean;
  notifyCommandExec: boolean;
  notifySoarBlock: boolean;
};

type PairedDevice = {
  deviceId: string;
  deviceName: string;
  platform: string;
  hasFcmToken: boolean;
  pairedAtMs: number;
  lastSeenAtMs: number;
};

// Local runtime fallback store when Python Admin API is offline
let localPolicy: MobilePolicy = {
  enabled: true,
  minRiskScore: 70,
  cooldownSeconds: 60,
  notifyBruteForce: true,
  notifyCommandExec: true,
  notifySoarBlock: true,
};

let localDevices: PairedDevice[] = [];

async function proxyToAdminApi(path: string, init: RequestInit): Promise<Response | null> {
  if (adminApiConfigError()) {
    return null;
  }
  try {
    const { baseUrl, headers } = adminApiConfig();
    return await fetch(new URL(path, baseUrl), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...headers,
        ...(init.headers ?? {}),
      },
      signal: AbortSignal.timeout(4000),
    });
  } catch {
    return null;
  }
}

export async function GET() {
  const upstream = await proxyToAdminApi("/mobile/config", { method: "GET" });
  if (upstream && upstream.ok) {
    const data = await upstream.json();
    return NextResponse.json({ ...data, source: "sensor" });
  }
  return NextResponse.json({
    ok: true,
    policy: localPolicy,
    devices: localDevices,
    source: "local_fallback",
  });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
    const action = String(body.action || "config");

    if (action === "pairing-token") {
      const serverUrl = String(body.serverUrl || "").trim();
      const upstream = await proxyToAdminApi("/mobile/pairing-token", {
        method: "POST",
        body: JSON.stringify({ serverUrl }),
      });
      if (upstream && upstream.ok) {
        return NextResponse.json(await upstream.json());
      }
      const code = String(randomInt(100000, 999999));
      const token = randomBytes(18).toString("base64url");
      const ttlSeconds = 300;
      const expiresAtMs = Date.now() + ttlSeconds * 1000;
      const cleanUrl = serverUrl || "http://127.0.0.1:8080";
      return NextResponse.json({
        ok: true,
        pairingCode: code,
        pairingToken: token,
        serverUrl: cleanUrl,
        expiresAtMs,
        ttlSeconds,
        qrPayload: JSON.stringify({
          v: 1,
          serverUrl: cleanUrl,
          pairingCode: code,
          pairingToken: token,
        }),
        source: "local_fallback",
      });
    }

    if (action === "test-alert") {
      const upstream = await proxyToAdminApi("/mobile/test-alert", {
        method: "POST",
        body: JSON.stringify({
          ip: body.ip || "185.220.101.42",
          country: body.country || "Germany",
          riskScore: body.riskScore ?? 92,
          summary: body.summary || "Test DEFCON alert triggered from CloudSentinel Web Settings",
        }),
      });
      if (upstream && upstream.ok) {
        return NextResponse.json(await upstream.json());
      }
      return NextResponse.json({
        ok: true,
        dispatched: localDevices.length,
        mode: "local_fallback",
        message: "Test alert queued locally (sensor admin API offline).",
      });
    }

    // Default: update policy config
    const policyUpdates = (body.policy ?? body) as Partial<MobilePolicy>;
    localPolicy = {
      ...localPolicy,
      ...policyUpdates,
      minRiskScore: Math.max(0, Math.min(100, Number(policyUpdates.minRiskScore ?? localPolicy.minRiskScore))),
      cooldownSeconds: Math.max(0, Math.min(3600, Number(policyUpdates.cooldownSeconds ?? localPolicy.cooldownSeconds))),
    };

    const upstream = await proxyToAdminApi("/mobile/config", {
      method: "POST",
      body: JSON.stringify(localPolicy),
    });
    if (upstream && upstream.ok) {
      return NextResponse.json(await upstream.json());
    }
    return NextResponse.json({
      ok: true,
      policy: localPolicy,
      devices: localDevices,
      source: "local_fallback",
    });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "Mobile API request failed" },
      { status: 400 },
    );
  }
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const deviceId = (searchParams.get("deviceId") || "").trim();
  if (!deviceId) {
    return NextResponse.json({ ok: false, error: "deviceId is required" }, { status: 400 });
  }
  const upstream = await proxyToAdminApi(`/mobile/devices/${encodeURIComponent(deviceId)}`, {
    method: "DELETE",
  });
  if (upstream && upstream.ok) {
    return NextResponse.json(await upstream.json());
  }
  localDevices = localDevices.filter((d) => d.deviceId !== deviceId);
  return NextResponse.json({
    ok: true,
    deviceId,
    devices: localDevices,
    source: "local_fallback",
  });
}
