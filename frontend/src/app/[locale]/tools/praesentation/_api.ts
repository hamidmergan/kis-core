import type { JobProgress, JobStatus, Outline, OutlineRow, PraesentationState, Slide, Vorlage } from "./_types";
import type { DemoView } from "./_demo";

export interface PraesentationView {
  job_uuid: string;
  status: JobStatus;
  progress: JobProgress | null;
  error: string | null;
  params: { language: string; notes: boolean; notes_include: boolean; template_id: string;
            template_name: string; template_fallback: boolean; instructions: string; presenter?: string;
            instruction_unmatched?: boolean } | null;
  outline: Outline | null;
  slides: Slide[];
  previews: string[];
  images: Record<string, string[]>;
  missing_images: string[];
  has_deck: boolean;
}

export interface JobView {
  status: JobStatus;
  progress: JobProgress | null;
  error: string | null;
}

/** Only a real message from the server, a validation error's first item, otherwise the caller says it in its own words. */
export async function fehlerText(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") return detail[0].msg;
  return "";
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(await fehlerText(res));
  return res.json() as Promise<T>;
}

const post = (url: string, body?: unknown) =>
  fetch(url, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
               body: body === undefined ? undefined : JSON.stringify(body) });
const put = (url: string, body: unknown) =>
  fetch(url, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export async function startPraesentation(state: PraesentationState, llmProviderId: number | null): Promise<string> {
  const form = new FormData();
  form.append("params", JSON.stringify({
    language: state.language, instructions: state.instructions, presenter: state.presenter,
    notes: state.notes, template_id: state.templateId, llm_provider_id: llmProviderId,
    // Left out while untouched, the server then takes the style of the template.
    ...(state.imageStyle !== null ? { style_text: state.imageStyle } : {}),
  }));
  form.append("mode", state.source.mode);
  if (state.source.mode === "module") {
    form.append("workspace_uuid", state.source.moduleId);
    form.append("source_uuids", JSON.stringify(state.source.sourceIds));
  } else {
    for (const f of state.source.files) form.append("files", f);
  }
  const res = await fetch("/api/praesentation/start", { method: "POST", credentials: "include", body: form });
  return (await json<{ job_uuid: string }>(res)).job_uuid;
}

export const fetchPraesentation = (uuid: string) =>
  fetch(`/api/praesentation/${uuid}`, { credentials: "include" }).then((r) => json<PraesentationView>(r));

export const fetchJob = (uuid: string) =>
  fetch(`/api/jobs/${uuid}`, { credentials: "include" }).then((r) => json<JobView>(r));

export const cancelJob = (uuid: string) => post(`/api/jobs/${uuid}/cancel`).then(() => undefined).catch(() => undefined);

export const deleteJob = (uuid: string) =>
  fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).then(() => undefined).catch(() => undefined);

export const saveOutline = (uuid: string, outline: Outline) =>
  put(`/api/praesentation/${uuid}/outline`, outline).then((r) => json<Outline>(r));

export const regenRow = (uuid: string, id: string, messages: { role: string; content: string }[], selectedText: string) =>
  post(`/api/praesentation/${uuid}/outline/${id}/regen`, { messages, selected_text: selectedText })
    .then((r) => json<OutlineRow>(r));

export const startBuild = (uuid: string) => post(`/api/praesentation/${uuid}/build`).then((r) => json<unknown>(r));

export const saveSlide = (uuid: string, slide: Slide) =>
  put(`/api/praesentation/${uuid}/slides/${slide.id}`, slide).then((r) => json<Slide>(r));

export const regenSlide = (uuid: string, id: string, messages: { role: string; content: string }[], selectedText: string) =>
  post(`/api/praesentation/${uuid}/slides/${id}/regen`, { messages, selected_text: selectedText }).then((r) => json<Slide>(r));

export const regenImage = (uuid: string, id: string, prompts: string[]) =>
  post(`/api/praesentation/${uuid}/slides/${id}/image`, { prompts }).then((r) => json<unknown>(r));

export const deleteSlide = (uuid: string, id: string) =>
  fetch(`/api/praesentation/${uuid}/slides/${id}`, { method: "DELETE", credentials: "include" }).then((r) => json<{ previews: string[] }>(r));

export const insertSlide = (uuid: string, after: string | null, title: string, instruction: string) =>
  post(`/api/praesentation/${uuid}/slides`, { after, title, instruction }).then((r) => json<{ id: string }>(r));

export const setNotesInclude = (uuid: string, include: boolean) =>
  put(`/api/praesentation/${uuid}/notes`, { include }).then((r) => json<{ include: boolean }>(r));

export const saveOrder = (uuid: string, ids: string[]) =>
  put(`/api/praesentation/${uuid}/slides/order`, { ids }).then((r) => json<{ previews: string[] }>(r));

export const finalize = (uuid: string) => post(`/api/praesentation/${uuid}/finalize`).then((r) => json<unknown>(r));

/** The prepared demo run has no job, its pictures and file come from the demo route. */
export const DEMO_JOB = "demo";
const ablage = (uuid: string) => (uuid === DEMO_JOB ? "/api/praesentation-demo" : `/api/praesentation/${uuid}`);

export const fetchDemo = () =>
  fetch("/api/praesentation-demo/ansicht", { credentials: "include" })
    .then((r) => json<DemoView>(r));

export const demoAvailable = () =>
  fetch("/api/praesentation-demo/available", { credentials: "include" })
    .then((r) => json<{ available: boolean }>(r))
    .then((d) => d.available)
    .catch(() => false);

export const previewUrl = (uuid: string, id: string, version: number) => `${ablage(uuid)}/preview/${id}.png?v=${version}`;
export const imageUrl = (uuid: string, id: string, slot: string, version: number) =>
  `${ablage(uuid)}/image/${id}/${slot}?v=${version}`;
export const downloadUrl = (uuid: string) => `${ablage(uuid)}/download`;

export const listVorlagen = () =>
  fetch("/api/praesentation/vorlagen", { credentials: "include" }).then((r) => json<Vorlage[]>(r));

export async function uploadVorlage(file: File, name: string, stiltext: string): Promise<Vorlage> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  form.append("stiltext", stiltext);
  const res = await fetch("/api/praesentation/vorlagen", { method: "POST", credentials: "include", body: form });
  return json<Vorlage>(res);
}

export const updateVorlage = (id: string, name: string, stiltext: string) =>
  put(`/api/praesentation/vorlagen/${id}`, { name, stiltext }).then((r) => json<Vorlage>(r));

export const deleteVorlage = (id: string) =>
  fetch(`/api/praesentation/vorlagen/${id}`, { method: "DELETE", credentials: "include" }).then((r) => json<unknown>(r));

export const vorlagePreviewUrl = (id: string) => `/api/praesentation/vorlagen/${id}/vorschau`;
