import { FilePdf, FileDoc, FileVideo, FileAudio, YoutubeLogo } from "@phosphor-icons/react";
import type { LernKarte, QuizQuestion } from "./_types";
import { isYoutubeSource, youtubeVideoId } from "@/lib/youtube";

export const _MEDIA_EXTENSIONS = new Set([".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm", ".youtube"]);
export const _VIDEO_EXTENSIONS = new Set([".mp4", ".webm", ".youtube"]);
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

export function _fileKind(filename: string): "pdf" | "video" | "audio" | "doc" | "youtube" {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  if (ext === ".pdf") return "pdf";
  // A YouTube source is a video without a file, it gets its own icon.
  if (ext === ".youtube") return "youtube";
  if (_VIDEO_EXTENSIONS.has(ext)) return "video";
  if (_AUDIO_EXTENSIONS.has(ext)) return "audio";
  return "doc";
}

/** The video id behind a YouTube source, undefined for every other source. */
export function _youtubeIdOf(source: { filename: string; source_url?: string | null }): string | undefined {
  if (!isYoutubeSource(source.filename)) return undefined;
  return youtubeVideoId(source.source_url) ?? undefined;
}

/** Splits file name and extension, because renaming keeps the extension fixed. */
export function splitFilename(filename: string): [string, string] {
  const i = filename.lastIndexOf(".");
  return i > 0 ? [filename.slice(0, i), filename.slice(i)] : [filename, ""];
}

export function _getChipIcon(filename: string) {
  const kind = _fileKind(filename);
  if (kind === "youtube") return YoutubeLogo;
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

/** Turns bold and italic into HTML, LaTeX is flattened to Unicode first. */
export function _md(text: string): string {
  const esc = _mathToUnicode(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
}

// Protects dollar pairs that are no formula so KaTeX swallows no prose.
const _CODE_SPANS = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g;
const _DOLLAR_SPANS = /\$\$[\s\S]*?\$\$|(?<!\\)\$([^$\n]{1,200})(?<!\\)\$/g;
function _looksLikeMath(inner: string): boolean {
  // A LaTeX command, sub-/superscript or grouping is unambiguous math.
  if (/[\\^_{}]/.test(inner)) return true;
  // Without letters it is digits and punctuation, so money and not a formula.
  if (!/\p{L}/u.test(inner)) {
    // A whole calculation or a number pair still counts as a formula.
    if (/\d\s*[+*/=<>−]\s*\d/.test(inner) || /\d\s+-\s+\d/.test(inner)) return true;
    return /^\(\s*-?\d[\d\s.,]*\)$/.test(inner);
  }
  // With a letter an operator or comparison sign makes it a formula.
  if (/[=<>+\-*\/−]/.test(inner)) return true;
  // Otherwise a short, space-free token is a bare variable ("x", "H2O", "v0").
  return !/\s/.test(inner) && inner.length <= 20;
}
export function _guardMathDollars(text: string): string {
  if (!text.includes("$")) return text;
  return text
    .split(_CODE_SPANS)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(_DOLLAR_SPANS, (match, inner?: string) =>
      inner === undefined || _looksLikeMath(inner) ? match : `\\$${inner}\\$`)))
    .join("");
}

