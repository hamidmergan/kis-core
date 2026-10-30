# Builds the ASK Francis logo as SVG with the name converted to outlines, so no font is needed to display it.
import os
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

OUT = os.path.dirname(os.path.abspath(__file__))
FONT = "/Users/hamidmergan/Projects/kis-thl/frontend/node_modules/next/dist/next-devtools/server/font/geist-latin.woff2"
BLUE, BLACK, WHITE = "#004261", "#000000", "#ffffff"

# Geometry at header size: 18 px text, letter spacing -0.02 em, plate padding 5/10/5/10, radius 8.
# Display scale of the standalone files, so a viewer opens them at about 1000 px wide; the viewBox stays at header size.
VIEW = 10.0
F, LS = 18.0, -0.02 * 18
PAD_T, PAD_R, PAD_B, PAD_L, RADIUS = 5.0, 10.0, 5.0, 10.0, 8.0
# ASK carries the weight, Francis stays lighter, the space between takes the regular width.
PARTS = (("ASK", 800, True), (" ", 600, None), ("Francis", 500, False))


def instance(weight):
    """A static TTF of Geist at the given weight, plus its shaper font."""
    font = instancer.instantiateVariableFont(TTFont(FONT), {"wght": weight})
    font.flavor = None
    path = f"/tmp/geist-{weight}.ttf"
    font.save(path)
    return font, hb.Font(hb.Face(hb.Blob.from_file_path(path)))


glyphs, x = [], 0.0
for text, weight, is_ask in PARTS:
    font, hbfont = instance(weight)
    s = F / font["head"].unitsPerEm
    order, gset = font.getGlyphOrder(), font.getGlyphSet()
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        pen, bounds = SVGPathPen(gset, ntos=lambda v: f"{v:.1f}"), BoundsPen(gset)
        gset[name].draw(pen)
        gset[name].draw(bounds)
        if is_ask is not None and bounds.bounds:
            glyphs.append((is_ask, x + pos.x_offset * s, s, pen.getCommands(), bounds.bounds))
        x += pos.x_advance * s + LS

# The box hugs the ink: left edge of A, right edge of s, cap top, baseline.
x0 = min(gx + b[0] * s for _, gx, s, _, b in glyphs)
x1 = max(gx + b[2] * s for _, gx, s, _, b in glyphs)
top = max(b[3] * s for _, _, s, _, b in glyphs)
bottom = min(b[1] * s for _, _, s, _, b in glyphs)
ink_w, ink_h = x1 - x0, top - bottom


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def svg(plate, ask_color, francis_color):
    ox, oy = (PAD_L, PAD_T) if plate else (0.0, 0.0)
    w = ink_w + (PAD_L + PAD_R if plate else 0)
    h = ink_h + (PAD_T + PAD_B if plate else 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" width="{fmt(w * VIEW)}" height="{fmt(h * VIEW)}">']
    if plate:
        parts.append(f'<rect width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(RADIUS)}" fill="{WHITE}"/>')
    for color, keep in ((ask_color, True), (francis_color, False)):
        parts.append(f'<g fill="{color}">')
        for is_ask, gx, s, d, _ in glyphs:
            if is_ask == keep and d:
                parts.append(f'<path transform="translate({fmt(ox + gx - x0)} {fmt(oy + top)}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


# On dark grounds the blue ASK would vanish, there both words are white and only the weight sets them apart.
for fname, plate, ac, fc in (("ask-francis-logo-white-plate.svg", True, BLUE, BLACK),
                             ("ask-francis-logo-transparent-black.svg", False, BLUE, BLACK),
                             ("ask-francis-logo-transparent-white.svg", False, WHITE, WHITE)):
    open(f"{OUT}/{fname}", "w").write(svg(plate, ac, fc))
    print(fname, "ok")
print("ink %.2f x %.2f, plate %.2f x %.2f" % (ink_w, ink_h, ink_w + PAD_L + PAD_R, ink_h + PAD_T + PAD_B))
