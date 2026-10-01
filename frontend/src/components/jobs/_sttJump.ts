/** Whether and how a transcription job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** A finished transcript opens and reads again, there is no mid-flow page to resume into. */
export function sttJumpKind(job: JumpJob): "open" | null {
  if (job.tool !== "transcription") return null;
  return job.status === "success" && job.has_download ? "open" : null;
}

export function sttJumpHref(jobUuid: string): string {
  return `/tools/stt?job=${jobUuid}`;
}
