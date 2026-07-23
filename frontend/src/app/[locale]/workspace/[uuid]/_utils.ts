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

/** Convert **bold** and *italic* markdown to HTML (XSS-safe). Flashcards render through
 * this, and there is no KaTeX on them, so LaTeX is flattened to Unicode first. */
export function _md(text: string): string {
  const esc = _mathToUnicode(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
}

// Models write math in LaTeX ("$\rightarrow$", "$x^2$"), so the chat renders it with
// KaTeX. The catch: a single "$" is also a currency sign, and remark-math would pair
// "5$ ... 10$" into one bogus formula that swallows the prose in between. So before
// handing text to Markdown, escape every "$" pair whose content does not look like math.
// Math means: a LaTeX command/sub-/superscript/brace, OR a short span with no spaces
// (covers "$n$", "$a+b$"). Language-agnostic, it only looks at symbols, never at words.
// Code spans and fences are skipped, and "$$…$$" display math is left as one unit.
// An unclosed "$" stays plain text, so a streaming answer only snaps into a rendered
// formula once the model has written the closing "$".
const _CODE_SPANS = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g;
const _DOLLAR_SPANS = /\$\$[\s\S]*?\$\$|(?<!\\)\$([^$\n]{1,200})(?<!\\)\$/g;
function _looksLikeMath(inner: string): boolean {
  if (/[\\^_{}]/.test(inner)) return true;
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

// Same LaTeX, but for the surfaces that show model text as PLAIN text (note preview
// line, flashcard front/back) — no KaTeX there, so "$\rightarrow$" would sit in the UI
// verbatim. Flatten the formula to the closest Unicode instead: symbols by table,
// fractions to "a/b", sub-/superscripts to their Unicode digits, and an unknown command
// at least loses its backslash. Currency is protected by the same _looksLikeMath rule
// the renderer uses, so "5$ … 10$" stays untouched here as well.
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

// Localized label for a source-citation chip. The page/part wording comes from
// the i18n "sourceChip" namespace, so it follows the UI language (S./Teil in DE,
// p./Part in EN, and whatever a future locale file provides) — no hardcoded
// per-language strings. `tChip` is `useTranslations("sourceChip")`; when omitted
// (non-React callers / plain text export) it falls back to the German wording.
export type ChipLabelT = (key: "page" | "part", values: { num: number }) => string;

export function _chunkLabel(
  filename: string,
  num: number,
  startTime?: number | null,
  tChip?: ChipLabelT,
): string {
  if (_isMediaFile(filename) && startTime != null) return _formatTime(startTime);
  if (_isMediaFile(filename)) return tChip ? tChip("part", { num }) : `Teil ${num}`;
  return tChip ? tChip("page", { num }) : `S. ${num}`;
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
