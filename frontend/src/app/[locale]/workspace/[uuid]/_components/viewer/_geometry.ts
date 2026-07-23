// Wrap engine.getPageGeometry to clamp inflated glyph heights on PDFs with
// oversized FontBBox. PDFium's FPDFText_GetLooseCharBox derives char heights
// from the font's bbox; some PDFs (e.g. LibreOffice-embedded Cambria with
// FontBBox height ~5580 FUnits) inflate this to 2-5x the real line-height,
// which makes text-selection highlights visually span multiple lines.
//
// Self-correcting: only clamps when `loose_height > 2.0 * tight_height`
// (clear FontBBox bug). Normal PDFs have loose/tight ratio ~1.2-1.4, so the
// guard is a no-op on correctly-behaving fonts.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function wrapEngineGeometry(engine: any) {
  if (!engine || engine.__kisGeometryWrapped) return;
  const original = engine.getPageGeometry?.bind(engine);
  if (typeof original !== "function") return;
  engine.__kisGeometryWrapped = true;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  engine.getPageGeometry = (doc: any, page: any) => {
    const task = original(doc, page);
    // Task may be sync-resolved (direct engine) or async (worker). In both
    // cases wait() fires our callback before any other consumer's (ordered).
    // clampGeometry mutates in place → downstream consumers see clamped data.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (task as any)?.wait?.((geo: any) => { clampGeometry(geo); }, () => {});
    return task;
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function clampGeometry(geo: any) {
  if (!geo || !Array.isArray(geo.runs)) return geo;
  const INFLATION_THRESHOLD = 2.0;  // loose > 2x tight → treat as FontBBox bug
  const CLAMP_PADDING = 0.15;       // 15% padding above/below ink for visual breathing room

  for (const run of geo.runs) {
    if (!run || !Array.isArray(run.glyphs) || run.glyphs.length === 0) continue;

    let minTightY = Infinity;
    let maxTightBottom = -Infinity;
    let maxLooseHeight = 0;
    for (const g of run.glyphs) {
      if (g.flags === 2) continue; // isEmpty
      if (typeof g.tightY === "number" && typeof g.tightHeight === "number") {
        if (g.tightY < minTightY) minTightY = g.tightY;
        const bottom = g.tightY + g.tightHeight;
        if (bottom > maxTightBottom) maxTightBottom = bottom;
      }
      if (g.height > maxLooseHeight) maxLooseHeight = g.height;
    }
    if (minTightY === Infinity || maxTightBottom === -Infinity) continue;

    const tightHeight = maxTightBottom - minTightY;
    if (tightHeight <= 0) continue;
    if (maxLooseHeight <= tightHeight * INFLATION_THRESHOLD) continue; // normal PDF → skip

    const pad = tightHeight * CLAMP_PADDING;
    const clampedY = minTightY - pad;
    const clampedHeight = tightHeight + 2 * pad;

    let minX = Infinity;
    let maxX = -Infinity;
    for (const g of run.glyphs) {
      if (g.flags === 2) continue;
      g.y = clampedY;
      g.height = clampedHeight;
      if (g.x < minX) minX = g.x;
      if (g.x + g.width > maxX) maxX = g.x + g.width;
    }
    if (minX !== Infinity && run.rect) {
      run.rect.x = minX;
      run.rect.y = clampedY;
      run.rect.width = maxX - minX;
      run.rect.height = clampedHeight;
    }
  }
  return geo;
}
