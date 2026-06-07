// Popup / action-bar exact-selection highlight for the PDF viewer.
//
// The ONLY remaining programmatic highlight: when the user selects text in the PDF
// and runs a popup action (translate / elaborate / …), the chat answer's chip can
// re-mark that exact selection on the page. Citation chips themselves NO LONGER draw
// any highlight — a chip click only scrolls to the page/timestamp.
//
// The marker is a passive YELLOW Highlight annotation, drawn as an ephemeral
// annotation (created but NEVER committed, so the PDF file is untouched). It is NOT a
// text selection, so it never triggers the selection action-popup. The user's own
// manual text selection still uses EmbedPDF's native blue selection + popup, and the
// native action-bar "highlight" command is left untouched.
//
// EmbedPDF-internal APIs in use (NOT in public docs — re-verify on @embedpdf bump):
//   annotation.createAnnotation / purgeAnnotation / deselectAnnotation,
//   engine.getPageGeometry, engine.getTextSlices, selection.getState (geometry cache).

export type HighlightRefs = {
  prevHighlightRef: { current: { pageIndex: number; ids: string[] } | null };
  // Tracks the current ephemeral highlight — a Highlight annotation that is NEVER
  // committed, so it never touches the PDF file — so it can be purged on the next
  // selection or when the user dismisses it. `scrollY` is the topmost region's
  // page-coordinate y, so the jump chip can re-center the exact spot instead of the
  // page top.
  citationHighlightRef: { current: { pageIndex: number; ids: string[]; scrollY?: number } | null };
  // Toggles the "dismiss highlight" control in the viewer.
  onHighlightActive?: (active: boolean) => void;
};

// Controls how drawCitationHighlight integrates with the current marker set:
//   scroll (default true): scroll the highlight into view after drawing.
type DrawOpts = { scroll?: boolean };

// Exact-selection highlight = passive yellow marker (NOT a text selection), so it
// never triggers the selection action-popup. Single colour constant — swap for a
// tenant brand colour here if desired.
const CITATION_HL_COLOR = "#FFE14D";   // highlighter yellow
const CITATION_HL_OPACITY = 0.4;
const HIGHLIGHT_SUBTYPE = 9;           // PdfAnnotationSubtype.HIGHLIGHT

// Page-frame marker for citation-chip jumps: a yellow border drawn around the whole
// target page (no fill) so the user sees which page the chip landed on. Persistent
// until the next jump or the "Markierung aufheben" button. SQUARE (subtype 5) renders
// for programmatically-created annotations in our EmbedPDF build (verified by the
// Docling layer-box overlay), unlike the HIGHLIGHT subtype which needs segmentRects.
const SQUARE_SUBTYPE = 5;              // PdfAnnotationSubtype.SQUARE
const BORDER_STYLE_SOLID = 1;         // PdfAnnotationBorderStyle.SOLID
const PAGE_BORDER_WIDTH = 3;          // px frame thickness
const PAGE_BORDER_OPACITY = 0.95;     // crisp frame

// Position-preserving diacritic fold + lowercase: every character maps to exactly
// ONE character (its NFKD base letter), so the result has the SAME length and the
// match index still aligns with cleanToRaw for the highlight geometry. Makes the
// search diacritic-insensitive, so a selection with umlauts ("Dezimalbrüche") still
// matches a PDF text layer whose font lost or mangled them ("Dezimalbruche…") —
// common in LaTeX/maths PDFs. Language-agnostic.
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
// to realign.
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


// Remove the current ephemeral highlight (purgeAnnotation does NOT modify the PDF —
// we never commit). Safe to call when none is active.
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


