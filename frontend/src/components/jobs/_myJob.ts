/** One row of the own jobs list as the backend sends it, and the rules read off it. */

export interface MyJob {
  job_uuid: string;
  tool: string;
  tool_label: string;
  original_filename: string;
  status: "pending" | "running" | "success" | "failed" | "awaiting_user" | "queued" | "waiting_retry" | "paused";
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  expires_at: string | null;
  render_queued_at: string | null;
  has_download: boolean;
  has_docx?: boolean;
  result_filename: string | null;
  tts_params?: { voice_id?: string; voice_label?: string; provider?: string } | null;
  is_generating_scripts?: boolean;
}

type JobFacts = Pick<MyJob, "tool" | "status" | "has_download" | "result_filename">;

const SCREENCAST_TOOLS = new Set(["screencast_render", "screencast_auto", "screencast_translate"]);
const FIXED_FORMAT = new Map([["image_generate", "PNG"], ["image_edit", "PNG"], ["image_analyze", "TXT"], ["tts", "MP3"]]);
const FORMAT_FROM_NAME = new Set(["transcription", "translation", "summary"]);
const RETRY_AFTER_FAILURE = new Set(["tts", "screencast_translate", "screencast_render"]);
const CONTINUE_ONLY = new Set(["summary", "pages"]);

/** A finished job whose files are gone. */
export const isExpired = (job: JobFacts) => job.status === "success" && !job.has_download;

export const isScreencast = (job: JobFacts) => SCREENCAST_TOOLS.has(job.tool);

/** The format on the download link, null where only the general word fits. */
export function downloadFormat(job: JobFacts): string | null {
  if (isScreencast(job)) return "MP4";
  const fixed = FIXED_FORMAT.get(job.tool);
  if (fixed) return fixed;
  if (FORMAT_FROM_NAME.has(job.tool)) return job.result_filename?.split(".").pop()?.toUpperCase() ?? null;
  return null;
}

/** Whether the list itself offers the retry, other tools continue on their own page. */
export function canRetry(job: JobFacts): boolean {
  if (RETRY_AFTER_FAILURE.has(job.tool)) return job.status === "failed" || job.status === "paused";
  return CONTINUE_ONLY.has(job.tool) && job.status === "paused";
}
