const STORAGE_KEY = "kis.youtube-consent";

/** Whether this browser has ever agreed to load YouTube's embedded player. */
export function readYoutubeConsent(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "granted";
  } catch {
    return false;
  }
}

/** Remembers the agreement so no later video on this browser asks again. */
export function writeYoutubeConsent(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, "granted");
  } catch {
    // ignore
  }
}
