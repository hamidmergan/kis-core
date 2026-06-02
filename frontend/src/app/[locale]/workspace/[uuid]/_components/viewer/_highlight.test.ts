import { describe, it, expect, vi } from "vitest";
import { drawCitationHighlight, type HighlightRefs } from "./_highlight";

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
