// Text search + highlight orchestration for the PDF viewer.
// Extracted from PdfViewer.tsx. Uses the EmbedPDF registry/engine/selection
// plugins plus heuristics (bullet detection, sentence/paragraph expansion)
// to turn a raw search string + page number into an EmbedPDF instant selection.
//
// EmbedPDF-internal APIs in use (NOT in public docs — re-verify on @embedpdf bump):
//   selection.applyInstantSelection, selection.enableForMode, selCap.getState,
//   engine.getPageGeometry, engine.getTextSlices.
// Public Search plugin can't replace this: it only highlights exact matches,
// not the surrounding sentence/paragraph that _findParaBounds expands to.

export type HighlightRefs = {
  prevHighlightRef: { current: { pageIndex: number; ids: string[] } | null };
};

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


// Apply an instant selection over a geometry char-range, handling the two
// Selection-plugin pitfalls (panMode rects + virtualized-page geometry not yet
// mounted), then scroll the range into view. Shared by both highlight paths.
function applyRangeSelection(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, docId2: string, scroll: any, g: any, refs: HighlightRefs,
  targetPageIndex: number, geoStart: number, geoEnd: number,
): Promise<boolean> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const selInstance = r.getPlugin?.("selection") as any;
  const selCapability = selInstance?.provides?.();
  if (!selInstance?.applyInstantSelection || docId2 == null) return Promise.resolve(false);
  // 1. Pan plugin defaults to "panMode" on touch; the Selection plugin only ships
  //    rect config for "pointerMode", so without this rects never render.
  //    Idempotent per doc; enabling panMode rects does NOT enable drag-to-select.
  try {
    selCapability?.enableForMode?.("panMode", { enableSelection: false, showSelectionRects: true }, docId2);
    selCapability?.enableForMode?.("pointerMode", { enableSelection: true, showSelectionRects: true }, docId2);
  } catch { /* ignore */ }
  // 2. On virtualized layouts the page's SelectionLayer may not be mounted yet
  //    (state.geometry[p] empty → zero rects). Poll getState() until geometry lands.
  const applyWhenReady = (attempt = 0): Promise<boolean> => {
    const selGeo = selCapability?.getState?.(docId2)?.geometry?.[targetPageIndex];
    if (selGeo || attempt >= 40) {
      selInstance.applyInstantSelection(docId2, targetPageIndex, geoStart, geoEnd, "default");
      refs.prevHighlightRef.current = { pageIndex: targetPageIndex, ids: [] };
      return Promise.resolve(true);
    }
    return new Promise((res) => setTimeout(res, 25)).then(() => applyWhenReady(attempt + 1));
  };
  return applyWhenReady().then(() => {
    let targetRun = g.runs[0];
    for (const run of g.runs) {
      if (run.charStart > geoStart) break;
      targetRun = run;
    }
    if (targetRun?.rect && scroll) {
      scroll.scrollToPage({
        pageNumber: targetPageIndex + 1,
        pageCoordinates: { x: 0, y: targetRun.rect.y },
        behavior: "instant",
        alignY: 50,
      });
    }
    return true;
  });
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

      const docId2 = docMgr.getActiveDocumentId?.();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const selInstance = r.getPlugin?.("selection") as any;
      if (!selInstance?.applyInstantSelection || !docId2) return false;

      const findGeo = makeFindGeo(engine, doc, targetPageIndex, totalChars, R.length);
      return Promise.all([findGeo(rawStart), findGeo(rawEnd)]).then(([geoStart, geoEnd]) =>
        applyRangeSelection(r, docId2, scroll, g, refs, targetPageIndex, geoStart, geoEnd),
      );
    });
  }).catch(() => false);
}


