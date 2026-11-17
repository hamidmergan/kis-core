import { NextRequest } from "next/server";
import { sseResponse } from "../../_sse";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ uuid: string }> },
) {
  const { uuid } = await params;
  const body = await req.text();

  const upstream = await fetch(
    `${BACKEND}/ai-assistant/workspaces/${uuid}/chat`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        cookie: req.headers.get("cookie") || "",
      },
      body,
      // Passes the cancellation through so the backend closes the stream.
      signal: req.signal,
    },
  );

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), { status: upstream.status });
  }

  return sseResponse(upstream.body);
}
