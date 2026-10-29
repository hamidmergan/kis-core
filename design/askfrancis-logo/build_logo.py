# Builds the askFrancis logo as SVG with the name converted to outlines, so no font is needed to display it.
import re
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
import uharfbuzz as hb

OUT = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
BIRD = "/Users/hamidmergan/Projects/kis-thl/frontend/public/logos/kis-vogel.svg"
GREEN, BLACK, WHITE = "#7dc5ac", "#000000", "#ffffff"

# Geometry at header size: 18 px text, 24 px bird, 0.8 em overlap, plate padding 5/8/5/10, radius 8.
F, B, OVERLAP, LS = 18.0, 24.0, 0.8 * 18, -0.01 * 18
PAD_T, PAD_R, PAD_B, PAD_L, RADIUS = 5.0, 8.0, 5.0, 10.0, 8.0
VB_X, VB_Y, VB_W, VB_H = 83.0, 8.0, 154.0, 78.0
bird_scale = B / VB_H
bird_w = VB_W * bird_scale

vf = TTFont("/Users/hamidmergan/Projects/kis-thl/frontend/node_modules/next/dist/next-devtools/server/font/geist-latin.woff2")
font600 = instancer.instantiateVariableFont(vf, {"wght": 600})
font600.flavor = None
font600.save("/tmp/geist-600.ttf")
upem = font600["head"].unitsPerEm
asc, desc = font600["OS/2"].sTypoAscender, font600["OS/2"].sTypoDescender
glyph_order = font600.getGlyphOrder()
glyph_set = font600.getGlyphSet()

face = hb.Face(hb.Blob.from_file_path("/tmp/geist-600.ttf"))
hbfont = hb.Font(face)
buf = hb.Buffer()
buf.add_str("askFrancis")
buf.guess_segment_properties()
hb.shape(hbfont, buf, {"kern": True, "liga": True})
infos, positions = buf.glyph_infos, buf.glyph_positions

# Baseline as the browser places it: line box of 1 em centred in the bird height, glyphs centred by typo metrics.
line_top = (B - F) / 2
baseline = line_top + (F - (asc - desc) * F / upem) / 2 + asc * F / upem
s = F / upem

glyphs = []
x = 0.0
for i, (info, pos) in enumerate(zip(infos, positions)):
    name = glyph_order[info.codepoint]
    pen = SVGPathPen(glyph_set, ntos=lambda v: f"{v:.1f}")
    glyph_set[name].draw(pen)
    gx = x + pos.x_offset * s
    gy = baseline - pos.y_offset * s
    glyphs.append((info.cluster < 3, gx, gy, pen.getCommands()))
    x += pos.x_advance * s + (LS if i < len(infos) - 1 else 0)
text_w = x

bird_x = text_w - OVERLAP
content_w = bird_x + bird_w
bird_paths = re.findall(r"<path[^>]*/>", open(BIRD).read())

def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")

def svg(plate, francis_color):
    ox, oy = (PAD_L, PAD_T) if plate else (0.0, 0.0)
    w = content_w + (PAD_L + PAD_R if plate else 0)
    h = B + (PAD_T + PAD_B if plate else 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" width="{fmt(w)}" height="{fmt(h)}">']
    if plate:
        parts.append(f'<rect width="{fmt(w)}" height="{fmt(h)}" rx="{fmt(RADIUS)}" fill="{WHITE}"/>')
    for color, keep in ((GREEN, True), (francis_color, False)):
        parts.append(f'<g fill="{color}">')
        for is_ask, gx, gy, d in glyphs:
            if is_ask == keep and d:
                parts.append(f'<path transform="translate({fmt(ox + gx)} {fmt(oy + gy)}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
        parts.append("</g>")
    tx, ty = ox + bird_x - VB_X * bird_scale, oy - VB_Y * bird_scale
    parts.append(f'<g transform="translate({fmt(tx)} {fmt(ty)}) scale({bird_scale:.5f})">' + "".join(bird_paths) + "</g>")
    parts.append("</svg>")
    return "\n".join(parts)

for fname, plate, fc in (("askfrancis-logo-white-plate.svg", True, BLACK), ("askfrancis-logo-transparent-black.svg", False, BLACK), ("askfrancis-logo-transparent-white.svg", False, WHITE)):
    open(f"{OUT}/{fname}", "w").write(svg(plate, fc))
    print(fname, "ok")
print("text width %.2f, plate %.2f x %.2f, baseline %.2f" % (text_w, content_w + PAD_L + PAD_R, B + PAD_T + PAD_B, baseline))