export function tryHighlightOnPage(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, doc: any, engine: any, docMgr: any, scroll: any,
  targetPageIndex: number, searchText: string, exactSelection: boolean = false,
): Promise<boolean> {
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
      if (scroll) {
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
        if (/^(?:[•·▪◦‣⁃●○…*]|\.{2,}|[-–—]\s|\(?\d{1,3}[.)]\s)/.test(afterSlice)) return true;
        if (/^\d{1,4}[.\-/]\d{1,2}(?:[.\-/]\d{1,4})?\b/.test(afterSlice)) return true;
        if (/[.!?]$/.test(beforeSlice)) return true;  // previous sentence ended
        if (/^\p{Ll}/u.test(afterSlice)) return false; // lowercase start → wrap
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
        if (scroll) {
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

      // Expand to sentence boundaries (period, newline, or start/end of text)
      // Skip abbreviation dots: bzw. z.B. u.a. etc. ca. vs. Dr. Nr. Prof. d.h. o.ä. ggf. S. Abs.
      const _abbrPattern = /(?:bzw|z\.B|u\.a|etc|ca|vs|Dr|Nr|Prof|d\.h|o\.ä|ggf|Abs|Abb|vgl|inkl|sog|evtl|S)\s*$/i;
      const _isAbbrevDot = (text: string, dotIdx: number) => {
        if (dotIdx < 1) return false;
        // Dot directly followed by a letter (no space) is inside an abbreviation
        // (e.g. "z.B.", "d.h.", "U.S.A."). Digits after a dot are NOT treated as
        // abbreviation to keep footnote markers ("erprobt.11") as real sentence ends —
        // decimal numbers like "3.14" are covered by the digit-before-dot rule below.
        const next = text[dotIdx + 1];
        if (next && /\p{L}/u.test(next)) return true;
        const before = text.slice(Math.max(0, dotIdx - 6), dotIdx);
        if (_abbrPattern.test(before)) return true;
        // Single uppercase letter + dot (e.g. "S." "A.")
        if (dotIdx >= 1 && /^\p{Lu}$/u.test(text[dotIdx - 1]) && (dotIdx < 2 || text[dotIdx - 2] === " ")) return true;
        // Number + dot (e.g. "3." "49%.")
        if (/\d$/.test(text.slice(Math.max(0, dotIdx - 1), dotIdx))) return true;
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

      // Paragraph-break detection: double newline in raw text, or a heading pattern
      // ("Kapitel:", "1.2 Titel") at the start of the next line.
      const _isHeading = (text: string): boolean => {
        const t = text.replace(/^\s+/, "");
        // Colon-terminated heading: "International Coach:", "Fachlandkarte:"
        if (/^\p{Lu}[\p{L}\p{N}_-]+(?:\s+\p{Lu}?[\p{L}\p{N}_-]+){0,3}\s*:/u.test(t)) return true;
        // Numbered section heading: "1. Management Summary", "4.4 Transferpotential",
        // "2.1.3 Skizze der Ausgangslage"
        if (/^\d+(?:\.\d+)*\.?\s+\p{Lu}[\p{L}\p{N}_-]+/u.test(t)) return true;
        return false;
      };
      const _isParagraphBreakBefore = (startInClean: number): boolean => {
        if (startInClean <= 0) return false;
        // cleanToRaw points at the FIRST whitespace char of the run — scan forward
        // through raw to count newlines until a non-whitespace char appears.
        const rawPos = cleanToRaw[startInClean - 1];
        if (rawPos == null) return false;
        let nlCount = 0;
        for (let i = rawPos; i < rawPageText.length; i++) {
          const ch = rawPageText[i];
          if (ch === "\n") nlCount++;
          else if (ch !== " " && ch !== "\r" && ch !== "\t") break;
        }
        // PPTX bullet page: single newline is a paragraph break ONLY if the
        // next line starts like a new bullet — otherwise it's a wrap.
        if (_isBulletPage && nlCount >= 1 && _looksLikeNewBullet(startInClean)) return true;
        if (nlCount >= 2) return true;
        const preview = cleanText.slice(startInClean, Math.min(cleanText.length, startInClean + 80));
        if (_isHeading(preview)) return true;
        // Skip a leading footnote-digit marker ("11 International Coach:") and re-test
        const skipped = preview.replace(/^\s*\d{1,3}\s+/, "");
        return skipped !== preview && _isHeading(skipped);
      };
      // True only if the WHOLE text is a heading (with optional leading page-num /
      // footnote digit), not just its prefix — otherwise "4.4. Title Actual paragraph
      // content..." would falsely match and cause the first paragraph sentence to be
      // dropped from the highlight.
      const _isFullHeading = (text: string): boolean => {
        const t = text.replace(/^\s+|\s+$/g, "");
        if (/^\p{Lu}[\p{L}\p{N}_-]+(?:\s+\p{Lu}?[\p{L}\p{N}_-]+){0,4}\s*:$/u.test(t)) return true;
        if (/^\d+(?:\.\d+)*\.?\s+\p{Lu}[\p{L}\p{N}_-]+(?:\s+\p{Lu}?[\p{L}\p{N}_-]+){0,5}$/u.test(t)) return true;
        return false;
      };
      const _isHeadingLike = (text: string): boolean => {
        if (_isFullHeading(text)) return true;
        const skipped = text.replace(/^\s*\d{1,3}\s+/, "");
        return skipped !== text && _isFullHeading(skipped);
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
      // Expand to paragraph bounds: walk sentence-by-sentence backwards/forwards,
      // stopping at a paragraph break or heading.
      const _findParaBounds = (startPos: number, endPos: number): [number, number] => {
        const [sStart0, sEnd0] = _findSentBounds(startPos, endPos);
        let pStart = _stripLeadingHeading(sStart0);
        if (pStart >= endPos) pStart = sStart0; // safety: don't strip past the match
        for (let attempts = 0; attempts < 40 && pStart > 0; attempts++) {
          if (_isParagraphBreakBefore(pStart)) break;
          let prevEnd = pStart - 1;
          while (prevEnd > 0 && cleanText[prevEnd] === " ") prevEnd--;
          if (prevEnd <= 0) { pStart = 0; break; }
          const [rawPrevStart] = _findSentBounds(prevEnd, prevEnd);
          // Skip any leading page-num lines so prevStart lands at real content.
          const prevStart = _stripLeadingHeading(rawPrevStart);
          if (prevStart >= pStart) break;
          const prevText = cleanText.slice(prevStart, prevEnd + 1);
          if (_isHeadingLike(prevText)) break;
          pStart = prevStart;
        }
        let pEnd = sEnd0;
        for (let attempts = 0; attempts < 40 && pEnd < cleanText.length - 1; attempts++) {
          let nextStart = pEnd + 1;
          while (nextStart < cleanText.length && cleanText[nextStart] === " ") nextStart++;
          if (nextStart >= cleanText.length) break;
          if (_isParagraphBreakBefore(nextStart)) break;
          const [, nextEnd] = _findSentBounds(nextStart, nextStart);
          if (nextEnd <= pEnd) break;
          const nextText = cleanText.slice(nextStart, nextEnd + 1);
          if (_isHeadingLike(nextText)) break;
          pEnd = nextEnd;
        }
        return [pStart, pEnd];
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
        [sentStart, sentEnd] = _findParaBounds(matchStart, matchEnd);
        if (sentEnd - sentStart > 2500) {
          [sentStart, sentEnd] = _findSentBounds(matchStart, matchEnd);
        }
        // PPTX-converted PDFs: all bullets live in one text box, so the whole
        // slide is one paragraph. Back off to the current bullet/line via the
        // original newline positions in rawPageText.
        if ((sentEnd - sentStart + 1) > cleanText.length * 0.6) {
          [sentStart, sentEnd] = _findLineBounds(matchStart, matchEnd);
        }
      }

      const rawStart = cleanToRaw[sentStart];
      const rawEnd = cleanToRaw[sentEnd];

      const findGeo = makeFindGeo(engine, doc, targetPageIndex, totalChars, rawPageText.length);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const selInstance = (r.getPlugin?.("selection") as any);
      const docId2 = docMgr.getActiveDocumentId?.();
      if (!selInstance?.applyInstantSelection || !docId2) return false;

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
        return applyRangeSelection(r, docId2, scroll, g, refs, targetPageIndex, geoStart, geoEnd);
      });
    });
  }).catch(() => false);
}

export function doHighlightSearch(
  refs: HighlightRefs, reg: unknown, page: number, text: string,
  exactSelection: boolean = false, offsets?: [number, number],
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

  // Clear previous highlight (selection) before applying a new one — otherwise
  // successive chip clicks accumulate marks across pages.
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
  // Architecture B: when the chip carries an exact span offset, draw it directly
  // (no re-finding / no expansion). On any failure (span not on the page, geometry
  // unavailable, pdfium drift) fall back to the legacy keyword search so a chip is
  // never worse than before.
  if (offsets && !exactSelection) {
    tryHighlightByOffsets(refs, r, doc, engine, docMgr, scroll, pageIndex, offsets, text)
      .then((ok) => {
        if (!ok) tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection);
      })
      .catch(() => {
        tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection);
      });
    return;
  }

  tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, exactSelection);
}
