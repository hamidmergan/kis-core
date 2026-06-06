// Citation highlight orchestration for the PDF viewer (chip click → highlight).
// Turns a span offset (Architecture B) or a raw search string + page number into a
// passive YELLOW marker, drawn as an ephemeral Highlight annotation (created but
// NEVER committed, so the PDF file is untouched). It is NOT a text selection, so a
// chip click never triggers the selection action-popup. The user's own manual text
// selection still uses EmbedPDF's native blue selection + popup (untouched here).
//
// EmbedPDF-internal APIs in use (NOT in public docs — re-verify on @embedpdf bump):
//   annotation.createAnnotation / purgeAnnotation / deselectAnnotation,
//   engine.getPageGeometry, engine.getTextSlices, selection.getState (geometry cache).
// Public Search plugin can't replace this: it only highlights exact matches,
// not the surrounding sentence that _findSentBounds expands a keyword hit to.

export type HighlightRefs = {
  prevHighlightRef: { current: { pageIndex: number; ids: string[] } | null };
  // Tracks the current ephemeral citation highlight(s) — Highlight annotations that
  // are NEVER committed, so they never touch the PDF file — so they can be purged on
  // the next chip click or when the user dismisses it. A merged chip draws several
  // annotations (one per cited region), hence a list of ids. `scrollY` is the
  // topmost region's page-coordinate y, so the jump chip can re-center the exact
  // spot instead of the page top.
  citationHighlightRef: { current: { pageIndex: number; ids: string[]; scrollY?: number } | null };
  // Toggles the "dismiss highlight" control in the viewer.
  onHighlightActive?: (active: boolean) => void;
};

// One highlight target for a (possibly merged) citation chip: a server-computed
// offset span and/or a verbatim keyword to relocate it on the live page.
export type CitationSpan = { offsets?: [number, number]; keyword?: string };

// Controls how drawCitationHighlight integrates with the current marker set:
//   append=false (default): purge previous markers, start a new set, scroll into view.
//   append=true: add to the current set (no purge) — used for extra regions of a
//   merged chip. scroll defaults to !append; pass explicitly to override.
//   highlightEnabled=false (default true): user turned the yellow citation marker
//   off in settings — still scroll to the exact spot, but draw no annotation.
type DrawOpts = { append?: boolean; scroll?: boolean; highlightEnabled?: boolean };

// Citation highlight = passive yellow marker (NOT a text selection), so a chip
// click never triggers the selection action-popup. Single colour constant — swap
// for a tenant brand colour here if desired.
const CITATION_HL_COLOR = "#FFE14D";   // highlighter yellow
const CITATION_HL_OPACITY = 0.4;
const HIGHLIGHT_SUBTYPE = 9;           // PdfAnnotationSubtype.HIGHLIGHT

// Position-preserving diacritic fold + lowercase: every character maps to exactly
// ONE character (its NFKD base letter), so the result has the SAME length and the
// match index still aligns with cleanToRaw for the highlight geometry. Makes the
// keyword search diacritic-insensitive, so a citation keyword with umlauts
// ("Dezimalbrüche") still matches a PDF text layer whose font lost or mangled them
// ("Dezimalbruche…") — common in LaTeX/maths PDFs. Language-agnostic.
function _foldDiacritics(s: string): string {
  let out = "";
  for (let i = 0; i < s.length; i++) {
    const d = s[i].normalize("NFKD");
    out += d[0] || s[i];
  }
  return out.toLowerCase();
}


// Map a raw text-layer index to the geometry/glyph index space that
// applyInstantSelection expects. Some pages carry "phantom" glyphs (no visible
// text), so the geometry index can run ahead of the raw text index; binary-search
// to realign. Shared by the offset path and the legacy keyword path.
function makeFindGeo(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  engine: any, doc: any, targetPageIndex: number, totalChars: number, rawLen: number,
): (rawIdx: number) => Promise<number> {
  const phantoms = totalChars - rawLen;
  return (rawIdx: number): Promise<number> => {
    if (phantoms === 0) return Promise.resolve(rawIdx);
    let lo = rawIdx + 1, hi = Math.min(rawIdx + 1 + phantoms, totalChars);
    const step = (): Promise<number> => {
      if (lo >= hi) return Promise.resolve(lo - 1);
      const mid = (lo + hi) >> 1;
      const t = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: mid }]);
      return (t?.toPromise?.() ?? Promise.resolve(null)).then((res: unknown) => {
        const len = (res as string[])?.[0]?.length ?? 0;
        if (len < rawIdx + 1) lo = mid + 1; else hi = mid;
        return step();
      });
    };
    return step();
  };
}


// Whitespace-collapsed, diacritic-folded view of a page string plus a map from
// each clean index back to the original raw index. MUST mirror the backend
// _collapse_fold so server-computed offsets and the client text fold identically.
// Exported for unit tests (parity with the backend folding contract).
export function _collapseFold(s: string): { clean: string; map: number[] } {
  let clean = "";
  const map: number[] = [];
  let inSpace = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (/\s/.test(ch)) {
      if (!inSpace) { clean += " "; map.push(i); inSpace = true; }
    } else {
      clean += (ch.normalize("NFKD")[0] || ch).toLowerCase();
      map.push(i);
      inSpace = false;
    }
  }
  return { clean, map };
}


