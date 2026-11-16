/** Where a job from the jobs list leads, one table instead of a chain per tool. */

import { bildJumpHref, bildJumpKind } from "./_bildJump";
import { pagesJumpHref, pagesJumpKind } from "./_pagesJump";
import { podcastJumpHref, podcastJumpKind } from "./_podcastJump";
import { praesentationJumpHref, praesentationJumpKind } from "./_praesentationJump";
import { screencastJumpHref, screencastJumpKind } from "./_screencastJump";
import { sttJumpHref, sttJumpKind } from "./_sttJump";
import { summaryJumpHref, summaryJumpKind } from "./_summaryJump";
import { translateJumpHref, translateJumpKind } from "./_translateJump";
import { ttsJumpHref, ttsJumpKind } from "./_ttsJump";

interface JumpJob {
  job_uuid: string;
  tool: string;
  status: string;
  has_download?: boolean;
  render_queued_at?: string | null;
  is_generating_scripts?: boolean;
}

/** The key of the link text under myJobs.artifacts. */
export type OpenLabel =
  | "openPodcast" | "openPraesentation" | "openScreencast" | "openPage" | "openSummary"
  | "openTranslation" | "openTts" | "openStt" | "openImage";

interface Jump {
  kind: (job: JumpJob) => "resume" | "open" | null;
  href: (jobUuid: string) => string;
  label: OpenLabel;
}

// The order is the order the links are rendered in.
const JUMPS: Jump[] = [
  { kind: podcastJumpKind, href: podcastJumpHref, label: "openPodcast" },
  { kind: praesentationJumpKind, href: praesentationJumpHref, label: "openPraesentation" },
  { kind: screencastJumpKind, href: screencastJumpHref, label: "openScreencast" },
  { kind: pagesJumpKind, href: pagesJumpHref, label: "openPage" },
  { kind: summaryJumpKind, href: summaryJumpHref, label: "openSummary" },
  { kind: translateJumpKind, href: translateJumpHref, label: "openTranslation" },
  { kind: ttsJumpKind, href: ttsJumpHref, label: "openTts" },
  { kind: sttJumpKind, href: sttJumpHref, label: "openStt" },
  { kind: bildJumpKind, href: bildJumpHref, label: "openImage" },
];

// Only these three tools have a page that waits for the person.
const RESUMABLE: Jump[] = [JUMPS[2], JUMPS[0], JUMPS[1]];

/** The page a waiting job continues on, undefined when it has none. */
export function resumeHref(job: JumpJob): string | undefined {
  return RESUMABLE.find((j) => j.kind(job) === "resume")?.href(job.job_uuid);
}

/** The links that open a running or finished job in its tool. */
export function openJumps(job: JumpJob): { href: string; label: OpenLabel }[] {
  return JUMPS.filter((j) => j.kind(job) === "open").map((j) => ({ href: j.href(job.job_uuid), label: j.label }));
}
