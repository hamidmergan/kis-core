import { MAX_TRANSCRIPTION_MINUTES } from "./constants";

/** The transcription ceiling in seconds, mirroring backend MAX_AUDIO_SEC. */
export const MINUTES_LIMIT_SECONDS = MAX_TRANSCRIPTION_MINUTES * 60;

/** Whether a recording is too long, an unknown duration deliberately passes. */
export function exceedsTranscriptionLimit(durationSeconds: number | null): boolean {
  if (durationSeconds === null || !Number.isFinite(durationSeconds)) return false;
  return durationSeconds > MINUTES_LIMIT_SECONDS;
}

/** Reads the playing time in the browser, null means the server decides. */
export function readMediaDurationSeconds(file: File, timeoutMs = 5000): Promise<number | null> {
  return new Promise((resolve) => {
    // A <video> element reads plain audio too, so one element covers both.
    const element = document.createElement("video");
    const url = URL.createObjectURL(file);
    let settled = false;

    const finish = (value: number | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      element.removeAttribute("src");
      element.load();
      URL.revokeObjectURL(url);
      resolve(value);
    };

    // Some formats fire no event at all and the button would stay dead.
    const timer = setTimeout(() => finish(null), timeoutMs);

    element.preload = "metadata";
    element.onloadedmetadata = () => finish(element.duration);
    element.onerror = () => finish(null);
    element.src = url;
  });
}
