"use client";

import type { JobProgress, JobStatus, Line, PodcastState } from "./_types";

export interface PodcastParamsView {
  language: "de" | "en";
  instructions: string;
  persons: { name: string; role: string; voice_id: string; provider_id: number }[];
  length: string;
  style: string;
  speed: number;
  self_written: boolean;
  instruction_unmatched: boolean;
}

export interface PodcastView {
  job_uuid: string;
  status: JobStatus;
  progress: JobProgress | null;
  error: string | null;
  params: PodcastParamsView | null;
  lines: Line[];
  /** The parts already written while the script is still being written. */
  draft?: Line[];
  voiced: string[];
  has_result: boolean;
}

/** Only a real message from the server, otherwise the caller says it in its own words. */
async function fehlerText(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  return typeof detail === "string" ? detail : "";
}

/** Step one: material and cast go out, a job comes back. */
export async function startPodcast(state: PodcastState, glossary: Record<string, string>,
                                   llmProviderId: number | null): Promise<string> {
  const persons = state.persons.slice(0, state.count).map((p) => ({
    name: p.name.trim(),
    role: p.role,
    voice_id: p.voiceId,
    provider_id: p.providerId,
  }));
  const form = new FormData();
  form.append("params", JSON.stringify({
    language: state.language,
    instructions: state.instructions,
    persons,
    length: state.length,
    style: state.style,
    speed: state.speed,
    glossary,
    llm_provider_id: llmProviderId,
  }));
  form.append("mode", state.source.mode);
  if (state.source.mode === "files") state.source.files.forEach((f) => form.append("files", f));
  if (state.source.mode === "module") {
    form.append("workspace_uuid", state.source.moduleId);
    form.append("source_uuids", JSON.stringify(state.source.sourceIds));
  }
  const res = await fetch("/api/podcast/start", { method: "POST", body: form, credentials: "include" });
  if (!res.ok) throw new Error(await fehlerText(res));
  return (await res.json()).job_uuid as string;
}

/** A new cast for a podcast that already exists, material and language stay as they were. */
export async function savePodcastParams(jobUuid: string, state: PodcastState): Promise<void> {
  const persons = state.persons.slice(0, state.count).map((p) => ({
    name: p.name.trim(),
    role: p.role,
    voice_id: p.voiceId,
    provider_id: p.providerId,
  }));
  const res = await fetch(`/api/podcast/${jobUuid}/params`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persons, length: state.length, style: state.style, speed: state.speed }),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await fehlerText(res));
}

export async function fetchPodcast(jobUuid: string): Promise<PodcastView> {
  const res = await fetch(`/api/podcast/${jobUuid}`, { credentials: "include" });
  if (!res.ok) throw new Error(await fehlerText(res));
  return res.json();
}

/** Saved on every change, so a closed tab loses no edit. */
export async function saveScript(jobUuid: string, lines: Line[]): Promise<Line[]> {
  const res = await fetch(`/api/podcast/${jobUuid}/script`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lines }),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await fehlerText(res));
  return (await res.json()).lines as Line[];
}

/** One contribution reworked to a wish, the answer is only the new text. */
export async function rephraseLine(jobUuid: string, lineId: string,
                                   messages: { role: string; content: string }[] = [],
                                   selectedText = ""): Promise<string> {
  const res = await fetch(`/api/podcast/${jobUuid}/rephrase`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ line_id: lineId, messages, selected_text: selectedText }),
    credentials: "include",
  });
  if (!res.ok) throw new Error(await fehlerText(res));
  return (await res.json()).text as string;
}

export async function startRender(jobUuid: string): Promise<void> {
  const res = await fetch(`/api/podcast/${jobUuid}/render`, { method: "POST", credentials: "include" });
  if (!res.ok) throw new Error(await fehlerText(res));
}

export async function cancelJob(jobUuid: string): Promise<void> {
  await fetch(`/api/jobs/${jobUuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
}

export interface JobView {
  status: JobStatus;
  progress: JobProgress | null;
  error: string | null;
  download_url?: string | null;
  meta?: { seconds?: number; lines?: number; voices?: number } | null;
}

export async function fetchJob(jobUuid: string): Promise<JobView> {
  const res = await fetch(`/api/jobs/${jobUuid}`, { credentials: "include" });
  if (!res.ok) throw new Error(await fehlerText(res));
  return res.json();
}

/** The prepared demo run has no job, its audio and transcript come from the demo route. */
export const DEMO_JOB = "demo";
const DEMO = "/api/podcast-demo";

export const lineAudioUrl = (jobUuid: string, lineId: string) =>
  jobUuid === DEMO_JOB ? `${DEMO}/line/${lineId}` : `/api/podcast/${jobUuid}/line/${lineId}`;
export const resultUrl = (jobUuid: string) => (jobUuid === DEMO_JOB ? `${DEMO}/download` : `/api/jobs/${jobUuid}/download`);
export const transcriptUrl = (jobUuid: string) =>
  jobUuid === DEMO_JOB ? `${DEMO}/transcript` : `/api/podcast/${jobUuid}/transcript`;

export async function fetchDemo(): Promise<PodcastView & { seconds: number | null; workspace: string; files: string[] }> {
  const res = await fetch(`${DEMO}/ansicht`, { credentials: "include" });
  if (!res.ok) throw new Error(await fehlerText(res));
  return res.json();
}

export const demoAvailable = (): Promise<boolean> =>
  fetch(`${DEMO}/available`, { credentials: "include" })
    .then((r) => (r.ok ? r.json() : { available: false }))
    .then((d: { available: boolean }) => d.available)
    .catch(() => false);
