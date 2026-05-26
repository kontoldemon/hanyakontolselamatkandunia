const SESSION_COOKIE = "cloudsentinel_session";
const SESSION_TTL_SECONDS = 60 * 60 * 8;

type SessionPayload = {
  username: string;
  exp: number;
};

function base64UrlEncode(value: string) {
  return btoa(value).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value: string) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(
    Math.ceil(value.length / 4) * 4,
    "=",
  );
  return atob(padded);
}

function authSecret() {
  return process.env.DASHBOARD_AUTH_SECRET || process.env.AUTH_SECRET || "";
}

export function constantTimeEqual(left: string, right: string) {
  const leftBytes = new TextEncoder().encode(left);
  const rightBytes = new TextEncoder().encode(right);
  const maxLength = Math.max(leftBytes.length, rightBytes.length);
  let difference = leftBytes.length ^ rightBytes.length;

  for (let index = 0; index < maxLength; index += 1) {
    difference |= (leftBytes[index] ?? 0) ^ (rightBytes[index] ?? 0);
  }

  return difference === 0;
}

async function hmac(message: string, secret: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  const bytes = Array.from(new Uint8Array(signature));
  return base64UrlEncode(String.fromCharCode(...bytes));
}

export function sessionCookieName() {
  return SESSION_COOKIE;
}

export function hasAuthConfig() {
  return Boolean(authSecret() && process.env.DASHBOARD_USERNAME && process.env.DASHBOARD_PASSWORD);
}

export async function createSessionToken(username: string) {
  const secret = authSecret();
  if (!secret) {
    throw new Error("DASHBOARD_AUTH_SECRET is not configured");
  }
  const payload: SessionPayload = {
    username,
    exp: Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS,
  };
  const encodedPayload = base64UrlEncode(JSON.stringify(payload));
  return `${encodedPayload}.${await hmac(encodedPayload, secret)}`;
}

export async function verifySessionToken(token?: string | null) {
  const secret = authSecret();
  if (!token || !secret) {
    return null;
  }

  const [encodedPayload, signature] = token.split(".");
  if (!encodedPayload || !signature) {
    return null;
  }

  const expected = await hmac(encodedPayload, secret);
  if (!constantTimeEqual(signature, expected)) {
    return null;
  }

  try {
    const payload = JSON.parse(base64UrlDecode(encodedPayload)) as SessionPayload;
    if (!payload.username || payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

export function sessionMaxAge() {
  return SESSION_TTL_SECONDS;
}
