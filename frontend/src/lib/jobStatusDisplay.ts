/**
 * Welchen Zustand ein Auftrag zeigt und in welchem Ton.
 *
 * Eigene Datei, weil dieselbe Entscheidung an drei Stellen gebraucht wird und
 * vorher an allen dreien fast gleich im Code stand.
 */

export type StatusTone = "brand" | "success" | "error" | "warn" | "muted";

export type JobStatusDisplay =
  | { kind: "action"; key: "awaitingUser" }
  | { kind: "mark"; key: string; tone: StatusTone; pulse?: true };

type Umstaende = { expired?: boolean; isGeneratingScripts?: boolean };

/** Abgelaufen schlaegt alles, danach zaehlt der Zustand selbst. */
export function jobStatusDisplay(status: string, { expired, isGeneratingScripts }: Umstaende): JobStatusDisplay {
  if (expired) return { kind: "mark", key: "expired", tone: "muted" };
  if (status === "success") return { kind: "mark", key: "success", tone: "success" };
  if (status === "failed") return { kind: "mark", key: "failed", tone: "error" };
  if (status === "running" || isGeneratingScripts)
    return { kind: "mark", key: "running", tone: "brand", pulse: true };
  if (status === "awaiting_user") return { kind: "action", key: "awaitingUser" };
  if (status === "queued") return { kind: "mark", key: "queued", tone: "muted" };
  return { kind: "mark", key: "pending", tone: "warn" };
}
