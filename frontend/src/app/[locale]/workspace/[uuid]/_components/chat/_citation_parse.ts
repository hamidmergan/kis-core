// Reads the citation markers, old forms with extra fields are tolerated.

export interface CitationFields {
  qNum: number | null;
  uuid: string | null;
  page: number;                 // 0 for a timestamp citation
  timestamp: string | null;
  index: number;                // match start in the source string
  length: number;               // match length
}

// A fresh matcher per call, trailing extras are discarded.
export function citationPattern(): RegExp {
  return /[[【](?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))[^\]】]*[\]】]/g;
}

// Does this answer carry a citation at all?
export function hasCitations(text: string): boolean {
  return citationPattern().test(text);
}

export function parseCitationFields(text: string): CitationFields[] {
  const re = citationPattern();
  const out: CitationFields[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    out.push({
      qNum: m[1] ? parseInt(m[1]) : null,
      uuid: m[2] || null,
      page: m[3] ? parseInt(m[3]) : 0,
      timestamp: m[4] || null,
      index: m.index,
      length: m[0].length,
    });
  }
  return out;
}

// Two neighbouring citations to the same page collapse into one chip.
export function citationsAreAdjacentSameTarget(
  text: string,
  a: CitationFields,
  b: CitationFields,
  sourceKeyA: string,
  sourceKeyB: string,
): boolean {
  if (a.timestamp || b.timestamp) return false;     // media chips stay separate
  if (a.page <= 0 || b.page <= 0) return false;      // need a real page on both
  if (a.page !== b.page) return false;               // different page → different chip
  if (sourceKeyA !== sourceKeyB) return false;       // different source → different chip
  const gap = text.slice(a.index + a.length, b.index);
  return /^[\s.,;:!?…]*$/u.test(gap);                 // only whitespace / sentence punctuation between them
}


// Cleans up citations that would break a separator line or a table.
export function sanitizeCitationsForMarkdown(text: string): string {
  let out = stripStrayCitations(normalizeTableBlocks(text));
  out = out.replace(/^(\s{0,3}(?:[-*_]\s*){3,})(?:\s*\[[^\]\n]*\])+\s*$/gm, "$1");
  out = out.replace(_TABLE_TRAIL_CHIP, (_m, row: string, chips: string) =>
    row.replace(/\s*\|\s*$/, ` ${chips.trim()} |`));
  return out;
}

// Empty 【…】 brackets are dropped, real citations stay.
const _STRAY_LENTICULAR = /\s?【(?![^】]*(?:S\.\s*\d|\d{1,2}:\d{2}))[^】]*】/g;
export function stripStrayCitations(text: string): string {
  return text.replace(_STRAY_LENTICULAR, "");
}

// Lifts indented tables to the margin, otherwise Markdown does not render them.
function _isTableRow(l: string): boolean {
  const s = l.trim();
  return s.startsWith("|") && s.endsWith("|") && (s.match(/\|/g)?.length ?? 0) >= 2;
}
function _isTableDelim(l: string): boolean {
  const s = l.trim();
  return s.length > 0 && s.includes("-") && /^[|\-: ]+$/.test(s);
}
function normalizeTableBlocks(text: string): string {
  if (!text.includes("|")) return text;
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    if (_isTableRow(lines[i]) && i + 1 < lines.length && _isTableDelim(lines[i + 1])) {
      if (out.length > 0 && out[out.length - 1].trim() !== "") out.push("");
      out.push(lines[i].trim());
      i++;
      while (i < lines.length && (_isTableRow(lines[i]) || _isTableDelim(lines[i]))) {
        out.push(lines[i].trim());
        i++;
      }
      if (i < lines.length && lines[i].trim() !== "") out.push("");
      continue;
    }
    out.push(lines[i]);
    i++;
  }
  return out.join("\n");
}

// A single citation marker, recognises a chip at the end of a table row.
const _CHIP_SRC =
  "[[【](?:Q?\\d+(?::[a-f0-9]{6,64})?,\\s*)?" +
  "(?:S\\.\\s*\\d+|\\d{1,2}:\\d{2}(?::\\d{2})?)" +
  "[^\\]】]*[\\]】]";
// A table-row line (`| … |`) followed only by chip(s) + optional sentence punctuation.
const _TABLE_TRAIL_CHIP =
  new RegExp(`^(\\s*\\|.*\\|)(\\s*(?:${_CHIP_SRC}\\s*[.;,]?\\s*)+)$`, "gm");


// Removes every citation, for copying an answer.
export function stripCitations(text: string): string {
  return text
    .replace(
      /[[【](?:Q?\d+(?::[a-f0-9]{6,64})?,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]】]*[\]】]/g,
      "",
    )
    .replace(_STRAY_LENTICULAR, "");   // also drop bare 【source】 placeholders
}
