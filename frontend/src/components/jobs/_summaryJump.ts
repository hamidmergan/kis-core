/** Whether and how a summary job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** A finished summary opens and shows again, there is no mid-flow page to resume into. */
export function summaryJumpKind(job: JumpJob): "open" | null {
  if (job.tool !== "summary") return null;
  return job.status === "success" && job.has_download ? "open" : null;
}

export function summaryJumpHref(jobUuid: string): string {
  return `/tools/summarize?job=${jobUuid}`;
}