// The same LaTeX for surfaces without KaTeX, flattened to the nearest Unicode.
const _LATEX_SYMBOLS: Record<string, string> = {
  rightarrow: "→", to: "→", longrightarrow: "→", Rightarrow: "⇒", implies: "⇒",
  leftarrow: "←", Leftarrow: "⇐", leftrightarrow: "↔", Leftrightarrow: "⇔", iff: "⇔",
  times: "×", cdot: "·", div: "÷", pm: "±", mp: "∓", ast: "∗",
  leq: "≤", le: "≤", geq: "≥", ge: "≥", neq: "≠", ne: "≠", approx: "≈", equiv: "≡", sim: "∼", propto: "∝",
  infty: "∞", sum: "∑", prod: "∏", int: "∫", partial: "∂", nabla: "∇", surd: "√",
  in: "∈", notin: "∉", subset: "⊂", supset: "⊃", cup: "∪", cap: "∩", emptyset: "∅",
  forall: "∀", exists: "∃", neg: "¬", land: "∧", lor: "∨", perp: "⊥", parallel: "∥", angle: "∠",
  degree: "°", circ: "°", ldots: "…", dots: "…", cdots: "…", quad: " ", qquad: "  ",
  alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", zeta: "ζ", eta: "η", theta: "θ",
  kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", rho: "ρ", sigma: "σ", tau: "τ",
  phi: "φ", chi: "χ", psi: "ψ", omega: "ω", pi: "π",
  Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Sigma: "Σ", Phi: "Φ", Psi: "Ψ", Omega: "Ω",
};
const _SUPERSCRIPTS: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
  "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾", n: "ⁿ", i: "ⁱ",
};
const _SUBSCRIPTS: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
  "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎", n: "ₙ", i: "ᵢ",
};
function _script(chars: string, table: Record<string, string>): string {
  return [...chars].every((c) => c in table) ? [...chars].map((c) => table[c]).join("") : chars;
}
function _flattenMath(body: string): string {
  return body
    .replace(/\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "$1/$2")
    .replace(/\\sqrt\s*\{([^{}]*)\}/g, "√($1)")
    .replace(/\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}/g, "$1")
    .replace(/\\(?:left|right)(?![a-zA-Z])|\\[!,;:]/g, "")  // sizing/spacing only — the trailing guard keeps \rightarrow intact
    .replace(/\\([a-zA-Z]+)/g, (_m, name: string) => _LATEX_SYMBOLS[name] ?? name)
    .replace(/\^\{([^{}]*)\}|\^(\S)/g, (_m, braced: string, single: string) => _script(braced ?? single, _SUPERSCRIPTS))
    .replace(/_\{([^{}]*)\}|_(\S)/g, (_m, braced: string, single: string) => _script(braced ?? single, _SUBSCRIPTS))
    .replace(/[{}]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
const _MATH_SPANS = /\$\$([\s\S]*?)\$\$|(?<!\\)\$([^$\n]{1,200})(?<!\\)\$/g;
export function _mathToUnicode(text: string): string {
  if (!text.includes("$")) return text;
  return text.replace(_MATH_SPANS, (match, display?: string, inline?: string) => {
    const body = display ?? inline;
    if (body === undefined) return match;
    return display !== undefined || _looksLikeMath(body) ? _flattenMath(body) : match;
  });
}

/** Key for recognising duplicate citation chips. */
export function _sourceChipKey(
  label: string,
  page: number | null | undefined,
  startTime: number | null | undefined,
  highlight: string | null | undefined,
): string {
  if (startTime != null) return `m:${label}:${startTime}`;
  return `p:${label}:${page ?? 0}:${highlight ?? ""}`;
}

// Label of a citation chip in the interface language, German without tChip.
export type ChipLabelT = (key: "page" | "part", values: { num: number }) => string;

export function _chunkLabel(
  filename: string,
  num: number | null | undefined,
  startTime?: number | null,
  tChip?: ChipLabelT,
): string {
  if (_isMediaFile(filename) && startTime != null) return _formatTime(startTime);
  // If both are missing, the chip names only the file instead of a wrong minute.
  if (_isMediaFile(filename)) {
    if (num == null) return "";
    return tChip ? tChip("part", { num }) : `Teil ${num}`;
  }
  return tChip ? tChip("page", { num: num ?? 1 }) : `S. ${num ?? 1}`;
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
      const optText = optMatch[1].replace(/✓|\(richtig\)/g, "").trim();
      if (isCorrect) current.correct = current.options.length;
      current.options.push(optText);
    }
  }
  if (current && current.options.length > 0) questions.push(current);
  return questions;
}
