import type { JobStatus } from "@/lib/api";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import type { SlideData } from "@/types";
import { LANGUAGE_FLAG } from "@/lib/languageFlags";

export function computeVoiceLabel(
  providerId: number,
  voiceId: string,
  providers: ProviderWithVoices[],
): string {
  const provider = providers.find((p) => p.id === providerId);
  if (!provider) return voiceId;
  const voice = provider.voices.find((v) => v.voice_id === voiceId);
  if (!voice) return voiceId;
  const flag = LANGUAGE_FLAG[voice.language] ?? "";
  return `${flag} ${voice.name}`.trim();
}


export type RenderProgress =
  | { kind: "queue" }
  | { kind: "translatePresentation" }
  | { kind: "extractSlides" }
  | { kind: "scripts"; total?: number }
  | { kind: "images" }
  | { kind: "tts"; current?: number; total?: number; fertig: number[]; nichtDabei: number[] }
  | { kind: "video"; current?: number; total?: number }
  | { kind: "concat" }
  | { kind: "subtitles" }
  | { kind: "fallback" };

export function renderProgress(status: JobStatus): RenderProgress {
  const p = status.progress as { step?: string; current?: number; total?: number; fertig?: number[]; nicht_dabei?: number[] } | null;
  if (!p?.step) return { kind: "queue" };
  if (p.step === "translate") return { kind: "translatePresentation" };
  if (p.step === "extract") return { kind: "extractSlides" };
  if (p.step === "scripts") return { kind: "scripts", total: p.total ?? undefined };
  if (p.step === "images") return { kind: "images" };
  if (p.step === "tts") return { kind: "tts", current: p.current ?? undefined, total: p.total ?? undefined, fertig: p.fertig ?? [], nichtDabei: p.nicht_dabei ?? [] };
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

/** Abzug des letzten erfolgreichen Laufs, Grundlage der Aenderungs-Erkennung. */
export interface VertonterStand {
  scripts: string[];
  folientexte: string[];
  voice_id: string;
  provider_id: number;
  target_lang: string;
  speed?: number;
  slide_pause?: number;
  subtitles?: boolean;
  video_folien?: number[];
}

export type FolienMarke = "skript" | "folie" | null;

/** Beides geaendert meldet das Skript, das ist der Grund der den Nutzer betrifft. */
export function markeFuerFolie(
  stand: VertonterStand | null,
  index: number,
  script: string,
  folientext: string,
): FolienMarke {
  if (!stand) return null;
  const alterText = stand.folientexte[index];
  const altesSkript = stand.scripts[index];
  if (altesSkript === undefined && alterText === undefined) return "skript";
  if ((script ?? "").trim() !== (altesSkript ?? "").trim()) return "skript";
  if ((folientext ?? "").trim() !== (alterText ?? "").trim()) return "folie";
  return null;
}

/** Die Folien, die Schritt 6 zum Neuvertonen vorschlaegt. */
export function geaenderteFolien(stand: VertonterStand | null, slides: SlideData[]): number[] {
  if (!stand) return [];
  return slides
    .map((s, i) => (s.script?.trim() && markeFuerFolie(stand, i, s.script, s.extractedText) ? i : -1))
    .filter((i) => i >= 0);
}

/** Was ein neuer Lauf gegenueber dem letzten aendern wuerde. */
export interface LaufStand {
  stand: VertonterStand | null;
  hatVideo: boolean;
  imScreencast: number[];
  neuVertonen: number[];
  ohneTon: number[];
  geaendert: number[];
  providerId: number;
  voiceId: string;
  targetLang: string;
  speed: number;
  slidePause: number;
  subtitles: boolean;
}

/** Wahr, wenn dieser Lauf keine einzige Folie neu sprechen wuerde. */
export function nichtsWirdGesprochen(s: LaufStand): boolean {
  if (s.neuVertonen.length > 0) return false;
  // Eine Folie ohne Ton bekaeme welchen, auch ohne Haken.
  return !s.ohneTon.some((i) => s.imScreencast.includes(i));
}

/** Wahr, wenn eine neue Stimme wirkungslos bliebe, weil nichts gesprochen wird. */
export function stimmwechselOhneWirkung(s: LaufStand): boolean {
  if (!s.stand || !s.hatVideo) return false;
  if (!nichtsWirdGesprochen(s)) return false;
  return (
    s.stand.voice_id !== s.voiceId ||
    s.stand.provider_id !== s.providerId ||
    s.stand.target_lang !== s.targetLang
  );
}

/** Wahr, wenn ein neuer Lauf genau dasselbe Video ergaebe. */
export function laufWaereUmsonst(s: LaufStand): boolean {
  if (!s.stand || !s.hatVideo) return false;
  if (!nichtsWirdGesprochen(s)) return false;
  if (s.geaendert.length > 0) return false;
  if (s.stand.voice_id !== s.voiceId) return false;
  if (s.stand.provider_id !== s.providerId) return false;
  if (s.stand.target_lang !== s.targetLang) return false;
  if (s.stand.speed !== undefined && rundeZwei(s.stand.speed) !== rundeZwei(s.speed)) return false;
  if (s.stand.slide_pause !== undefined && rundeZwei(s.stand.slide_pause) !== rundeZwei(s.slidePause)) return false;
  if (s.stand.subtitles !== undefined && s.stand.subtitles !== s.subtitles) return false;
  if (s.stand.video_folien !== undefined
      && !gleicheNummern(s.stand.video_folien, s.imScreencast)) return false;
  return true;
}

function rundeZwei(n: number): number {
  return Math.round(n * 100) / 100;
}

function gleicheNummern(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const x = [...a].sort((p, q) => p - q);
  const y = [...b].sort((p, q) => p - q);
  return x.every((wert, i) => wert === y[i]);
}

/** Welche Folien nicht im Video sind, aus dem Fortschritt oder aus dem Ergebnis. */
export function ausgeschlosseneFolien(
  anzahl: number,
  ausDemFortschritt: number[],
  videoFolien: number[] | null,
): number[] {
  if (ausDemFortschritt.length > 0) return ausDemFortschritt;
  if (!videoFolien) return [];
  const dabei = new Set(videoFolien);
  return Array.from({ length: anzahl }, (_, i) => i).filter((i) => !dabei.has(i));
}
