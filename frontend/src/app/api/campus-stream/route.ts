import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

/** Pipes the campus chat stream through, the same way the assistant stream does. */
export async function POST(req: NextRequest) {
  const body = await req.text();

  const upstream = await fetch(`${BACKEND}/campus/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      cookie: req.headers.get("cookie") || "",
      "Accept-Language": req.headers.get("accept-language") || "",
    },
    body,
    signal: req.signal,
  });

  // The backend answers 204 when the browser left during the search, a body is not allowed then.
  if (upstream.status === 204) return new Response(null, { status: 204 });

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") || "application/json" },
    });
  }

  const reader = upstream.body.getReader();
  const stream = new ReadableStream({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) controller.close();
      else controller.enqueue(value);
    },
    cancel() {
      reader.cancel();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
