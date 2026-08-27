/** Pure helpers for the dot on the jobs button. */

import { toMs } from "@/lib/format";

interface JobTimes {
  status: string;
  completed_at: string | null;
}

const DONE_STATES = new Set(["success", "failed"]);

/** True when a job finished after the user last looked at the panel. */
export function hasUnseenDone(jobs: JobTimes[], lastSeenMs: number): boolean {
  return jobs.some(
    (j) => DONE_STATES.has(j.status) && j.completed_at !== null && toMs(j.completed_at) > lastSeenMs,
  );
}
