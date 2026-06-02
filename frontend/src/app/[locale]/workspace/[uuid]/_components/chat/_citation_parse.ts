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
// same source and sit directly next to each other (only whitespace between them in
// the answer text, e.g. "… [1] S. 15 [1] S. 15"). Media timestamps and bare-page
// citations never merge. `sourceKeyA/B` are the caller-resolved source identities
// (uuid via qmap), so two adjacent "[1] S. 15" tokens that resolve to the same
// source merge even though the raw token has no uuid. Pure for unit testing.
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
  return /^\s*$/.test(gap);                           // only whitespace may separate them
}


// A URL inside a citation keyword (it can be verbatim source text, e.g. a slide
// listing "Mensch und Computer, https://muc2026…/") must be removed BEFORE the text
// reaches react-markdown: gfm autolinks the URL, which splits the [..|..] token into
// separate nodes so the chip never forms and the raw brackets leak as plain text.
const _URL_IN_CITE = /https?:\/\/[^\s\]】|❘]+|www\.[^\s\]】|❘]+/gi;

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
