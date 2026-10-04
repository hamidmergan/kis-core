import type { Card, EventConfig, EventStats, PublicEvent } from "@/lib/event/types";

const VISITOR_KEY = "kis.event.visitor";

/** A random id that stays in this browser, the server only ever sees its hash. */
export function visitorId(): string {
  try {
    const known = localStorage.getItem(VISITOR_KEY);
    if (known && /^[A-Za-z0-9_-]{16,64}$/.test(known)) return known;
    const fresh = crypto.randomUUID();
    localStorage.setItem(VISITOR_KEY, fresh);
    return fresh;
  } catch {
    // Blocked storage, the card then lives only until the page closes.
    return (memoryId ??= crypto.randomUUID());
  }
}
let memoryId: string | undefined;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: "include", cache: "no-store", ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : null;
    throw new Error(detail ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

const visitor = (): HeadersInit => ({ "X-Visitor-Id": visitorId(), "Content-Type": "application/json" });

export const eventApi = {
  publicEvent: () => request<PublicEvent>("/event/public"),
  card: () => request<Card>("/event/card", { headers: visitor() }),
  stamp: (stationId: string) =>
    request<{ card: Card; stationId: string }>("/event/stamp", {
      method: "POST",
      headers: visitor(),
      body: JSON.stringify({ stationId }),
    }),
  code: (code: string) =>
    request<{ result: "stamped" | "wrong" | "locked"; stationId: string | null; card: Card }>("/event/code", {
      method: "POST",
      headers: visitor(),
      body: JSON.stringify({ code }),
    }),
  adminGet: () => request<EventConfig>("/admin/event"),
  adminPut: (config: EventConfig) =>
    request<EventConfig>("/admin/event", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    }),
  adminStats: () => request<EventStats>("/admin/event/stats"),
  adminResetMyCard: () => request<Card>("/admin/event/card", { method: "DELETE", headers: visitor() }),
  adminResetAllStamps: () => request<{ ok: boolean }>("/admin/event/stamps", { method: "DELETE" }),
};
