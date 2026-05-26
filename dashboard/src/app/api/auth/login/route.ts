import { NextResponse } from "next/server";
import {
  constantTimeEqual,
  createSessionToken,
  hasAuthConfig,
  sessionCookieName,
  sessionMaxAge,
} from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FAILURE_COOKIE = "cloudsentinel_login_failures";
const FAILURE_WINDOW_SECONDS = 60 * 10;
const MAX_FAILURES = 5;

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
  const failures = parseFailures(request.headers.get("cookie")?.match(/cloudsentinel_login_failures=(\d+)/)?.[1]);

  if (failures >= MAX_FAILURES) {
    await wait(1000);
    return NextResponse.json(
      { ok: false, error: "too many failed attempts" },
      { status: 429 },
    );
  }

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(password, process.env.DASHBOARD_PASSWORD || "")
  ) {
    await wait(650);
    return failedResponse(failures);
  }

  const token = await createSessionToken(username);
  const response = NextResponse.json({ ok: true });
  clearFailures(response);
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
