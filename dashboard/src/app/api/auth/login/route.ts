import { NextResponse } from "next/server";
import { constantTimeEqual, hasAuthConfig } from "@/lib/auth";
import {
  buildOtpEmailHtml,
  computeOtpHash,
  OTP_HASH_COOKIE,
  parseCookieFailures,
} from "@/lib/otpAuth";
import crypto from "crypto";
import { Resend } from "resend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FAILURE_COOKIE = "cloudsentinel_login_failures";
const FAILURE_WINDOW_SECONDS = 60 * 10;
const MAX_FAILURES = 5;

const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null;

function failedResponse(failures: number) {
  const nextFailures = Math.min(failures + 1, MAX_FAILURES);
  const response = NextResponse.json({ ok: false, error: "invalid credentials" }, { status: 401 });
  response.cookies.set({
    name: FAILURE_COOKIE,
    value: String(nextFailures),
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/api/auth/login",
    maxAge: FAILURE_WINDOW_SECONDS,
  });
  return response;
}

function clearFailures(response: NextResponse) {
  response.cookies.set({
    name: FAILURE_COOKIE,
    value: "",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/api/auth/login",
    maxAge: 0,
  });
}

function wait(ms: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export async function POST(request: Request) {
  if (!hasAuthConfig()) {
    return NextResponse.json(
      { ok: false, error: "dashboard auth is not configured" },
      { status: 503 },
    );
  }

  const body = await request.json().catch(() => ({}));
  const username = String(body.username ?? "");
  const password = String(body.password ?? "");
  const turnstileToken = String(body.turnstileToken ?? "");
  const failures = parseCookieFailures(
    request.headers.get("cookie")?.match(/cloudsentinel_login_failures=(\d+)/)?.[1],
  );

  if (failures >= MAX_FAILURES) {
    await wait(1000);
    return NextResponse.json(
      { ok: false, error: "too many failed attempts" },
      { status: 429 },
    );
  }

  if (!turnstileToken) {
    return NextResponse.json({ ok: false, error: "captcha is required" }, { status: 400 });
  }

  const configuredSecret = process.env.TURNSTILE_SECRET_KEY;
  let secretKey: string;
  if (configuredSecret) {
    secretKey = configuredSecret;
  } else if (process.env.NODE_ENV !== "production") {
    secretKey = "1x0000000000000000000000000000000AA";
  } else {
    return NextResponse.json(
      { ok: false, error: "captcha is not configured" },
      { status: 503 },
    );
  }
  const formData = new URLSearchParams();
  formData.append("secret", secretKey);
  formData.append("response", turnstileToken);

  try {
    const turnstileRes = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: formData,
      signal: AbortSignal.timeout(8000),
    });
    const turnstileData = await turnstileRes.json();

    if (!turnstileData.success) {
      return NextResponse.json({ ok: false, error: "captcha verification failed" }, { status: 400 });
    }
  } catch {
    return NextResponse.json({ ok: false, error: "captcha service unavailable" }, { status: 500 });
  }

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(password, process.env.DASHBOARD_PASSWORD || "")
  ) {
    await wait(650);
    return failedResponse(failures);
  }

  const otp = crypto.randomInt(100000, 999999).toString();
  const otpHash = computeOtpHash(otp);

  const adminEmail = process.env.ADMIN_EMAIL;
  if (resend && adminEmail) {
    try {
      const { error } = await resend.emails.send({
        from: "CloudSentinel <onboarding@resend.dev>",
        to: [adminEmail],
        subject: "CloudSentinel - Dashboard Verification Code",
        html: buildOtpEmailHtml(otp),
      });

      if (error) {
        console.error("Resend API Error:", error);
        return NextResponse.json(
          { ok: false, error: "verification email could not be sent" },
          { status: 503 },
        );
      }
    } catch (e) {
      console.error("Failed to send OTP email exception:", e);
      return NextResponse.json(
        { ok: false, error: "verification email could not be sent" },
        { status: 503 },
      );
    }
  } else if (process.env.NODE_ENV !== "production") {
    console.log(`\n\n[CloudSentinel Auth] RESEND_API_KEY not found. OTP for ${username} is: ${otp}\n\n`);
  } else {
    return NextResponse.json(
      { ok: false, error: "OTP delivery is not configured" },
      { status: 503 },
    );
  }

  const response = NextResponse.json({
    ok: true,
    requireOtp: true,
    message: "OTP sent to your registered email address.",
  });

  clearFailures(response);

  response.cookies.set({
    name: OTP_HASH_COOKIE,
    value: otpHash,
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 5 * 60,
  });

  return response;
}
