/** Which state a job shows and in which tone, needed in three places. */

export type StatusTone = "brand" | "success" | "error" | "warn" | "muted";

export type JobStatusDisplay =
  | { kind: "action"; key: "awaitingUser" | "paused" }
  | { kind: "mark"; key: string; tone: StatusTone; pulse?: true };

type Umstaende = { expired?: boolean; isGeneratingScripts?: boolean };

/** Expired beats everything, after that the state itself counts. */
export function jobStatusDisplay(status: string, { expired, isGeneratingScripts }: Umstaende): JobStatusDisplay {
  if (expired) return { kind: "mark", key: "expired", tone: "muted" };
  if (status === "success") return { kind: "mark", key: "success", tone: "success" };
  if (status === "failed") return { kind: "mark", key: "failed", tone: "error" };
  if (status === "running" || isGeneratingScripts)
    return { kind: "mark", key: "running", tone: "brand", pulse: true };
  if (status === "awaiting_user") return { kind: "action", key: "awaitingUser" };
  // Paused waits for a click just like awaiting_user, it is not a failure.
  if (status === "paused") return { kind: "action", key: "paused" };
  if (status === "waiting_retry") return { kind: "mark", key: "waitingRetry", tone: "warn", pulse: true };
  if (status === "queued") return { kind: "mark", key: "queued", tone: "muted" };
  return { kind: "mark", key: "pending", tone: "warn" };
}
