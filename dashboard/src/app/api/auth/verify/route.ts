import { NextResponse } from "next/server";
import {
  constantTimeEqual,
  createSessionToken,
  hasAuthConfig,
  sessionCookieName,
  sessionMaxAge,
} from "@/lib/auth";
import crypto from "crypto";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const OTP_HASH_COOKIE = "cloudsentinel_otp_hash";

export async function POST(request: Request) {
  if (!hasAuthConfig()) {
    return NextResponse.json(
      { ok: false, error: "dashboard auth is not configured" },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const username = String(body.username ?? "");
  const otp = String(body.otp ?? "");
  
  // Retrieve the stored OTP hash cookie
  const cookieHeader = request.headers.get("cookie");
  const storedOtpHash = cookieHeader?.match(new RegExp(`${OTP_HASH_COOKIE}=([^;]+)`))?.[1];

  if (!storedOtpHash) {
    return NextResponse.json({ ok: false, error: "OTP expired or missing" }, { status: 401 });
  }

  // Hash the incoming OTP using the same secret
  const otpSecret = process.env.OTP_SECRET || process.env.DASHBOARD_PASSWORD || "default-secret";
  const incomingOtpHash = crypto.createHmac("sha256", otpSecret).update(otp).digest("hex");

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(incomingOtpHash, storedOtpHash)
  ) {
    // Wait slightly to prevent timing attacks
    await new Promise((resolve) => setTimeout(resolve, 650));
    return NextResponse.json({ ok: false, error: "invalid verification code" }, { status: 401 });
  }

  const token = await createSessionToken(username);
  const response = NextResponse.json({ ok: true });
  
  // Clear the OTP cookie
  response.cookies.set({
    name: OTP_HASH_COOKIE,
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

  // Set the actual session cookie
  response.cookies.set({
    name: sessionCookieName(),
    value: token,
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: sessionMaxAge(),
  });
  
  return response;
}
