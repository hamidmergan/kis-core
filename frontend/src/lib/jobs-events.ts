export const JOBS_CHANGED_EVENT = "kis-jobs-changed";

export function notifyJobsChanged(): void {
  window.dispatchEvent(new CustomEvent(JOBS_CHANGED_EVENT));
}