// Draw a yellow frame around the whole target page when a citation chip jumps here,
// so the user sees which page they landed on. Border only (no fill); persistent until
// the next jump or the "Markierung aufheben" button. Ephemeral SQUARE annotation —
// created but NEVER committed, so the PDF file is untouched — and readOnly+locked so
// it never intercepts selection/edits. Reuses citationHighlightRef so the existing
// dismiss button clears it and the next jump replaces it (one marker at a time).
export function flashPageBorder(refs: HighlightRefs, reg: unknown, page: number) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = reg as any;
  const anno = r.getPlugin?.("annotation")?.provides?.();
  const docMgr = r.getPlugin?.("document-manager")?.provides?.();
  const docId = docMgr?.getActiveDocumentId?.();
  const doc = docMgr?.getActiveDocument?.();
  if (!anno?.createAnnotation || !docId || !doc) return;

  const pageIndex = page - 1;
  const pageObj = doc.pages?.[pageIndex];
  const pageW = pageObj?.size?.width ?? pageObj?.width;
  const pageH = pageObj?.size?.height ?? pageObj?.height;
  if (!pageW || !pageH) return;

  clearCitationHighlight(refs, r);   // one marker at a time

  // Rect = the whole page (origin 0,0). The stroke is centred on the page edge so the
  // frame sits flush — no inset, because the rect is in page coordinates while the
  // stroke width is screen px, so any page-unit inset would open a zoom-dependent gap.
  const id = `kis-pageborder-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  try {
    anno.createAnnotation(pageIndex, {
      type: SQUARE_SUBTYPE,
      pageIndex,
      id,
      rect: { origin: { x: 0, y: 0 }, size: { width: pageW, height: pageH } },
      color: "transparent",
      strokeColor: CITATION_HL_COLOR,
      strokeWidth: PAGE_BORDER_WIDTH,
      strokeStyle: BORDER_STYLE_SOLID,
      opacity: PAGE_BORDER_OPACITY,
      flags: ["readOnly", "locked"],
      created: new Date(),
    });
    anno.deselectAnnotation?.();
    refs.citationHighlightRef.current = { pageIndex, ids: [id] };
    refs.onHighlightActive?.(true);
  } catch {
    /* frame is non-essential — ignore */
  }
}


// Smoothly scroll the active highlight back into view. Re-centres the exact
// highlight position (page + region y), not just the page top, mirroring the initial
// scroll. The annotation persists in EmbedPDF's model across page virtualization, so
// no re-draw is needed.
export function scrollToCitationPage(refs: HighlightRefs, reg: unknown) {
  const cur = refs.citationHighlightRef.current;
  if (!cur) return;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scroll = (reg as any)?.getPlugin?.("scroll")?.provides?.();
  scroll?.scrollToPage?.({
    pageNumber: cur.pageIndex + 1,
    ...(cur.scrollY != null
      ? { pageCoordinates: { x: 0, y: cur.scrollY }, alignY: 50 }
      : {}),
    behavior: "smooth",
  });
}


// Draw the highlight as a passive yellow Highlight annotation (ephemeral: created
// but never committed). No text selection is made, so the selection action-popup
// never appears. Purges any previous one first (one highlight at a time), deselects
// so no edit handles show, and scrolls the range into view.
// Exported for unit tests.
export function drawCitationHighlight(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, docMgr: any, scroll: any, targetPageIndex: number, geoStart: number, geoEnd: number, g: any,
  opts: DrawOpts = {},
): boolean {
  const doScroll = opts.scroll ?? true;
  const { segmentRects, bbox } = buildSegmentRects(g, geoStart, geoEnd);
  if (!segmentRects.length || !bbox) return false;
  const anno = r.getPlugin?.("annotation")?.provides?.();
  const docId = docMgr.getActiveDocumentId?.();
  if (!anno?.createAnnotation || !docId) return false;
  clearCitationHighlight(refs, r);   // one highlight at a time
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
    refs.citationHighlightRef.current = { pageIndex: targetPageIndex, ids: [id], scrollY: bbox.origin.y };
    refs.onHighlightActive?.(true);
  } catch {
    return false;
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


// Locate the verbatim selection on the page and draw it. The caller (a popup/action-
// bar exact selection) supplied a precise quote: highlight EXACTLY what the user
// marked, no sentence/paragraph expansion. If the quote doesn't match the page, DO
// NOT fall back to a fuzzy / single-keyword search — that would highlight something
// unrelated (e.g. a random date in a slide footer). Just scroll and bail out.
export function tryHighlightOnPage(
  refs: HighlightRefs,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  r: any, doc: any, engine: any, docMgr: any, scroll: any,
  targetPageIndex: number, searchText: string,
  opts: DrawOpts = {},
): Promise<boolean> {
  const doScroll = opts.scroll ?? true;
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
        scroll.scrollToPage({ pageNumber: targetPageIndex + 1, behavior: "instant" });
      }
      return true;
    }

    const sliceTask = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: totalChars }]);
    const slicePromise: Promise<unknown> = sliceTask?.toPromise?.() ?? Promise.resolve(null);

    return slicePromise.then((slices: unknown) => {
      const arr = slices as string[] | null;
      if (!arr?.[0]) return false;
      const rawPageText = arr[0];

      // Normalize whitespace for robust search, track mapping to raw indices.
      const cleanToRaw: number[] = [];
      let cleanText = "";
      let inSpace = false;
      for (let i = 0; i < rawPageText.length; i++) {
        const ch = rawPageText[i];
        if (ch === "\r" || ch === "\n" || ch === " " || ch === "\t") {
          if (!inSpace) { cleanText += " "; cleanToRaw.push(i); inSpace = true; }
        } else { cleanText += ch; cleanToRaw.push(i); inSpace = false; }
      }

      // Verbatim user selection: do NOT trim or alter — the user's chosen text IS
      // the intended highlight.
      const cleanInput = searchText.replace(/\s+/g, " ").trim()
        .replace(/^\d{1,3}\s+/, "").trim();
      // Diacritic-folded (still 1:1 length) so the search tolerates a PDF text layer
      // that lost/mangled umlauts; match indices stay aligned with cleanToRaw.
      const ptLower = _foldDiacritics(cleanText);
      const fullPhrase = _foldDiacritics(cleanInput);

      const fullIdx = ptLower.indexOf(fullPhrase);
      if (fullIdx < 0) {
        // Exact selection didn't match the page — scroll and bail, never fuzzy-match.
        if (scroll && doScroll) {
          scroll.scrollToPage({ pageNumber: targetPageIndex + 1, behavior: "instant" });
        }
        return true;
      }
      const matchStart = fullIdx;
      const matchEnd = fullIdx + fullPhrase.length - 1;

      // Highlight EXACTLY what the user marked — no expansion, regardless of length.
      const rawStart = cleanToRaw[matchStart];
      const rawEnd = cleanToRaw[matchEnd];

      const findGeo = makeFindGeo(engine, doc, targetPageIndex, totalChars, rawPageText.length);

      if (!docMgr.getActiveDocumentId?.()) return false;

      return Promise.all([findGeo(rawStart), findGeo(rawEnd)]).then(([geoStart, geoEnd]) => {
        // Constrain the range to runs on the same VISUAL line(s) as the match.
        // PPTX PDFs sometimes store chars in an order that doesn't match the visual
        // layout, so a char-range can span header+body+footer even if the match
        // itself is short. Trimming by run y-coordinate prevents that.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const runs = (g.runs || []) as any[];
        if (runs.length) {
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


// Orchestration for the popup / action-bar exact-selection highlight: scroll to the
// page, clear any previous marker + stray selection, then mark the verbatim text.
export function doHighlightSearch(
  refs: HighlightRefs, reg: unknown, page: number, text: string,
) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = reg as any;
  const opts: DrawOpts = {};
  const scroll = r.getPlugin?.("scroll")?.provides?.();
  scroll?.scrollToPage?.({ pageNumber: page, behavior: "instant" });

  const engine = r.getEngine?.();
  const docMgr = r.getPlugin?.("document-manager")?.provides?.();
  if (!engine || !docMgr) return;

  const doc = docMgr.getActiveDocument?.();
  if (!doc) return;

  // Clear the previous highlight (and any stray selection) before a new one.
  clearCitationHighlight(refs, r);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const selCap = r.getPlugin?.("selection")?.provides?.() as any;
  const activeDocId = docMgr.getActiveDocumentId?.();
  try { selCap?.clear?.(activeDocId); } catch { /* ignore */ }
  refs.prevHighlightRef.current = null;

  if (!text?.trim()) return;

  const pageIndex = page - 1;

  // Only try the exact target page. Falling back to nearby pages would mean the
  // highlight could land on the wrong page when the target is an OCR/image page
  // whose PDF text layer doesn't contain the selected text.
  tryHighlightOnPage(refs, r, doc, engine, docMgr, scroll, pageIndex, text, opts);
}
