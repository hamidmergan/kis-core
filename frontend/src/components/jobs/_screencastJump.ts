/** Whether and how a screencast job from the jobs list opens in the assistant. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
  render_queued_at?: string | null;
  is_generating_scripts?: boolean;
}

/** 'resume' waits for input, 'open' is running or finished, null has no page. */
export function screencastJumpKind(job: JumpJob): "resume" | "open" | null {
  if (job.tool !== "screencast_translate") return null;
  if (job.status === "awaiting_user") return job.is_generating_scripts ? null : "resume";
  // Paused waits for a click, the render step shows the reason and the button.
  if (job.status === "paused" && job.render_queued_at) return "resume";
  // Expired jobs have no files left, there is nothing to show.
  if (job.status === "success") return job.has_download ? "open" : null;
  // Only the voicing has a waiting page, the translation does not.
  if ((job.status === "queued" || job.status === "running" || job.status === "waiting_retry") && job.render_queued_at) return "open";
  return null;
}

export function screencastJumpHref(jobUuid: string): string {
  return `/tools/screencast?resume=${jobUuid}`;
}
