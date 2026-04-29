import { FilePdf, FileDoc, FileVideo, FileAudio } from "@phosphor-icons/react";
import type { LernKarte, QuizQuestion } from "./_types";

export const _MEDIA_EXTENSIONS = new Set([".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"]);
export const _VIDEO_EXTENSIONS = new Set([".mp4", ".webm"]);
export const _AUDIO_EXTENSIONS = new Set([".mp3", ".wav", ".flac", ".m4a"]);

export function _embedQmapIntoCitations(content: string, qmap: { qnum: number; uuid: string }[]): string {
  if (!qmap.length) return content;
  // Matches both old [Q1, ...] and new [1, ...] citation formats
  return content.replace(/\[Q?(\d+)(,)/g, (match, n, comma) => {
    const entry = qmap.find((q) => q.qnum === parseInt(n, 10));
    return entry ? `[Q${n}:${entry.uuid}${comma}` : match;
  });
}

export function _formatApiError(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return null;
}

export function _isMediaFile(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return _MEDIA_EXTENSIONS.has(ext);
}

export function _fileKind(filename: string): "pdf" | "video" | "audio" | "doc" {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  if (ext === ".pdf") return "pdf";
  if (_VIDEO_EXTENSIONS.has(ext)) return "video";
  if (_AUDIO_EXTENSIONS.has(ext)) return "audio";
  return "doc";
}

export function _getChipIcon(filename: string) {
  const kind = _fileKind(filename);
  if (kind === "video") return FileVideo;
  if (kind === "audio") return FileAudio;
  if (kind === "pdf") return FilePdf;
  return FileDoc;
}

export function _formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

/** Convert **bold** and *italic* markdown to HTML (XSS-safe). */
export function _md(text: string): string {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
}

/** Deduplication key for source chips. Same PDF page+highlight or same media timestamp
 * share a key so duplicate chips can be filtered out. */
export function _sourceChipKey(
  label: string,
  page: number | null | undefined,
  startTime: number | null | undefined,
  highlight: string | null | undefined,
): string {
  if (startTime != null) return `m:${label}:${startTime}`;
  return `p:${label}:${page ?? 0}:${highlight ?? ""}`;
}

export function _chunkLabel(filename: string, num: number, startTime?: number | null): string {
  if (_isMediaFile(filename) && startTime != null) return _formatTime(startTime);
  if (_isMediaFile(filename)) return `Teil ${num}`;
  return `S. ${num}`;
}

export function parseFlashcards(text: string): LernKarte[] {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const karten: LernKarte[] = [];
  for (const line of lines) {
    const sepIdx = line.indexOf(" | ");
    if (sepIdx !== -1) {
      const front = line.slice(0, sepIdx).replace(/^\d+[.)]\s*/, "").trim();
      const back = line.slice(sepIdx + 3).trim();
      if (front && back) karten.push({ front, back });
    }
  }
  return karten;
}

export function parseQuiz(text: string): QuizQuestion[] {
  const questions: QuizQuestion[] = [];
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  let current: { question: string; options: string[]; correct: number } | null = null;
  for (const line of lines) {
    const qMatch = line.match(/^\d+[.)]\s+(.+)$/);
    const optMatch = line.match(/^[A-Da-d][.)]\s+(.+)$/);
    if (qMatch) {
      if (current && current.options.length > 0) questions.push(current);
      current = { question: qMatch[1], options: [], correct: 0 };
    } else if (optMatch && current) {
      const isCorrect = line.includes("✓") || line.includes("(richtig)");
      const optText = optMatch[1].replace(/[✓(richtig)]/g, "").trim();
      if (isCorrect) current.correct = current.options.length;
      current.options.push(optText);
    }
  }
  if (current && current.options.length > 0) questions.push(current);
  return questions;
}
