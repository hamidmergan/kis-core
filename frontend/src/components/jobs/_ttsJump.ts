/** Whether and how a TTS job from the jobs list opens in the tool. */

interface JumpJob {
  tool: string;
  status: string;
  has_download?: boolean;
}

/** A finished audio opens and plays again, there is no mid-flow page to resume into. */
export function ttsJumpKind(job: JumpJob): "open" | null {
  if (job.tool !== "tts") return null;
  return job.status === "success" && job.has_download ? "open" : null;
}

export function ttsJumpHref(jobUuid: string): string {
  return `/tools/tts?job=${jobUuid}`;
}
