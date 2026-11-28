import { NextResponse } from "next/server";
import {
  constantTimeEqual,
  createSessionToken,
  hasAuthConfig,
  sessionCookieName,
  sessionMaxAge,
} from "@/lib/auth";
import {
  computeOtpHash,
  hasOtpSecret,
  OTP_HASH_COOKIE,
  parseCookieFailures,
} from "@/lib/otpAuth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FAILURE_COOKIE = "cloudsentinel_otp_failures";
const MAX_FAILURES = 5;
const FAILURE_WINDOW_SECONDS = 5 * 60;

function clearOtp(response: NextResponse) {
  response.cookies.set({
    name: OTP_HASH_COOKIE,
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}

function setFailures(response: NextResponse, count: number) {
  response.cookies.set({
    name: FAILURE_COOKIE,
    value: String(Math.min(count, MAX_FAILURES)),
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: FAILURE_WINDOW_SECONDS,
  });
}

export async function POST(request: Request) {
  if (!hasAuthConfig()) {
    return NextResponse.json(
      { ok: false, error: "dashboard auth is not configured" },
      { status: 503 },
    );
  }
  if (!hasOtpSecret()) {
    return NextResponse.json(
      { ok: false, error: "OTP secret is not configured" },
      { status: 503 },
    );
  }

  const cookieHeader = request.headers.get("cookie");
  const failures = parseCookieFailures(
    cookieHeader?.match(new RegExp(`${FAILURE_COOKIE}=(\\d+)`))?.[1],
  );

  if (failures >= MAX_FAILURES) {
    const response = NextResponse.json(
      { ok: false, error: "too many verification attempts" },
      { status: 429 },
    );
    clearOtp(response);
    return response;
  }

  const body = await request.json().catch(() => ({}));
  const username = String(body.username ?? "");
  const otp = String(body.otp ?? "");

  const storedOtpHash = cookieHeader?.match(new RegExp(`${OTP_HASH_COOKIE}=([^;]+)`))?.[1];

  if (!storedOtpHash) {
    return NextResponse.json({ ok: false, error: "OTP expired or missing" }, { status: 401 });
  }

  const incomingOtpHash = computeOtpHash(otp);

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(incomingOtpHash, storedOtpHash)
  ) {
    await new Promise((resolve) => setTimeout(resolve, 650));
    const nextFailures = failures + 1;
    const response = NextResponse.json(
      { ok: false, error: "invalid verification code" },
      { status: nextFailures >= MAX_FAILURES ? 429 : 401 },
    );
    setFailures(response, nextFailures);
    if (nextFailures >= MAX_FAILURES) {
      clearOtp(response);
    }
    return response;
  }

  const token = await createSessionToken(username);
  const response = NextResponse.json({ ok: true });

  clearOtp(response);
  response.cookies.set({
    name: FAILURE_COOKIE,
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });

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
