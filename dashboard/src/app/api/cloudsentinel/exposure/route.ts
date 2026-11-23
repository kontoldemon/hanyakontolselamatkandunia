import { proxyAdminPost } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  return proxyAdminPost(request, "/admin/exposure");
}
