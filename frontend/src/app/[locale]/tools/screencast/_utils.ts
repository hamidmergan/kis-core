import type { JobStatus } from "@/lib/api";
import { KOKORO_ACCENT_LABEL } from "@/lib/voice-labels";
import type { KokoroVoice, ElevenLabsVoice, OpenAITtsVoice } from "@/hooks/useVoices";

const MYLAB_FLAG: Record<string, string> = {
  "de": "🇩🇪",
  "en": "🇺🇸",
};

export function computeVoiceLabel(
  provider: string,
  voiceId: string,
  kokoroVoices: KokoroVoice[],
  elevenlabsVoices: ElevenLabsVoice[],
  mylabVoices: OpenAITtsVoice[] = [],
): string {
  if (provider === "kokoro") {
    const v = kokoroVoices.find((x) => x.voice_id === voiceId);
    return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId;
  }
  if (provider === "mylab") {
    const v = mylabVoices.find((x) => x.voice_id === voiceId);
    return v ? `${MYLAB_FLAG[v.language ?? ""] ?? ""} ${v.name}`.trim() : voiceId;
  }
  return elevenlabsVoices.find((x) => x.voice_id === voiceId)?.label ?? voiceId;
}


export type RenderProgress =
  | { kind: "queue" }
  | { kind: "translatePresentation" }
  | { kind: "extractSlides" }
  | { kind: "scripts"; total?: number }
  | { kind: "images" }
  | { kind: "tts"; current?: number; total?: number }
  | { kind: "video"; current?: number; total?: number }
  | { kind: "concat" }
  | { kind: "subtitles" }
  | { kind: "fallback" };

export function renderProgress(status: JobStatus): RenderProgress {
  const p = status.progress as { step?: string; current?: number; total?: number } | null;
  if (!p?.step) return { kind: "queue" };
  if (p.step === "translate") return { kind: "translatePresentation" };
  if (p.step === "extract") return { kind: "extractSlides" };
  if (p.step === "scripts") return { kind: "scripts", total: p.total ?? undefined };
  if (p.step === "images") return { kind: "images" };
  if (p.step === "tts") return { kind: "tts", current: p.current ?? undefined, total: p.total ?? undefined };
  if (p.step === "video") return { kind: "video", current: p.current ?? undefined, total: p.total ?? undefined };
  if (p.step === "concat") return { kind: "concat" };
  if (p.step === "subtitles") return { kind: "subtitles" };
  return { kind: "fallback" };
}

export type ScriptImportError = "invalidExtension" | "mustBeArray" | "parseError";

export type ScriptJsonParseResult =
  | { scripts: string[]; error?: never }
  | { scripts?: never; error: ScriptImportError };

export async function checkHasActiveJob(tool: string): Promise<{ ok: true; hasActive: boolean } | { ok: false }> {
  try {
    const res = await fetch(`/api/jobs/check/${tool}`, { credentials: "include" });
    const data = await res.json();
    return { ok: true, hasActive: !!data.has_active_job };
  } catch {
    return { ok: false };
  }
}

export async function checkJobValidity(jobUuid: string): Promise<"ok" | "running" | "deleted"> {
  try {
    const res = await fetch(`/api/jobs/${jobUuid}`, { credentials: "include" });
    if (!res.ok) return "deleted";
    const job = await res.json();
    if (job.status === "awaiting_user" || job.status === "success" || job.status === "failed") return "ok";
    if (job.status === "pending" || job.status === "running") return "running";
    return "deleted";
  } catch {
    return "ok"; // Network error — let backend decide
  }
}

export async function checkJobFolderExists(jobUuid: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/screencast/folder-exists/${jobUuid}`, { credentials: "include" });
    const data = await res.json();
    return !!data.exists;
  } catch {
    return true; // Network error — let backend decide
  }
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function parseScriptJsonFile(file: File): Promise<ScriptJsonParseResult> {
  if (!file.name.toLowerCase().endsWith(".json")) {
    return Promise.resolve({ error: "invalidExtension" });
  }
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === "string")) {
          resolve({ error: "mustBeArray" });
          return;
        }
        resolve({ scripts: parsed });
      } catch {
        resolve({ error: "parseError" });
      }
    };
    reader.readAsText(file);
  });
}
