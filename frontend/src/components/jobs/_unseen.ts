/** Reine Helfer für den Punkt am Job-Knopf. */

interface JobTimes {
  status: string;
  completed_at: string | null;
}

const DONE_STATES = new Set(["success", "failed"]);

/** Backend timestamps carry no zone marker but are UTC. */
export function toMs(dateStr: string): number {
  return new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z").getTime();
}

/** True when a job finished after the user last looked at the panel. */
export function hasUnseenDone(jobs: JobTimes[], lastSeenMs: number): boolean {
  return jobs.some(
    (j) => DONE_STATES.has(j.status) && j.completed_at !== null && toMs(j.completed_at) > lastSeenMs,
  );
}
