/** Whether and how a page job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
}

/** A finished page opens in its editor, a page is never downloaded as a file. */
export function pagesJumpKind(job: JumpJob): "open" | null {
  if (job.tool !== "pages") return null;
  return job.status === "success" ? "open" : null;
}

export function pagesJumpHref(jobUuid: string): string {
  return `/tools/pages/${jobUuid}`;
}
