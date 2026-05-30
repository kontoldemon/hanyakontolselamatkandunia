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

  // Credentials are correct. Generate a 6-digit OTP.
  const otp = crypto.randomInt(100000, 999999).toString();
  
  // Hash the OTP securely
  const otpSecret = process.env.OTP_SECRET || process.env.DASHBOARD_PASSWORD || "default-secret";
  const otpHash = crypto.createHmac("sha256", otpSecret).update(otp).digest("hex");

  // Send the email using Resend
  const adminEmail = process.env.ADMIN_EMAIL;
  if (resend && adminEmail) {
    try {
      const { data, error } = await resend.emails.send({
        from: "CloudSentinel <onboarding@resend.dev>", // Must use onboarding@resend.dev for unverified domains
        to: [adminEmail],
        subject: "CloudSentinel - Dashboard Verification Code",
        html: `
          <!DOCTYPE html>
          <html>
          <head>
            <meta name="color-scheme" content="light dark">
            <meta name="supported-color-schemes" content="light dark">
            <style>
              @media (prefers-color-scheme: dark) {
                .bg-main { background-color: #050505 !important; color: #f1f5f9 !important; border-color: #1e293b !important; }
                .text-title { color: #ffffff !important; }
                .text-sub { color: #94a3b8 !important; }
                .bg-card { background-color: #0a0a0a !important; border-color: #1e293b !important; }
                .text-body { color: #cbd5e1 !important; }
                .bg-code { background: linear-gradient(145deg, #1e3a8a, #172554) !important; border-color: #1d4ed8 !important; box-shadow: inset 0 0 15px rgba(37,99,235,0.2) !important; }
                .text-code { color: #60a5fa !important; text-shadow: 0 0 10px rgba(96,165,250,0.5) !important; }
                .border-divider { border-top-color: #1e293b !important; }
              }
            </style>
          </head>
          <body>
            <div class="bg-main" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px; background-color: #ffffff; color: #0f172a; border-radius: 16px; border: 1px solid #e2e8f0; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);">
              <div style="text-align: center; margin-bottom: 30px;">
                <div style="display: inline-block; padding: 12px; background-color: #2563eb; border-radius: 12px; margin-bottom: 16px; box-shadow: 0 0 20px rgba(37, 99, 235, 0.4);">
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>
                </div>
                <h1 class="text-title" style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: #0f172a;">CloudSentinel</h1>
                <p class="text-sub" style="margin: 8px 0 0 0; font-size: 14px; color: #64748b;">Security Dashboard Verification</p>
              </div>
              
              <div class="bg-card" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; text-align: center; margin-bottom: 24px;">
                <p class="text-body" style="margin: 0 0 24px 0; font-size: 15px; color: #334155; line-height: 1.6;">A sign-in attempt was detected for your CloudSentinel administrator account. Use the authorization code below to proceed.</p>
                
                <div class="bg-code" style="background: linear-gradient(145deg, #eff6ff, #dbeafe); border: 1px solid #bfdbfe; padding: 24px; border-radius: 8px; margin: 0 auto; max-width: 300px; box-shadow: inset 0 0 15px rgba(37,99,235,0.05);">
                  <span class="text-code" style="font-family: monospace; font-size: 36px; font-weight: 800; letter-spacing: 12px; color: #2563eb; text-shadow: 0 0 10px rgba(37,99,235,0.2); margin-left: 12px;">${otp}</span>
                </div>
                
                <p class="text-sub" style="margin: 24px 0 0 0; font-size: 13px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Code expires in 5 minutes</p>
              </div>
              
              <div class="border-divider" style="text-align: center; border-top: 1px solid #e2e8f0; padding-top: 24px;">
                <p class="text-sub" style="margin: 0; font-size: 12px; color: #64748b; line-height: 1.5;">If you did not request this authorization code, your dashboard may be under attack.<br/>You can safely ignore this email, but consider rotating your credentials.</p>
              </div>
            </div>
          </body>
          </html>
        `
      });
      
      if (error) {
        console.error("Resend API Error:", error);
      } else {
        console.log("OTP Email sent successfully:", data);
      }
    } catch (e) {
      console.error("Failed to send OTP email exception:", e);
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
