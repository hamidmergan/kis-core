// Pure citation-token parsing, separated from React rendering so it can be unit
// tested in isolation. Chips are NAV-ONLY (position, no offsets/keyword):
//   [Q1:uuid, S. 2]   PDF page (optional Q-num, optional embedded source uuid)
//   [1, 05:32]        media timestamp
//   [S. 2]            bare page
// Legacy tokens with a trailing "@start-end" offset and/or "| keyword" still parse
// to their page/timestamp — the extras are tolerated and discarded (forward-tolerant
// for already-stored answers / saved notes). CJK lenticular brackets 【】
// (U+3010/U+3011) are accepted in place of [].

export interface CitationFields {
  qNum: number | null;
  uuid: string | null;
  page: number;                 // 0 for a timestamp citation
  timestamp: string | null;
  index: number;                // match start in the source string
  length: number;               // match length
}

// A fresh stateful (/g) matcher each call.
// Groups: 1=qnum 2=uuid 3=page 4=timestamp. Any trailing junk before the closing
// bracket (legacy "@1-9 | kw") is matched by [^\]】]* and discarded.
export function citationPattern(): RegExp {
  return /[[【](?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))[^\]】]*[\]】]/g;
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

// Two citations collapse into ONE chip when they point at the same PDF page of the
// same source and sit directly next to each other in the answer text, e.g.
// "… [1] S. 15 [1] S. 15" or "Passt die Fragestellung zum Thema? [7] S. 8. [7] S. 8".
// "Next to each other" means the gap between them is only whitespace and/or sentence
// punctuation — the model often ends a clause with one citation and immediately opens
// the next ("…?]. […"), which is still the same redundant target, not a new claim. Any
// letters/digits in the gap (real claim text, or a word that happens to end in a dot
// like "etc.") block the merge. Media timestamps and bare-page citations never merge.
// `sourceKeyA/B` are the caller-resolved source identities (uuid via qmap), so two
// adjacent "[1] S. 15" tokens that resolve to the same source merge even though the
// raw token has no uuid. Language-agnostic (no wordlist). Pure for unit testing.
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


// Make citation tokens safe to hand to react-markdown. Chips are nav-only now, so
// there is no in-chip '|' / keyword to scrub. Two structural fixes remain:
//   1. A thematic break (---/***/___) is a separator, not a claim. Older answers may
//      have a citation appended to it; strip the chip(s) so it renders as a clean rule.
//   2. The model often appends a citation AFTER the final pipe of a table row — incl.
//      the header. That trailing chip is a phantom extra column, so the header's cell
//      count no longer matches the delimiter row and gfm refuses to parse the block as
//      a table (it leaks as raw text with literal pipes). Tuck any such trailing chip
//      back into the last cell so every row keeps its pipe-defined column count.
// Language-agnostic; chips already inside a cell stay untouched.
export function sanitizeCitationsForMarkdown(text: string): string {
  let out = text.replace(/^(\s{0,3}(?:[-*_]\s*){3,})(?:\s*\[[^\]\n]*\])+\s*$/gm, "$1");
  out = out.replace(_TABLE_TRAIL_CHIP, (_m, row: string, chips: string) =>
    row.replace(/\s*\|\s*$/, ` ${chips.trim()} |`));
  return out;
}

// One nav-only citation token (page or timestamp, optional q-num/uuid, trailing junk
// tolerated). Used to recognise a chip trailing a table row.
const _CHIP_SRC =
  "[[【](?:Q?\\d+(?::[a-f0-9]{6,64})?,\\s*)?" +
  "(?:S\\.\\s*\\d+|\\d{1,2}:\\d{2}(?::\\d{2})?)" +
  "[^\\]】]*[\\]】]";
// A table-row line (`| … |`) followed only by chip(s) + optional sentence punctuation.
const _TABLE_TRAIL_CHIP =
  new RegExp(`^(\\s*\\|.*\\|)(\\s*(?:${_CHIP_SRC}\\s*[.;,]?\\s*)+)$`, "gm");


// Remove every citation chip (nav-only; legacy trailing offset/keyword tolerated) —
// used when copying an answer to the clipboard.
export function stripCitations(text: string): string {
  return text.replace(
    /[[【](?:Q?\d+(?::[a-f0-9]{6,64})?,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]】]*[\]】]/g,
    "",
  );
}
