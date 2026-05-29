import { NextResponse } from "next/server";
import {
  constantTimeEqual,
  hasAuthConfig,
} from "@/lib/auth";
import crypto from "crypto";
import { Resend } from "resend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FAILURE_COOKIE = "cloudsentinel_login_failures";
const OTP_HASH_COOKIE = "cloudsentinel_otp_hash";
const FAILURE_WINDOW_SECONDS = 60 * 10;
const MAX_FAILURES = 5;

// Initialize Resend
const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null;

function parseFailures(value?: string) {
  if (!value) {
    return 0;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0;
}

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
  const failures = parseFailures(request.headers.get("cookie")?.match(/cloudsentinel_login_failures=(\d+)/)?.[1]);

  if (failures >= MAX_FAILURES) {
    await wait(1000);
    return NextResponse.json(
      { ok: false, error: "too many failed attempts" },
      { status: 429 },
    );
  }

  // Turnstile Verification
  if (!turnstileToken) {
    return NextResponse.json({ ok: false, error: "captcha is required" }, { status: 400 });
  }

  // Verify with Cloudflare
  const secretKey = process.env.TURNSTILE_SECRET_KEY || "1x0000000000000000000000000000000AA";
  const formData = new URLSearchParams();
  formData.append("secret", secretKey);
  formData.append("response", turnstileToken);
  
  try {
    const turnstileRes = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { 
      method: "POST", 
      body: formData 
    });
    const turnstileData = await turnstileRes.json();
    
    if (!turnstileData.success) {
      return NextResponse.json({ ok: false, error: "captcha verification failed" }, { status: 400 });
    }
  } catch (e) {
    return NextResponse.json({ ok: false, error: "captcha service unavailable" }, { status: 500 });
  }

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(password, process.env.DASHBOARD_PASSWORD || "")
  ) {
    await wait(650);
    return failedResponse(failures);
  }

  // Credentials are correct. Generate a 6-digit OTP.
  const otp = crypto.randomInt(100000, 999999).toString();
  
  // Hash the OTP securely
  const otpSecret = process.env.OTP_SECRET || process.env.DASHBOARD_PASSWORD || "default-secret";
  const otpHash = crypto.createHmac("sha256", otpSecret).update(otp).digest("hex");

  // Send the email using Resend
  const adminEmail = process.env.ADMIN_EMAIL;
  if (resend && adminEmail) {
    try {
      await resend.emails.send({
        from: "CloudSentinel <security@cloudsentinel.dev>", // Or a verified domain you own on Resend
        to: [adminEmail],
        subject: "CloudSentinel - Dashboard Verification Code",
        html: `
          <div style="font-family: sans-serif; max-w-md: 600px; margin: 0 auto; padding: 20px;">
            <h2>CloudSentinel Dashboard Access</h2>
            <p>A sign-in attempt was made to your CloudSentinel dashboard. Use the verification code below to proceed:</p>
            <div style="background-color: #f3f4f6; padding: 24px; border-radius: 8px; text-align: center; margin: 24px 0;">
              <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2563eb;">${otp}</span>
            </div>
            <p style="color: #6b7280; font-size: 14px;">If you did not request this code, you can safely ignore this email.</p>
          </div>
        `
      });
    } catch (e) {
      console.error("Failed to send OTP email:", e);
    }
  } else {
    // Fallback for development if no Resend key is provided
    console.log(`\n\n[CloudSentinel Auth] RESEND_API_KEY not found. OTP for ${username} is: ${otp}\n\n`);
  }

  const response = NextResponse.json({ 
    ok: true, 
    requireOtp: true, 
    message: "OTP sent to your registered email address." 
  });
  
  clearFailures(response);

  // Set the OTP hash in an HttpOnly cookie valid for 5 minutes
  response.cookies.set({
    name: OTP_HASH_COOKIE,
    value: otpHash,
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 5 * 60, // 5 minutes
  });

  return response;
}
