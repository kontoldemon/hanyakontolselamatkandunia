import { proxyAdminGet } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return proxyAdminGet("/decoys");
}
