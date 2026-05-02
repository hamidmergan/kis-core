import type { JobStatus } from "@/lib/api";
import { KOKORO_ACCENT_LABEL } from "@/lib/voice-labels";
import type { KokoroVoice, ElevenLabsVoice } from "@/hooks/useVoices";

export function computeVoiceLabel(
  provider: string,
  voiceId: string,
  kokoroVoices: KokoroVoice[],
  elevenlabsVoices: ElevenLabsVoice[],
): string {
  if (provider === "kokoro") {
    const v = kokoroVoices.find((x) => x.voice_id === voiceId);
    return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId;
  }
  return elevenlabsVoices.find((x) => x.voice_id === voiceId)?.label ?? voiceId;
}


export function renderProgressLabel(status: JobStatus): string {
  const p = status.progress as { step?: string; current?: number; total?: number } | null;
  if (!p?.step) return "In der Warteschlange…";
  if (p.step === "translate") return "Präsentation wird übersetzt…";
  if (p.step === "extract") return "Folien werden analysiert…";
  if (p.step === "scripts" && p.total != null) return `Skripte werden generiert… (${p.total} Folien)`;
  if (p.step === "scripts") return "Skripte werden generiert…";
  if (p.step === "images") return "Folienbilder werden vorbereitet…";
  if (p.step === "tts" && p.current != null && p.total != null) return `Sprachsynthese: Folie ${p.current} von ${p.total}…`;
  if (p.step === "tts") return "Sprachsynthese läuft…";
  if (p.step === "video" && p.current != null && p.total != null) return `Video-Clip ${p.current} von ${p.total} wird gerendert…`;
  if (p.step === "video") return "Video-Clips werden gerendert…";
  if (p.step === "concat") return "Videos werden zusammengefügt…";
  if (p.step === "subtitles") return "Untertitel werden eingebettet…";
  return "Video wird erstellt…";
}

export type ScriptJsonParseResult =
  | { scripts: string[]; error?: never }
  | { scripts?: never; error: string };

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
    return Promise.resolve({ error: "Bitte eine gültige JSON-Datei auswählen (.json)." });
  }
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === "string")) {
          resolve({ error: 'Die JSON-Datei muss ein Array von Strings sein, z.B. ["Skript 1", "Skript 2"].' });
          return;
        }
        resolve({ scripts: parsed });
      } catch {
        resolve({ error: "Ungültige JSON-Datei - Parsing fehlgeschlagen." });
      }
    };
    reader.readAsText(file);
  });
}
