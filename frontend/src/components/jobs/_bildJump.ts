/** Whether and how an image job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

const BILD_TOOLS = new Set(["image_generate", "image_edit", "image_analyze"]);

/** A finished picture or answer opens on the large stage again, there is no mid-flow page to resume into. */
export function bildJumpKind(job: JumpJob): "open" | null {
  if (!BILD_TOOLS.has(job.tool)) return null;
  return job.status === "success" && job.has_download ? "open" : null;
}

export function bildJumpHref(jobUuid: string): string {
  return `/tools/image?job=${jobUuid}`;
}
