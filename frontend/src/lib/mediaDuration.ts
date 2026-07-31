import { MAX_TRANSCRIPTION_MINUTES } from "./constants";

/** The transcription ceiling in seconds, mirroring backend MAX_AUDIO_SEC. */
export const MINUTES_LIMIT_SECONDS = MAX_TRANSCRIPTION_MINUTES * 60;

/**
 * Whether a recording is too long to transcribe.
 *
 * An unknown duration (null, NaN for a file the browser cannot decode, Infinity
 * for a stream without a fixed length) deliberately passes: the browser check
 * exists to save the user a pointless upload, not to be the authority. ffprobe
 * on the server has the final say, so guessing here would only reject files
 * that would actually have worked.
 */
export function exceedsTranscriptionLimit(durationSeconds: number | null): boolean {
  if (durationSeconds === null || !Number.isFinite(durationSeconds)) return false;
  return durationSeconds > MINUTES_LIMIT_SECONDS;
}

/**
 * Read a media file's duration in the browser, without uploading it.
 *
 * Resolves to null whenever the duration cannot be determined (unsupported
 * codec, broken metadata, timeout), which :func:`exceedsTranscriptionLimit`
 * then treats as "let the server decide".
 */
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

    // Some containers never fire either event. Without this the upload button
    // would stay dead with no explanation.
    const timer = setTimeout(() => finish(null), timeoutMs);

    element.preload = "metadata";
    element.onloadedmetadata = () => finish(element.duration);
    element.onerror = () => finish(null);
    element.src = url;
  });
}
