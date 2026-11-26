import { proxyAdminGet, proxyAdminPost } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return proxyAdminGet("/runtime-config");
}

export async function POST(request: Request) {
  return proxyAdminPost(request, "/runtime-config");
}
