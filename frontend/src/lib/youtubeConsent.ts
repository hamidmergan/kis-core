import { readPrefs, updatePrefs } from "./browserStore";

/** Whether this browser has ever agreed to load YouTube's embedded player. */
export function readYoutubeConsent(): boolean {
  return readPrefs().youtubeConsent === true;
}

/** Remembers the agreement so no later video on this browser asks again. */
export function writeYoutubeConsent(): void {
  updatePrefs({ youtubeConsent: true });
}