// All start indices of `needle` in `hay` (capped), for occurrence disambiguation.
// Exported for unit tests.
export function _allIndexOf(hay: string, needle: string, cap = 24): number[] {
  const out: number[] = [];
  if (!needle) return out;
  let from = 0;
  let idx = hay.indexOf(needle, from);
  while (idx >= 0) {
    out.push(idx);
    from = idx + 1;
    if (out.length >= cap) break;
    idx = hay.indexOf(needle, from);
  }
  return out;
}


// Build per-line page-coordinate rects for the geometry char range [a, b] from the
// page glyph geometry. Same coordinate space the Selection plugin uses to build its
// highlight rects (min/max of glyph boxes, top-left origin, no y-flip), which is
// exactly what the annotation layer consumes — verified against @embedpdf internals.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildSegmentRects(g: any, a: number, b: number): { segmentRects: any[]; bbox: any } {
  const segs: { origin: { x: number; y: number }; size: { width: number; height: number } }[] = [];
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const run of (g.runs || [])) {
    const runStart = run.charStart;
    const runEnd = runStart + run.glyphs.length - 1;
    if (runEnd < a || runStart > b) continue;
    let lx = Infinity, ly = Infinity, hx = -Infinity, hy = -Infinity;
    for (let i = 0; i < run.glyphs.length; i++) {
      const idx = runStart + i;
      if (idx < a || idx > b) continue;
      const gl = run.glyphs[i];
      if (gl.flags === 2) continue; // empty glyph
      const x0 = gl.x, y0 = gl.y, x1 = gl.x + gl.width, y1 = gl.y + gl.height;
      if (x0 < lx) lx = x0; if (y0 < ly) ly = y0; if (x1 > hx) hx = x1; if (y1 > hy) hy = y1;
    }
    if (lx === Infinity) continue;
    segs.push({ origin: { x: lx, y: ly }, size: { width: hx - lx, height: hy - ly } });
    if (lx < minX) minX = lx; if (ly < minY) minY = ly; if (hx > maxX) maxX = hx; if (hy > maxY) maxY = hy;
  }
  if (!segs.length) return { segmentRects: [], bbox: null };
  return { segmentRects: segs, bbox: { origin: { x: minX, y: minY }, size: { width: maxX - minX, height: maxY - minY } } };
}


// Remove the current ephemeral citation highlight (purgeAnnotation does NOT modify
// the PDF — we never commit). Safe to call when none is active.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function clearCitationHighlight(refs: HighlightRefs, reg: unknown) {
  const cur = refs.citationHighlightRef?.current;
  if (!cur) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const anno = (reg as any)?.getPlugin?.("annotation")?.provides?.();
  for (const id of cur.ids) {
    try { anno?.purgeAnnotation?.(cur.pageIndex, id); } catch { /* ignore */ }
  }
  refs.citationHighlightRef.current = null;
  refs.onHighlightActive?.(false);
}


// Smoothly scroll the active citation highlight back into view. Re-centres the
// exact highlight position (page + the topmost region's y), not just the page top,
// mirroring the initial chip-click scroll. The annotation persists in EmbedPDF's
// model across page virtualization, so no re-draw is needed. Keeps the scroll
// plugin the only EmbedPDF surface the jump UI touches.
export function scrollToCitationPage(refs: HighlightRefs, reg: unknown) {
  const cur = refs.citationHighlightRef.current;
  if (!cur) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scroll = (reg as any)?.getPlugin?.("scroll")?.provides?.();
  scroll?.scrollToPage?.({
    pageNumber: cur.pageIndex + 1,
    ...(cur.scrollY != null ? { pageCoordinates: { x: 0, y: cur.scrollY } } : {}),
    behavior: "smooth",
    alignY: 50,
  });
}


