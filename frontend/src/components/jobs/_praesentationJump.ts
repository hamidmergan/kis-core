/** Whether and how a presentation job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** 'resume' waits for a decision, 'open' is running or finished, null has no page. */
export function praesentationJumpKind(job: JumpJob): "resume" | "open" | null {
  if (job.tool !== "praesentation") return null;
  if (job.status === "awaiting_user" || job.status === "failed" || job.status === "paused") return "resume";
  if (job.status === "success") return job.has_download ? "open" : null;
  if (job.status === "queued" || job.status === "running" || job.status === "pending") return "open";
  return null;
}

export function praesentationJumpHref(jobUuid: string): string {
  return `/tools/praesentation?job=${jobUuid}`;
}
