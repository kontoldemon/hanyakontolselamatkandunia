import { NextResponse } from "next/server";

export type AdminApiConfig = {
  baseUrl: string;
  headers: Record<string, string>;
};

export function adminApiConfig(): AdminApiConfig {
  const baseUrl = process.env.CLOUDSENTINEL_ADMIN_API_URL?.trim();
  const token = process.env.CLOUDSENTINEL_ADMIN_TOKEN?.trim();
  if (!baseUrl) {
    throw new Error("CLOUDSENTINEL_ADMIN_API_URL is not configured");
  }
  if (!token) {
    throw new Error("CLOUDSENTINEL_ADMIN_TOKEN is not configured");
  }
  return {
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
  };
}

export function adminApiConfigError(): NextResponse | null {
  try {
    adminApiConfig();
    return null;
  } catch (error) {
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "admin API is not configured",
      },
      { status: 503 },
    );
  }
}
