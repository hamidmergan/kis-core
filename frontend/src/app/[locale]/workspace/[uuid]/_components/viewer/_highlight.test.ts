import { describe, it, expect, vi } from "vitest";
import { drawCitationHighlight, doHighlightSearch, type HighlightRefs } from "./_highlight";

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
