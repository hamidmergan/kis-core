import { describe, it, expect, vi } from "vitest";
import { drawCitationHighlight, doHighlightSearch, doPageEdgeBar, _collapseFold, type HighlightRefs } from "./_highlight";

describe("_collapseFold drops OCR join artifacts (mirrors backend _collapse_fold)", () => {
  it("strips a U+FFFE join artifact so a hyphen-broken word matches", () => {
    const { clean, map } = _collapseFold("Bachelor￾Studiengangs");
    expect(clean).toBe("bachelorstudiengangs");
    expect(map.length).toBe(clean.length);
    expect(map[0]).toBe(0);
    expect(map[8]).toBe(9); // 'S' of Studiengangs keeps raw index 9, past the skipped artifact
  });

  it("strips a soft hyphen", () => {
    expect(_collapseFold("Kla­ren").clean).toBe("klaren");
  });

  it("strips zero-width chars and BOM", () => {
    expect(_collapseFold("a​﻿‍b").clean).toBe("ab");
  });

  it("leaves clean text unchanged", () => {
    expect(_collapseFold("Hallo Welt").clean).toBe("hallo welt");
  });
});

// Minimal page geometry: one run with two visible glyphs, so buildSegmentRects
// yields a non-empty bbox for the [0,1] glyph range.
function fakeGeometry() {
  return {
    runs: [
      {
        charStart: 0,
        glyphs: [
          { x: 10, y: 20, width: 5, height: 8, flags: 0 },
          { x: 15, y: 20, width: 5, height: 8, flags: 0 },
        ],
      },
    ],
  };
}

function fakeRegistry() {
  const createAnnotation = vi.fn();
  const anno = {
    createAnnotation,
    deselectAnnotation: vi.fn(),
    purgeAnnotation: vi.fn(),
  };
  const r = {
    getPlugin: (name: string) => (name === "annotation" ? { provides: () => anno } : undefined),
  };
  return { r, createAnnotation };
}

function fakeRefs(): HighlightRefs & { onHighlightActive: ReturnType<typeof vi.fn> } {
  return {
    prevHighlightRef: { current: null },
    citationHighlightRef: { current: null },
    onHighlightActive: vi.fn(),
  };
}

const docMgr = { getActiveDocumentId: () => "doc-1" };

// Full registry mock that lets the keyword search path reach (or skip) the draw.
// One run whose glyph count equals the raw text length (phantoms = 0), so the
// offset→geometry mapping is identity and a matched range yields a real bbox.
function fakeSearchRegistry(rawPageText: string) {
  const createAnnotation = vi.fn();
  const scrollToPage = vi.fn();
  const glyphs = Array.from(rawPageText, (_c, i) => ({
    x: i * 6, y: 20, width: 5, height: 8, flags: 0,
  }));
  const geo = { runs: [{ charStart: 0, rect: { origin: { x: 0, y: 20 }, size: { width: 1, height: 8 } }, glyphs }] };
  const anno = { createAnnotation, deselectAnnotation: vi.fn(), purgeAnnotation: vi.fn() };
  const engine = {
    getPageGeometry: () => ({ toPromise: () => Promise.resolve(geo) }),
    getTextSlices: () => ({ toPromise: () => Promise.resolve([rawPageText]) }),
  };
  const dm = {
    getActiveDocumentId: () => "doc-1",
    getActiveDocument: () => ({ pages: [{ size: { width: 600, height: 800 } }] }),
  };
  const r = {
    getEngine: () => engine,
    getPlugin: (name: string) => {
      if (name === "annotation") return { provides: () => anno };
      if (name === "scroll") return { provides: () => ({ scrollToPage }) };
      if (name === "document-manager") return { provides: () => dm };
      if (name === "selection") return { provides: () => ({ getState: () => ({ geometry: {} }), clear: vi.fn() }) };
      return undefined;
    },
  };
  return { r, createAnnotation, scrollToPage };
}

const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };

