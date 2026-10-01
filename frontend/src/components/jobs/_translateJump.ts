/** Whether and how a translation job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** A finished translation opens and shows again, there is no mid-flow page to resume into. */
export function translateJumpKind(job: JumpJob): "open" | null {
  if (job.tool !== "translation") return null;
  return job.status === "success" && job.has_download ? "open" : null;
}

export function translateJumpHref(jobUuid: string): string {
  return `/tools/translate?job=${jobUuid}`;
}
