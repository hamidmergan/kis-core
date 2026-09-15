import type { JobStats } from "./_components/adminStats";


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
  render_started_at: string | null;
  render_queued_at: string | null;
  expires_at: string | null;
  has_download: boolean;
  result_filename: string | null;
  folder_name: string | null;
  tts_params?: { voice_id?: string; voice_label?: string; provider?: string } | null;
  is_generating_scripts?: boolean;
  meta?: (Record<string, unknown> & { stats?: JobStats }) | null;
}


export const SCREENCAST_RENDER_TOOLS = new Set([
  "screencast_render",
  "screencast_auto",
]);

export const SCREENCAST_TOOLS = new Set([
  "screencast_translate",
  "screencast_render",
  "screencast_auto",
]);


export const isActive = (s: MyJob["status"]): boolean =>
  s === "pending" || s === "running" || s === "awaiting_user" || s === "queued" || s === "waiting_retry";


export const isExpired = (job: MyJob): boolean =>
  job.status === "success" && !job.has_download;