describe("citation keyword highlights are sentence-tight (C2: no paragraph expansion)", () => {
  // Three sentences; the keyword lives only in the MIDDLE one. The old paragraph
  // expansion would paint all three; C2 must paint only the middle sentence.
  const RAW = "Erster Satz voellig ohne Bezug zum Thema. Das Modul behandelt Audio Grafik und Video. Dritter Satz ebenfalls ohne jeden Bezug.";

  it("highlights only the matched SENTENCE, not the whole paragraph", async () => {
    const { r, createAnnotation } = fakeSearchRegistry(RAW);
    const refs = fakeRefs();

    doHighlightSearch(refs, r, 1, "Audio Grafik und Video", false, undefined);
    await flush();

    expect(createAnnotation).toHaveBeenCalledTimes(1);
    const rect = createAnnotation.mock.calls[0][1].rect;
    // Glyph x = index*6. The middle sentence starts well to the right of x=0, so a
    // highlight that began at sentence 1 (paragraph expansion) would have origin.x ~ 0.
    expect(rect.origin.x).toBeGreaterThan(100);
    // ...and it must not stretch into sentence 3 (whole paragraph ≈ RAW.length*6 wide).
    expect(rect.origin.x + rect.size.width).toBeLessThan(RAW.length * 6 - 100);
  });

  it("still highlights the user's OWN text selection (exactSelection=true)", async () => {
    const { r, createAnnotation } = fakeSearchRegistry(RAW);
    const refs = fakeRefs();

    doHighlightSearch(refs, r, 1, "Audio Grafik und Video", true, undefined);
    await flush();

    expect(createAnnotation).toHaveBeenCalled();
  });
});

describe("drawCitationHighlight highlightEnabled gating", () => {
  it("draws the annotation and scrolls when highlighting is enabled (default)", () => {
    const { r, createAnnotation } = fakeRegistry();
    const refs = fakeRefs();
    const scroll = { scrollToPage: vi.fn() };

    const ok = drawCitationHighlight(refs, r, docMgr, scroll, 0, 0, 1, fakeGeometry());

    expect(ok).toBe(true);
    expect(createAnnotation).toHaveBeenCalledTimes(1);
    expect(scroll.scrollToPage).toHaveBeenCalledTimes(1);
    expect(refs.onHighlightActive).toHaveBeenCalledWith(true);
  });

  it("scrolls to the exact spot but draws NO annotation when highlighting is disabled", () => {
    const { r, createAnnotation } = fakeRegistry();
    const refs = fakeRefs();
    const scroll = { scrollToPage: vi.fn() };

    const ok = drawCitationHighlight(refs, r, docMgr, scroll, 0, 0, 1, fakeGeometry(), {
      highlightEnabled: false,
    });

    expect(ok).toBe(true);
    expect(createAnnotation).not.toHaveBeenCalled();
    expect(refs.onHighlightActive).not.toHaveBeenCalledWith(true);
    // Still jumps to the exact text location — that is the whole point of the setting.
    expect(scroll.scrollToPage).toHaveBeenCalledTimes(1);
    const arg = scroll.scrollToPage.mock.calls[0][0];
    expect(arg.pageCoordinates.y).toBe(20);
  });
});

describe("doPageEdgeBar draws the nav-only left-margin cue", () => {
  it("draws a full-height left-edge bar on the cited page and scrolls to it", () => {
    const { r, createAnnotation, scrollToPage } = fakeSearchRegistry("irrelevant page text");
    const refs = fakeRefs();

    doPageEdgeBar(refs, r, 1); // page 1 → pageIndex 0 (the mock's only page, height 800)

    expect(createAnnotation).toHaveBeenCalledTimes(1);
    const [pageIndex, anno] = createAnnotation.mock.calls[0];
    expect(pageIndex).toBe(0);
    // Left margin: starts at x=0, narrow, spans the WHOLE page height (800 in the mock).
    expect(anno.rect.origin.x).toBe(0);
    expect(anno.rect.origin.y).toBe(0);
    expect(anno.rect.size.width).toBeLessThan(12);
    expect(anno.rect.size.height).toBe(800);
    // Nav-only: page-level scroll (alignY 50), no span pageCoordinates.
    const arg = scrollToPage.mock.calls.at(-1)?.[0];
    expect(arg.pageNumber).toBe(1);
    expect(arg.alignY).toBe(50);
    // Reuses the citation ref so the dismiss button + clear-on-next-chip work.
    expect(refs.citationHighlightRef.current?.pageIndex).toBe(0);
    expect(refs.onHighlightActive).toHaveBeenCalledWith(true);
  });

  it("falls back to a plain page scroll when the document manager is missing", () => {
    const scrollToPage = vi.fn();
    const r = {
      getPlugin: (name: string) =>
        name === "scroll" ? { provides: () => ({ scrollToPage }) } : undefined,
    };
    const refs = fakeRefs();

    doPageEdgeBar(refs, r, 5);

    expect(scrollToPage).toHaveBeenCalledTimes(1);
    expect(scrollToPage.mock.calls[0][0].pageNumber).toBe(5);
    expect(refs.citationHighlightRef.current).toBeNull();
  });
});