// Draw the citation highlight as a passive yellow Highlight annotation (ephemeral:
// created but never committed). No text selection is made, so the selection
// action-popup never appears for a chip click. Purges any previous one first
// (one citation highlight at a time), deselects so no edit handles show, and
// scrolls the range into view.
// Exported for unit tests (the highlightEnabled gating contract).
export function drawCitationHighlight(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, docMgr: any, scroll: any, targetPageIndex: number, geoStart: number, geoEnd: number, g: any,
  opts: DrawOpts = {},
): boolean {
  const append = opts.append ?? false;
  const doScroll = opts.scroll ?? !append;
  // User turned the marker off (settings): skip drawing the annotation entirely
  // but still compute the bbox below and scroll to the exact spot — "jump only".
  const highlightEnabled = opts.highlightEnabled ?? true;
  const { segmentRects, bbox } = buildSegmentRects(g, geoStart, geoEnd);
  if (!segmentRects.length || !bbox) return false;
  if (highlightEnabled) {
    const anno = r.getPlugin?.("annotation")?.provides?.();
    const docId = docMgr.getActiveDocumentId?.();
    if (!anno?.createAnnotation || !docId) return false;
    if (!append) clearCitationHighlight(refs, r);   // fresh chip → one set at a time
    const id = `kis-cite-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    try {
      anno.createAnnotation(targetPageIndex, {
        type: HIGHLIGHT_SUBTYPE,
        pageIndex: targetPageIndex,
        id,
        rect: bbox,
        segmentRects,
        strokeColor: CITATION_HL_COLOR,
        color: CITATION_HL_COLOR,
        opacity: CITATION_HL_OPACITY,
        // readOnly + locked so the user can't accidentally select/drag/edit our marker.
        flags: ["readOnly", "locked"],
        created: new Date(),
      });
      anno.deselectAnnotation?.();      // no selection handles on the fresh annotation
      const cur = refs.citationHighlightRef.current;
      if (append && cur && cur.pageIndex === targetPageIndex) {
        cur.ids.push(id);
        if (bbox.origin.y < (cur.scrollY ?? Infinity)) cur.scrollY = bbox.origin.y;
      } else {
        refs.citationHighlightRef.current = { pageIndex: targetPageIndex, ids: [id], scrollY: bbox.origin.y };
      }
      refs.onHighlightActive?.(true);
    } catch {
      return false;
    }
  }
  if (scroll && doScroll) {
    scroll.scrollToPage({
      pageNumber: targetPageIndex + 1,
      pageCoordinates: { x: 0, y: bbox.origin.y },
      behavior: "instant",
      alignY: 50,
    });
  }
  return true;
}


// Architecture B: draw the exact server-computed span. The chip carries
// `offsets` = [start, end] (inclusive) into the page's pdfium text plus `anchor`
// = the verbatim span. We re-find the anchor on the live page (collapsed+folded,
// so it survives whitespace/diacritic drift), disambiguate the occurrence by the
// server offset, then draw it directly — NO sentence/paragraph expansion. Returns
// false (→ caller falls back to keyword search) when the anchor isn't on the page.
function tryHighlightByOffsets(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, doc: any, engine: any, docMgr: any, scroll: any,
  targetPageIndex: number, offsets: [number, number], anchor: string,
  opts: DrawOpts = {},
): Promise<boolean> {
  const bStart = offsets[0];
  const pageObj = doc.pages?.[targetPageIndex];
  if (!pageObj) return Promise.resolve(false);
  const selection = r.getPlugin?.("selection")?.provides?.();
  const cachedGeo = selection?.getState?.()?.geometry?.[targetPageIndex];
  const geoPromise: Promise<unknown> = cachedGeo
    ? Promise.resolve(cachedGeo)
    : (engine.getPageGeometry?.(doc, pageObj)?.toPromise?.() ?? Promise.resolve(null));

  return geoPromise.then((geo: unknown) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const g = geo as any;
    if (!g?.runs?.length) return false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lastRun = g.runs[g.runs.length - 1] as any;
    const totalChars = lastRun.charStart + lastRun.glyphs.length;
    if (totalChars < 1) return false;

    const sliceTask = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: totalChars }]);
    const slicePromise: Promise<unknown> = sliceTask?.toPromise?.() ?? Promise.resolve(null);
    return slicePromise.then((slices: unknown) => {
      const arr = slices as string[] | null;
      if (!arr?.[0]) return false;
      const R = arr[0];

      const cAnchor0 = _collapseFold((anchor || "").trim()).clean.trim();
      if (cAnchor0.length < 3) return false;
      const { clean: cR, map: cMap } = _collapseFold(R);

      // Find the span verbatim; on drift fall back to a leading prefix so a
      // partial still anchors. No hit at all → let the caller search by keyword.
      let used = cAnchor0;
      let occ = _allIndexOf(cR, used);
      if (!occ.length && cAnchor0.length > 16) {
        used = cAnchor0.slice(0, Math.max(16, Math.floor(cAnchor0.length * 0.6)));
        occ = _allIndexOf(cR, used);
      }
      if (!occ.length) return false;

      // Disambiguate duplicates by proximity to the server offset.
      let bestC = occ[0];
      let bestD = Infinity;
      for (const o of occ) {
        const d = Math.abs((cMap[o] ?? 0) - bStart);
        if (d < bestD) { bestD = d; bestC = o; }
      }
      const cEndIdx = Math.min(bestC + used.length - 1, cR.length - 1);
      const rawStart = cMap[bestC];
      const rawEnd = cMap[cEndIdx];
      if (rawStart == null || rawEnd == null || rawEnd < rawStart) return false;

      if (!docMgr.getActiveDocumentId?.()) return false;

      const findGeo = makeFindGeo(engine, doc, targetPageIndex, totalChars, R.length);
      return Promise.all([findGeo(rawStart), findGeo(rawEnd)]).then(([geoStart, geoEnd]) =>
        drawCitationHighlight(refs, r, docMgr, scroll, targetPageIndex, geoStart, geoEnd, g, opts),
      );
    });
  }).catch(() => false);
}


export function tryHighlightOnPage(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, doc: any, engine: any, docMgr: any, scroll: any,
  targetPageIndex: number, searchText: string, exactSelection: boolean = false,
  opts: DrawOpts = {},
): Promise<boolean> {
  const doScroll = opts.scroll ?? !opts.append;
  const pageObj = doc.pages?.[targetPageIndex];
  if (!pageObj) return Promise.resolve(false);

  const selection = r.getPlugin?.("selection")?.provides?.();
  const cachedGeo = selection?.getState?.()?.geometry?.[targetPageIndex];
  const geoPromise: Promise<unknown> = cachedGeo
    ? Promise.resolve(cachedGeo)
    : (engine.getPageGeometry?.(doc, pageObj)?.toPromise?.() ?? Promise.resolve(null));

  return geoPromise.then((geo: unknown) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const g = geo as any;
    // Image-only (OCR) page: the text is in the DB chunk but the PDF text-layer
    // is empty. Scroll to the page and treat as "handled" so the caller doesn't
    // fall back to nearby pages and highlight something unrelated there.
    const noRuns = !g?.runs?.length;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const lastRun = !noRuns ? (g.runs[g.runs.length - 1] as any) : null;
    const totalChars = lastRun ? lastRun.charStart + lastRun.glyphs.length : 0;
    if (noRuns || totalChars < 50) {
      if (scroll && doScroll) {
        scroll.scrollToPage({
          pageNumber: targetPageIndex + 1,
          behavior: "instant",
          alignY: 50,
        });
      }
      return true;
    }

    const sliceTask = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: totalChars }]);
    const slicePromise: Promise<unknown> = sliceTask?.toPromise?.() ?? Promise.resolve(null);

    return slicePromise.then((slices: unknown) => {
      const arr = slices as string[] | null;
      if (!arr?.[0]) return false;
      const rawPageText = arr[0];

      // Normalize whitespace for robust search, track mapping to raw indices
      const cleanToRaw: number[] = [];
      let cleanText = "";
      let inSpace = false;
      for (let i = 0; i < rawPageText.length; i++) {
        const ch = rawPageText[i];
        if (ch === "\r" || ch === "\n" || ch === " " || ch === "\t") {
          if (!inSpace) { cleanText += " "; cleanToRaw.push(i); inSpace = true; }
        } else { cleanText += ch; cleanToRaw.push(i); inSpace = false; }
      }

      // "Structured" page: short lines separated by newlines (slides, bullet
      // lists, title/cover pages, tables of contents). On these a newline that
      // starts a new line/item IS a boundary — otherwise sentence/paragraph
      // expansion walks across the whole slide and grabs neighbouring items,
      // headers and footers (the "title + footer also highlighted" problem).
      // Threshold is low so sparse title slides (a few short lines) qualify.
      // Language-agnostic: line count + length only, no words.
      const _rawNlCount = (rawPageText.match(/\n/g) || []).length;
      const _avgLineLen = _rawNlCount > 0 ? rawPageText.length / _rawNlCount : rawPageText.length;
      const _isBulletPage = _rawNlCount >= 2 && _avgLineLen < 80;

      // cleanText collapses all raw whitespace (incl. newlines) to single spaces,
      // so we need a separate check to test whether a clean-space position
      // corresponds to a raw newline — essential for bullet-page sentence bounds
      // and for trimming matches that crossed a bullet boundary.
      const _isRawNewlineAtClean = (cleanIdx: number): boolean => {
        if (cleanIdx < 0 || cleanIdx >= cleanText.length) return false;
        if (cleanText[cleanIdx] !== " ") return false;
        const rawStart = cleanToRaw[cleanIdx];
        const rawEnd = cleanIdx + 1 < cleanToRaw.length ? cleanToRaw[cleanIdx + 1] : rawPageText.length;
        for (let k = rawStart; k < rawEnd; k++) {
          if (rawPageText[k] === "\n" || rawPageText[k] === "\r") return true;
        }
        return false;
      };

      // Length (clean chars) of the line ending at `cleanEnd`, scanning back to
      // the previous raw newline. A short ended line is a heading/title/list
      // item; a near-full-width line is wrapped prose. Pure geometry of the
      // text — language- and script-independent.
      const _prevLineLen = (cleanEnd: number): number => {
        let s = 0;
        for (let i = cleanEnd; i >= 1; i--) {
          if (_isRawNewlineAtClean(i)) { s = i + 1; break; }
        }
        return cleanEnd - s + 1;
      };

      // Decide whether the newline at `startClean` starts a NEW line/item (a
      // boundary) vs a soft wrap of the same sentence. LANGUAGE-AGNOSTIC: uses
      // punctuation, list/number/date markers, Unicode letter case and line
      // length only — never language-specific word lists.
      const _looksLikeNewBullet = (startClean: number): boolean => {
        if (startClean <= 0) return true;
        let prevEnd = startClean - 1;
        while (prevEnd > 0 && cleanText[prevEnd] === " ") prevEnd--;
        const beforeSlice = cleanText.slice(Math.max(0, prevEnd - 40), prevEnd + 1);
        if (beforeSlice.endsWith("-")) return false;  // hyphenated wrap
        if (/[,;:]$/.test(beforeSlice)) return false; // clause / list continues
        let nextStart = startClean;
        while (nextStart < cleanText.length && cleanText[nextStart] === " ") nextStart++;
        const afterSlice = cleanText.slice(nextStart, Math.min(cleanText.length, nextStart + 60));
        if (!afterSlice) return true;
        // List/enumeration marker or a date-like number opens a new item.
        // NB: the middle dot '·' (U+00B7) is deliberately excluded — in maths it is
        // the multiplication operator ("· 2x"), handled below as a continuation.
        if (/^(?:[•▪◦‣⁃●○…*]|\.{2,}|[-–—]\s|\(?\d{1,3}[.)]\s)/.test(afterSlice)) return true;
        if (/^\d{1,4}[.\-/]\d{1,2}(?:[.\-/]\d{1,4})?\b/.test(afterSlice)) return true;
        if (/[.!?]$/.test(beforeSlice)) return true;  // previous sentence ended
        // Anything that does NOT start with an uppercase LETTER continues the line:
        // lowercase prose wraps, but ALSO maths fragments that pdfium puts on their
        // own line — primes (′″), exponents (², ⁿ), operators (− + · = /), digits,
        // parentheses. Without this, "Die Ableitung lautet also F" + "′(x) = −sin(x²)"
        // is cut before the prime. Mirrors the backend _line_is_boundary.
        if (!/^\p{Lu}/u.test(afterSlice)) return false;
        // Ambiguous (Title-case line after another, no punctuation): a SHORT
        // ended line is a heading/title/standalone item → boundary; a long line
        // is wrapped prose → keep joined. Length, not language.
        if (_prevLineLen(prevEnd) <= 55) return true;
        return false;
      };

      let cleanInput = searchText.replace(/\s+/g, " ").trim()
        .replace(/^\d{1,3}\s+/, "").trim();
      // For LLM-cited sources (exactSelection=false) we trim very long quotes to
      // a central window so a 900-char quote doesn't match across a whole PPTX
      // slide. For a verbatim user-popup selection (exactSelection=true) the
      // user's chosen text IS the intended highlight — don't trim or alter it.
      if (!exactSelection && cleanInput.length > 150) {
        const mid = Math.floor(cleanInput.length / 2);
        cleanInput = cleanInput.slice(Math.max(0, mid - 60), Math.min(cleanInput.length, mid + 60)).trim();
      }
      // Diacritic-folded (still 1:1 length) so the search tolerates a PDF text layer
      // that lost/mangled umlauts; matchStart/End stay aligned with cleanToRaw.
      const ptLower = _foldDiacritics(cleanText);
      const inputWords = _foldDiacritics(cleanInput).split(" ").filter(w => w.length > 0);

      // Find keywords on the page — try as phrase first, then individual keywords
      let matchStart = -1;
      let matchEnd = -1;
      // If the full search text matches verbatim AND is long enough to span multiple
      // sentences (e.g. a user-selected paragraph), use the match bounds directly instead
      // of expanding via sentence boundaries — the selection already defines exact bounds.
      // Short keyword phrases still get sentence expansion as before.
      let exactFullMatch = false;

      // 1. Try full phrase match
      const fullPhrase = inputWords.join(" ");
      const fullIdx = ptLower.indexOf(fullPhrase);
      if (fullIdx >= 0) {
        matchStart = fullIdx;
        matchEnd = fullIdx + fullPhrase.length - 1;
        if (fullPhrase.length >= 120) exactFullMatch = true;
      }

      // Bullet-page leading-bullet trim: the backend may have stored a ±80
      // char context window that includes the previous bullet ("Themenfindung
      // 01.04.2026 Webkonferenz..."). If the matched range crosses a raw
      // newline AND contains a date pattern after it, the real target is the
      // date-bullet — trim matchStart forward to that date.
      // Skip entirely for exactSelection: the user-popup selection IS the
      // intended highlight bounds; heuristics must not move them.
      if (matchStart >= 0 && _isBulletPage && !exactSelection) {
        // Numeric date in any common order/separator (01.04.2026, 2026-04-01,
        // 4/1). Language-agnostic — no localized month names.
        const dateRe = /\b\d{1,4}[.\-/]\d{1,2}(?:[.\-/]\d{1,4})?\b/;
        const matchedSlice = cleanText.slice(matchStart, matchEnd + 1);
        const dm = dateRe.exec(matchedSlice);
        if (dm && dm.index > 0) {
          let hasNlBeforeDate = false;
          for (let i = matchStart; i < matchStart + dm.index; i++) {
            if (_isRawNewlineAtClean(i)) { hasNlBeforeDate = true; break; }
          }
          if (hasNlBeforeDate) {
            matchStart = matchStart + dm.index;
            exactFullMatch = false;
          }
        }
        // Trim matchEnd: if a newline after the date is followed by a line
        // that looks like the NEXT bullet, shrink matchEnd to before that
        // newline. Wrapped continuation lines (plain text, no marker) are
        // kept so multi-line bullets stay whole.
        for (let i = matchStart + 1; i <= matchEnd; i++) {
          if (!_isRawNewlineAtClean(i)) continue;
          if (_looksLikeNewBullet(i + 1)) {
            matchEnd = i - 1;
            while (matchEnd > matchStart && cleanText[matchEnd] === " ") matchEnd--;
            exactFullMatch = false;
            break;
          }
        }
      }

      // exactSelection = true (popup selection / schedule chip): the caller
      // supplied a precise verbatim quote. If it doesn't match the page,
      // DO NOT fall back to sliding-window or single-keyword search — that
      // would highlight something unrelated (e.g. a random date in the
      // footer of a PPTX slide). Just scroll and bail out.
      if (exactSelection && matchStart < 0) {
        if (scroll && doScroll) {
          scroll.scrollToPage({
            pageNumber: targetPageIndex + 1,
            behavior: "instant",
            alignY: 50,
          });
        }
        return true;
      }

      // 2. Try sliding windows (decreasing size)
      if (matchStart < 0) {
        outer:
        for (let windowSize = inputWords.length; windowSize >= 2; windowSize--) {
          for (let skip = 0; skip <= inputWords.length - windowSize; skip++) {
            const phrase = inputWords.slice(skip, skip + windowSize).join(" ");
            const idx = ptLower.indexOf(phrase);
            if (idx >= 0) {
              matchStart = idx;
              matchEnd = idx + phrase.length - 1;
              break outer;
            }
          }
        }
      }

      // 3. Find individual keywords and use the position of the most specific one (longest word)
      if (matchStart < 0) {
        const sorted = [...inputWords].sort((a, b) => b.length - a.length);
        for (const word of sorted) {
          if (word.length < 4) continue;
          const idx = ptLower.indexOf(word);
          if (idx >= 0) {
            matchStart = idx;
            matchEnd = idx + word.length - 1;
            break;
          }
        }
      }

      if (matchStart < 0 || matchEnd < 0) return false;

      // Expand to sentence boundaries (period, newline, or start/end of text),
      // skipping abbreviation/number dots. LANGUAGE-AGNOSTIC: no wordlist — a real
      // sentence end is continued by an uppercase start, so a dot followed (after a
      // space) by a digit or lowercase letter is an abbreviation/number continuation.
      const _isAbbrevDot = (text: string, dotIdx: number) => {
        if (dotIdx < 1) return false;
        // Dot directly followed by a letter (no space) is inside an abbreviation
        // (e.g. "z.B.", "d.h.", "U.S.A."). Digits glued to the dot are NOT treated as
        // abbreviation to keep footnote markers ("erprobt.11") as real sentence ends —
        // decimal numbers like "3.14" are covered by the digit-before-dot rule below.
        const next = text[dotIdx + 1];
        if (next && /\p{L}/u.test(next)) return true;
        // Single uppercase letter + dot (e.g. "S." "A.")
        if (dotIdx >= 1 && /^\p{Lu}$/u.test(text[dotIdx - 1]) && (dotIdx < 2 || text[dotIdx - 2] === " ")) return true;
        // Number + dot (e.g. "3." "49%.")
        if (/\d$/.test(text.slice(Math.max(0, dotIdx - 1), dotIdx))) return true;
        // SPACE then a digit / lowercase letter → abbreviation or number continuation
        // ("ca. 6-7", "ca. 2 Seiten", "z.B. das"). The space requirement keeps glued
        // footnote markers ("erprobt.11") as real sentence ends. Mirrors the backend.
        if (next && /\s/.test(next)) {
          let k = dotIdx + 1;
          while (k < text.length && /\s/.test(text[k])) k++;
          if (k < text.length && /[\d\p{Ll}]/u.test(text[k])) return true;
        }
        return false;
      };
      // Helper: find sentence boundaries around a position
      const _findSentBounds = (startPos: number, endPos: number): [number, number] => {
        let sStart = startPos, sEnd = endPos;
        for (let i = startPos - 1; i >= 0; i--) {
          const ch = cleanText[i];
          // PPTX bullet page: only newlines followed by a NEW bullet marker
          // count as sentence boundary. Wrap lines continue the sentence.
          if (_isBulletPage && _isRawNewlineAtClean(i) && _looksLikeNewBullet(i + 1)) {
            sStart = i + 1;
            while (sStart < startPos && cleanText[sStart] === " ") sStart++;
            break;
          }
          if (ch === "\n" || ch === "!" || ch === "?") {
            sStart = i + 1;
            while (sStart < startPos && cleanText[sStart] === " ") sStart++;
            break;
          }
          if (ch === "." && !_isAbbrevDot(cleanText, i)) {
            sStart = i + 1;
            while (sStart < startPos && cleanText[sStart] === " ") sStart++;
            break;
          }
          if (i === 0) sStart = 0;
        }
        for (let i = endPos + 1; i < cleanText.length; i++) {
          const ch = cleanText[i];
          if (_isBulletPage && _isRawNewlineAtClean(i) && _looksLikeNewBullet(i + 1)) { sEnd = i - 1; break; }
          if (ch === "\n" || ch === "!" || ch === "?") { sEnd = i; break; }
          if (ch === "." && !_isAbbrevDot(cleanText, i)) { sEnd = i; break; }
          if (i === cleanText.length - 1) sEnd = i;
        }
        return [sStart, sEnd];
      };

      // Strip a leading "page-number [+ numbered heading]" prefix from a position.
      // Needed because _findSentBounds scans backward for a sentence-ending period and
      // treats "1." / "4.4." as abbreviations, so pStart often lands at position 0 on
      // pages that begin with a section heading — swallowing page number and heading
      // into the highlight.
      // Check whether the whitespace run starting at a given raw index contains a newline.
      const _wsRunHasNewline = (rawIdx: number): boolean => {
        for (let i = rawIdx; i < rawPageText.length; i++) {
          const ch = rawPageText[i];
          if (ch === "\n") return true;
          if (ch !== " " && ch !== "\r" && ch !== "\t") return false;
        }
        return false;
      };
      // Split cleanText (starting at pos) into "lines" using whitespace runs that cross
      // a newline in raw as line boundaries. Strip leading lines that are page numbers
      // or numbered section headings; stop at the first content line.
      const _stripLeadingHeading = (pos: number): number => {
        let p = pos;
        const ws = cleanText.slice(p, Math.min(cleanText.length, p + 10)).match(/^\s+/);
        if (ws) p += ws[0].length;
        const endScan = Math.min(cleanText.length, p + 200);
        const lines: Array<[number, number]> = [];
        let lineStart = p;
        for (let i = p; i < endScan; i++) {
          if (cleanText[i] === " ") {
            const rawIdx = cleanToRaw[i];
            if (rawIdx != null && _wsRunHasNewline(rawIdx)) {
              lines.push([lineStart, i]);
              lineStart = i + 1;
            }
          }
        }
        lines.push([lineStart, endScan]);
        let result = p;
        // Only strip pure page-number lines; keep heading lines (e.g. "4.4. Transferpotential")
        // as part of the marked content.
        for (const [ls, le] of lines) {
          const lineText = cleanText.slice(ls, le).trim();
          if (/^\d{1,3}$/.test(lineText)) { result = le + 1; continue; }
          break;
        }
        return Math.min(result, cleanText.length);
      };
      // PPTX bullet helper: cleanText collapses newlines to spaces, so
      // _findSentBounds can't see line breaks. Look up the original rawPageText
      // to find newline boundaries for the current bullet / line.
      const _hasNewlineAtClean = (cleanIdx: number): boolean => {
        if (cleanIdx < 0 || cleanIdx >= cleanText.length) return false;
        if (cleanText[cleanIdx] !== " ") return false;
        const rawStart = cleanToRaw[cleanIdx];
        const rawEnd = cleanIdx + 1 < cleanToRaw.length ? cleanToRaw[cleanIdx + 1] : rawPageText.length;
        for (let k = rawStart; k < rawEnd; k++) {
          if (rawPageText[k] === "\n" || rawPageText[k] === "\r") return true;
        }
        return false;
      };
      const _findLineBounds = (startPos: number, endPos: number): [number, number] => {
        let sStart = 0, sEnd = cleanText.length - 1;
        // Fallback for PPTX slides where paragraph expansion grabbed too much.
        // Stop only at newlines that look like real bullet boundaries —
        // otherwise a wrapped multi-line bullet gets cut to its first line.
        for (let i = startPos - 1; i >= 0; i--) {
          if (_hasNewlineAtClean(i) && _looksLikeNewBullet(i + 1)) { sStart = i + 1; break; }
        }
        for (let i = endPos + 1; i < cleanText.length; i++) {
          if (_hasNewlineAtClean(i) && _looksLikeNewBullet(i + 1)) { sEnd = i - 1; break; }
        }
        while (sStart < sEnd && cleanText[sStart] === " ") sStart++;
        while (sEnd > sStart && cleanText[sEnd] === " ") sEnd--;
        return [sStart, sEnd];
      };

      // Default to paragraph expansion. Skip when the full search text matched verbatim
      // (popup selection — user already defined the bounds). Fall back to sentence
      // expansion if the paragraph is unreasonably long (wall-of-text PDFs).
      let sentStart: number, sentEnd: number;
      if (exactSelection) {
        // Verbatim user-popup selection: highlight EXACTLY what the user marked,
        // no expansion to sentence/paragraph/line, regardless of length.
        sentStart = matchStart;
        sentEnd = matchEnd;
      } else if (exactFullMatch) {
        const stripped = _stripLeadingHeading(matchStart);
        sentStart = stripped < matchEnd ? stripped : matchStart;
        sentEnd = matchEnd;
      } else {
        // C2: a citation keyword match highlights only the SENTENCE that contains it —
        // never the surrounding paragraph (paragraph expansion pulled in unrelated text
        // like a disclaimer). The tight unit is one sentence; tight-or-off, never broad.
        [sentStart, sentEnd] = _findSentBounds(matchStart, matchEnd);
        // PPTX-converted PDFs: all bullets live in one text box, so a "sentence" can be
        // the whole slide. Back off to the current bullet/line via raw newline positions.
        if ((sentEnd - sentStart + 1) > cleanText.length * 0.6) {
          [sentStart, sentEnd] = _findLineBounds(matchStart, matchEnd);
        }
      }

      const rawStart = cleanToRaw[sentStart];
      const rawEnd = cleanToRaw[sentEnd];

      const findGeo = makeFindGeo(engine, doc, targetPageIndex, totalChars, rawPageText.length);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if (!docMgr.getActiveDocumentId?.()) return false;

      return Promise.all([findGeo(rawStart), findGeo(rawEnd)]).then(([geoStart, geoEnd]) => {
        // For exact selections (popup actions, schedule chips): constrain the
        // range to runs on the same VISUAL line as the match start. PPTX PDFs
        // sometimes store chars in an order that doesn't match the visual
        // layout, so a char-range can span header+body+footer even if the
        // match itself is short. Trimming by run y-coordinate prevents that.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const runs = (g.runs || []) as any[];
        if (exactSelection && runs.length) {
          const runYMid = (rn: { rect?: { y?: number; height?: number } }) => {
            const y = rn.rect?.y ?? 0;
            const h = rn.rect?.height ?? 0;
            return y + h / 2;
          };
          const startRun = runs.find(rn => geoStart >= rn.charStart && geoStart < rn.charStart + rn.glyphs.length);
          const endRun = runs.find(rn => geoEnd >= rn.charStart && geoEnd < rn.charStart + rn.glyphs.length) ?? startRun;
          if (startRun?.rect) {
            const startY = runYMid(startRun);
            const endY = endRun?.rect ? runYMid(endRun) : startY;
            const lineH = Math.max(startRun.rect.height ?? 0, 6);
            const tol = lineH * 0.7;
            // Allow every line the match actually spans, plus tolerance —
            // multi-line popup selections (wrapped bullets, cross-sentence)
            // should keep line 2+ instead of being cut to line 1.
            const yMin = Math.min(startY, endY) - tol;
            const yMax = Math.max(startY, endY) + tol;
            const startIdx = runs.indexOf(startRun);
            const endIdx = endRun ? runs.indexOf(endRun) : startIdx;
            let minStart = startRun.charStart;
            let maxEnd = (endRun ?? startRun).charStart + (endRun ?? startRun).glyphs.length - 1;
            for (let i = startIdx - 1; i >= 0; i--) {
              const rn = runs[i]; if (!rn.rect) break;
              const y = runYMid(rn);
              if (y < yMin || y > yMax) break;
              minStart = rn.charStart;
            }
            for (let i = endIdx + 1; i < runs.length; i++) {
              const rn = runs[i]; if (!rn.rect) break;
              const y = runYMid(rn);
              if (y < yMin || y > yMax) break;
              maxEnd = rn.charStart + rn.glyphs.length - 1;
            }
            geoStart = Math.max(geoStart, minStart);
            geoEnd = Math.min(geoEnd, maxEnd);
          }
        }
        return drawCitationHighlight(refs, r, docMgr, scroll, targetPageIndex, geoStart, geoEnd, g, opts);
      });
    });
  }).catch(() => false);
}

export function doHighlightSearch(
  refs: HighlightRefs, reg: unknown, page: number, text: string,
  exactSelection: boolean = false, offsets?: [number, number],
  highlightEnabled: boolean = true,
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = reg as any;
  const opts: DrawOpts = { highlightEnabled };
  const scroll = r.getPlugin?.("scroll")?.provides?.();
  scroll?.scrollToPage?.({ pageNumber: page, behavior: "instant" });

  const engine = r.getEngine?.();
  const docMgr = r.getPlugin?.("document-manager")?.provides?.();
  if (!engine || !docMgr) return;

  const doc = docMgr.getActiveDocument?.();
  if (!doc) return;

  // Clear the previous citation highlight (and any stray selection) before a new
  // chip click — only one citation marker at a time.
  clearCitationHighlight(refs, r);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const selCap = r.getPlugin?.("selection")?.provides?.() as any;
  const activeDocId = docMgr.getActiveDocumentId?.();
  try { selCap?.clear?.(activeDocId); } catch { /* ignore */ }
  refs.prevHighlightRef.current = null;

  if (!text?.trim()) return;

  const pageIndex = page - 1;

  // Only try the exact cited page. Falling back to nearby pages would mean
  // a "[1] S. 4" chip could silently highlight something on S. 3 or S. 5 when
  // the target is an OCR/image page whose PDF text layer doesn't contain the
  // cited text. Better: scroll to the right page and highlight nothing.
  //
  // Architecture B/C2: when the chip carries an exact span offset, draw it directly
  // (no re-finding / no expansion). On failure (span not on the page, geometry
  // unavailable, pdfium/OCR drift) fall back to the keyword search — but that search
  // now highlights only the matched SENTENCE, never the whole paragraph (C2), so the
  // fallback can be tight-but-maybe-off, never a broad block.
  if (offsets && !exactSelection) {
    tryHighlightByOffsets(refs, r, doc, engine, docMgr, scroll, pageIndex, offsets, text, opts)
      .then((ok) => {
        if (!ok) tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection, opts);
      })
      .catch(() => {
        tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection, opts);
      });
    return;
  }

  tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection, opts);
}


// Merged citation chip: mark EVERY cited region on one page in a single ephemeral
// annotation set. Spans are drawn sequentially — the first purges the previous
// chip's markers and scrolls into view; the rest append (no purge, no scroll), so
// the page ends up with one yellow mark per region. Each span tries its exact offset
// first, then a keyword search (C2: sentence-tight, never a paragraph); a region that
// can't be located by either is simply skipped.
export function doMultiHighlightSearch(
  refs: HighlightRefs, reg: unknown, page: number, spans: CitationSpan[],
  highlightEnabled: boolean = true,
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = reg as any;
  const scroll = r.getPlugin?.("scroll")?.provides?.();
  scroll?.scrollToPage?.({ pageNumber: page, behavior: "instant" });

  const engine = r.getEngine?.();
  const docMgr = r.getPlugin?.("document-manager")?.provides?.();
  if (!engine || !docMgr) return;
  const doc = docMgr.getActiveDocument?.();
  if (!doc) return;

  // Clear previous markers + any stray selection once, up front. Every span then
  // appends, so a span that fails to draw can never leave a stale marker behind.
  clearCitationHighlight(refs, r);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const selCap = r.getPlugin?.("selection")?.provides?.() as any;
  try { selCap?.clear?.(docMgr.getActiveDocumentId?.()); } catch { /* ignore */ }
  refs.prevHighlightRef.current = null;

  const pageIndex = page - 1;
  const targets = spans.filter((s) => (s.keyword && s.keyword.trim()) || s.offsets);
  if (!targets.length) return;

  // Sequential: the first drawn region scrolls into view, later ones don't.
  let chain: Promise<unknown> = Promise.resolve();
  targets.forEach((span, idx) => {
    const opts: DrawOpts = { append: true, scroll: idx === 0, highlightEnabled };
    const text = (span.keyword || "").trim();
    chain = chain
      .then(() => {
        // Offset first; on failure fall back to the keyword search (C2: sentence-
        // tight, never a paragraph). A region with neither offset nor keyword is skipped.
        if (span.offsets && text) {
          return tryHighlightByOffsets(refs, r, doc, engine, docMgr, scroll, pageIndex, span.offsets, text, opts)
            .then((ok) => (ok ? true : (text ? tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, false, opts) : false)));
        }
        if (text) return tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, false, opts);
        return false;
      })
      .catch(() => false);
  });
}
