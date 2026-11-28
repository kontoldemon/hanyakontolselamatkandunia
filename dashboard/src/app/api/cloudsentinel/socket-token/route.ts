import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const token =
    process.env.CLOUDSENTINEL_STREAM_TOKEN?.trim()
    || process.env.NEXT_PUBLIC_CLOUDSENTINEL_SOCKET_TOKEN?.trim()
    || "";
  return NextResponse.json({ token });
}
