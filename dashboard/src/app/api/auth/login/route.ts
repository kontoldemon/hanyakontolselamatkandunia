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

  if (
    !constantTimeEqual(username, process.env.DASHBOARD_USERNAME || "") ||
    !constantTimeEqual(password, process.env.DASHBOARD_PASSWORD || "")
  ) {
    return NextResponse.json({ ok: false, error: "invalid credentials" }, { status: 401 });
  }

  const token = await createSessionToken(username);
  const response = NextResponse.json({ ok: true });
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
