import { getSystemStatus } from "@/features/system-status/snapshot";

export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json(await getSystemStatus(), {
    headers: { "Cache-Control": "no-store" },
  });
}
