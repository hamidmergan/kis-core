/** Whether and how a podcast job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** 'resume' waits for a decision, 'open' is running or finished, null has no page. */
export function podcastJumpKind(job: JumpJob): "resume" | "open" | null {
  if (job.tool !== "podcast") return null;
  // The script waits for the person, and a failed run waits to be continued.
  if (job.status === "awaiting_user" || job.status === "failed") return "resume";
  // An expired job has no files left, there is nothing to show.
  if (job.status === "success") return job.has_download ? "open" : null;
  if (job.status === "queued" || job.status === "running" || job.status === "pending") return "open";
  return null;
}

export function podcastJumpHref(jobUuid: string): string {
  return `/tools/podcast?job=${jobUuid}`;
}
