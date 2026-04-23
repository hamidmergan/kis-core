export const JOBS_CHANGED_EVENT = "kis-jobs-changed";

export function notifyJobsChanged(): void {
  window.dispatchEvent(new CustomEvent(JOBS_CHANGED_EVENT));
}

export function onJobsChanged(handler: () => void): () => void {
  window.addEventListener(JOBS_CHANGED_EVENT, handler);
  return () => window.removeEventListener(JOBS_CHANGED_EVENT, handler);
}
