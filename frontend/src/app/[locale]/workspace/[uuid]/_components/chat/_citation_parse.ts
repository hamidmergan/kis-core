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

// Remove every citation chip (incl. the optional @start-end offset token) — used
// when copying an answer to the clipboard.
export function stripCitations(text: string): string {
  return text.replace(
    /[[【](?:Q?\d+(?::[a-f0-9]{6,64})?,\s*)?(?:S\.\s*\d+(?:\s*@\d+-\d+)?|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*[|❘][^\]】]+)?[\]】]/g,
    "",
  );
}
