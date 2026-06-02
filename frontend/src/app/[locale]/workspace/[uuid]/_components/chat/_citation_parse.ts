// Pure citation-token parsing, separated from React rendering so it can be unit
// tested in isolation. Chip syntax (all optional except the position):
//   [Q1:uuid, S. 2 @start-end | keyword]   PDF with exact offset span
//   [1, 05:32 | keyword]                    media timestamp
//   [S. 2]                                  bare page
// CJK lenticular brackets 【】 (U+3010/U+3011) are accepted in place of [].

export interface CitationFields {
  qNum: number | null;
  uuid: string | null;
  page: number;                 // 0 for a timestamp citation
  offsets?: [number, number];   // Architecture-B exact char span into the page text
  timestamp: string | null;
  keyword: string | null;       // keyword OR verbatim span (offset chips)
  index: number;                // match start in the source string
  length: number;               // match length
}

// A fresh stateful (/g) matcher each call.
// Groups: 1=qnum 2=uuid 3=page 4=offStart 5=offEnd 6=timestamp 7=keyword
export function citationPattern(): RegExp {
  return /[[【](?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)(?:\s*@(\d+)-(\d+))?|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*[|❘]\s*([^\]】]+))?\s*[\]】]/g;
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
      offsets: m[4] && m[5] ? [parseInt(m[4]), parseInt(m[5])] : undefined,
      timestamp: m[6] || null,
      keyword: m[7]?.trim().replace(/^["']+|["']+$/g, "").trim() || null,
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


// A URL or bare email inside a citation keyword (it can be verbatim source text, e.g.
// a slide listing "Mensch und Computer, https://muc2026…/" or "E-Mail: x@th-luebeck.de")
// must be removed BEFORE the text reaches react-markdown: gfm autolinks both URLs AND
// bare email addresses, which splits the [..|..] token into separate nodes so the chip
// never forms and the raw brackets leak as plain text. The email alternation needs at
// least one local-part char immediately before '@' (a space there means it's the
// '@start-end' offset token, not an email) and a dotted domain.
const _URL_IN_CITE =
  /https?:\/\/[^\s\]】|❘]+|www\.[^\s\]】|❘]+|[^\s\]】|❘@]+@[\w.-]+\.[A-Za-z]{2,}/gi;

// Make citation tokens safe to hand to react-markdown. For every "[ … | … ]"-shaped
// token: strip URLs from the keyword, swap '|' → '❘' (a bare '|' is a table-column
// break in gfm), and tidy whitespace / a now-empty keyword. Finally collapse an
// exact-duplicate citation emitted back-to-back ("[…]. […]" → "[…]"). This is the
// last line of defence: it fixes already-stored answers and any time the model (or
// an offset span) puts a URL in the keyword — no chip is ever shown as raw text.
export function sanitizeCitationsForMarkdown(text: string): string {
  let out = text.replace(/[[【]([^\]】]*[|❘][^\]】]*)[\]】]/g, (m) =>
    m
      .replace(_URL_IN_CITE, "")
      .replace(/\|/g, "❘")
      .replace(/\s{2,}/g, " ")
      .replace(/\s+([❘\]】])/g, "$1")   // no space before the separator / close
      .replace(/❘\s*([\]】])/g, "$1"),  // drop the separator if the keyword went empty
  );
  out = out.replace(/(\[[^\]\n❘]*❘[^\]\n]*\])(?:\s*\.?\s*\1)+/g, "$1");
  // A thematic break (---/***/___) is a separator, not a claim. Older answers may
  // have a citation appended to it; strip the chip(s) so it renders as a clean rule.
  out = out.replace(/^(\s{0,3}(?:[-*_]\s*){3,})(?:\s*\[[^\]\n]*\])+\s*$/gm, "$1");
  return out;
}


// Remove every citation chip (incl. the optional @start-end offset token) — used
// when copying an answer to the clipboard.
export function stripCitations(text: string): string {
  return text.replace(
    /[[【](?:Q?\d+(?::[a-f0-9]{6,64})?,\s*)?(?:S\.\s*\d+(?:\s*@\d+-\d+)?|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*[|❘][^\]】]+)?[\]】]/g,
    "",
  );
}

// Compose the text shown for an assistant message. While streaming, grounded lines
// (filled by `line_done`) are shown verbatim (their chips are already correct); every
// other line has its raw LLM chips stripped, so an unverified chip is never visible.
// Once streaming is done the canonical `content` is rendered unchanged.
export function buildDisplayContent(
  content: string,
  groundedLines: (string | undefined)[] | undefined,
  streaming: boolean,
): string {
  if (!streaming) return content;
  const g = groundedLines ?? [];
  return content
    .split("\n")
    .map((raw, i) => g[i] ?? stripCitations(raw))
    .join("\n");
}
