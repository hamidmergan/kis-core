import type { PodcastState } from "./_types";

const KEY = "kis_podcast_mockup";
const VERSION = 1;

/** The mockup keeps its state in the browser, the real build keeps it in the job folder. */
export function loadState(): PodcastState | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { v?: number; state?: PodcastState };
    return parsed.v === VERSION && parsed.state ? parsed.state : null;
  } catch {
    return null;
  }
}

export function saveState(state: PodcastState): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: VERSION, state }));
  } catch {
    // Storage may be blocked, the page still works without it.
  }
}

export function clearState(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
