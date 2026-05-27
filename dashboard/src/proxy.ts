import { NextRequest, NextResponse } from "next/server";
import { sessionCookieName, verifySessionToken } from "@/lib/auth";

const publicPaths = [
  "/signin",
  "/api/auth/login",
  "/api/auth/logout",
  "/505",
  "/favicon.ico",
  "/logo.svg",
  "/file.svg",
  "/globe.svg",
  "/next.svg",
  "/vercel.svg",
  "/window.svg",
  "/world-atlas.json",
  "/sw.js",
];

function securityHeaders(response: NextResponse) {
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  response.headers.set("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'self'; form-action 'self'");
  response.headers.set("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload");
  return response;
}

function isPublicPath(pathname: string) {
  return (
    publicPaths.includes(pathname) ||
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/api/auth/")
  );
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/signin") {
    const session = await verifySessionToken(request.cookies.get(sessionCookieName())?.value);
    if (session) {
      const url = request.nextUrl.clone();
      url.pathname = "/";
      url.search = "";
      return securityHeaders(NextResponse.redirect(url));
    }
    return securityHeaders(NextResponse.next());
  }

  if (isPublicPath(pathname)) {
    return securityHeaders(NextResponse.next());
  }

  const session = await verifySessionToken(request.cookies.get(sessionCookieName())?.value);
  if (session) {
    return securityHeaders(NextResponse.next());
  }

  if (pathname.startsWith("/api/")) {
    return securityHeaders(NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 }));
  }

  const url = request.nextUrl.clone();
  url.pathname = "/signin";
  url.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
  return securityHeaders(NextResponse.redirect(url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
