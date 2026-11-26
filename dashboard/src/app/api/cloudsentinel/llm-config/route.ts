import { proxyAdminGet, proxyAdminPost } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return proxyAdminGet("/llm/config");
}

export async function POST(request: Request) {
  return proxyAdminPost(request, "/llm/config");
}
