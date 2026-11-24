export function GET() {
  return Response.json(
    { status: "ok", service: "dealmind-web" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
