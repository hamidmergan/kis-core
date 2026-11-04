# Builds AskFrancis logo drafts (one word, Ask in CD dark blue) with and without bird, as outlined SVG.
import os, re
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(f"{OUT}/../..")
FONT = f"{ROOT}/frontend/node_modules/next/dist/next-devtools/server/font/geist-latin.woff2"
BIRD = f"{ROOT}/frontend/public/logos/kis-vogel.svg"
BLUE, BLACK, WHITE = "#004261", "#000000", "#ffffff"
F, LS = 18.0, -0.02 * 18
VIEW = 10.0
B, OVERLAP = 21.0, -4.0  # bird height and overlap with the last letter
VB_X, VB_Y, VB_W, VB_H = 19.0, 16.0, 82.0, 102.5
PAD = 6.0

def instance(w):
    f = instancer.instantiateVariableFont(TTFont(FONT), {"wght": w}); f.flavor = None
    p = f"/tmp/geist-{w}.ttf"; f.save(p)
    return f, hb.Font(hb.Face(hb.Blob.from_file_path(p)))

def build(parts):
    glyphs, x = [], 0.0
    for text, weight, tag in parts:
        font, hbf = instance(weight); s = F / font["head"].unitsPerEm
        order, gs = font.getGlyphOrder(), font.getGlyphSet()
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
        hb.shape(hbf, buf, {"kern": True, "liga": True})
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            n = order[i.codepoint]; pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}"); bp = BoundsPen(gs)
            gs[n].draw(pen); gs[n].draw(bp)
            if bp.bounds: glyphs.append((tag, x + p.x_offset * s, s, pen.getCommands(), bp.bounds))
            x += p.x_advance * s + LS
    return glyphs, x

fmt = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
def gull(outline, body, wing, beak="#F5A623"):
    shapes = '<polygon points="20,56 1,48 8,70"/><ellipse cx="48" cy="60" rx="32" ry="24"/><circle cx="68" cy="34" r="18"/>'
    o = f'<g fill="{outline}" stroke="{outline}" stroke-width="7" stroke-linejoin="round">{shapes}</g>' if outline else ""
    return (o + f'<g stroke="{beak}" stroke-width="4" stroke-linecap="round"><line x1="42" y1="82" x2="40" y2="93"/><line x1="56" y1="82" x2="58" y2="93"/></g>'
      + f'<g fill="{body}">{shapes}</g>'
      + f'<path d="M30 56 Q46 44 66 58 Q56 76 34 72 Q26 66 30 56Z" fill="{wing}"/>'
      + f'<path d="M84 31 L99 37 L84 42 Z" fill="{beak}"/><circle cx="73" cy="31" r="3.4" fill="#0D1F2D"/><circle cx="74.2" cy="29.8" r="1.2" fill="#fff"/>'
      + '<circle cx="71" cy="40" r="3.2" fill="#ff9aa8" opacity=".7"/>')
_f = open(f"{OUT}/francis-idle.svg").read()
_f = re.sub(r"<ellipse[^>]*francis-shadow[^>]*></ellipse>", "", _f)
bird_paths = re.sub(r"^<svg[^>]*>|</svg>$", "", _f)


def svg(parts, colors, bird, plate, ring='none', circle=True):
    bs = B / VB_H
    CD = globals()['CD'] if circle else B * VB_W / VB_H
    bp_ = bird_paths if bird else ''
    g, adv = build(parts)
    x0 = min(a + b[0] * s for _, a, s, _, b in g); x1 = max(a + b[2] * s for _, a, s, _, b in g)
    top = max(t[4][3] * t[2] for t in g); bot = min(t[4][1] * t[2] for t in g)
    inkw, inkh = x1 - x0, top - bot
    off = (CD - OVERLAP) if (bird and LEFT) else 0.0
    cw = inkw + (CD - OVERLAP if bird else 0)
    ch = max(inkh, CD if circle else B) if bird else inkh
    ox = oy = PAD if plate else 0.0
    w, h = cw + 2 * ox, ch + 2 * oy
    # Vertical placement: text baseline so the bird (if any) is centred on the text's cap height.
    base_y = oy + (ch - inkh) / 2 + top
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" width="{fmt(w*VIEW)}" height="{fmt(h*VIEW)}">']
    if plate: o.append(f'<rect width="{fmt(w)}" height="{fmt(h)}" rx="{RADIUS}" fill="{WHITE}"/>')
    for tag, col in colors.items():
        o.append(f'<g fill="{col}">')
        for t, a, s, d, _ in g:
            if t == tag and d: o.append(f'<path transform="translate({fmt(ox+a-x0+off)} {fmt(base_y)}) scale({s:.5f} {-s:.5f})" d="{d}"/>')
        o.append("</g>")
    if bird:
        ccx = (ox + CD / 2) if LEFT else (ox + inkw - OVERLAP + CD / 2); ccy = oy + ch / 2
        if circle: o.append(f'<circle cx="{fmt(ccx)}" cy="{fmt(ccy)}" r="{fmt(CD/2)}" fill="{BLUE}" stroke="{ring}" stroke-width="0.8"/>')
        tx = ccx - (VB_X + VB_W / 2) * bs; ty = ccy - (VB_Y + VB_H / 2) * bs
        o.append(f'<g transform="translate({fmt(tx)} {fmt(ty)}) scale({bs:.5f})">{bp_}</g>')
    o.append("</svg>"); return "\n".join(o)

# Final: ask weight 800 in CD blue, Francis weight 500, Francis 15 high inside a blue circle of 23, gap 8, round plate radius 8.
PARTS = [("ask", 800, "k"), ("Francis", 500, "f")]
RADIUS = 8
OVERLAP = -8.0
LEFT = True
B, CD = 18, 27
for bird, suffix in ((True, ""), (False, "-ohne-francis")):
    for kind, plate, cols, ring in (("plate", True, {"k": BLUE, "f": BLACK}, "none"),
                                    ("transparent-black", False, {"k": BLUE, "f": BLACK}, "none"),
                                    ("transparent-white", False, {"k": WHITE, "f": WHITE}, WHITE)):
        n = f"askfrancis-logo-{kind}{suffix}.svg"
        # On the white variant Francis stands free on the blue ground, no circle.
        B = 26 if kind == "transparent-white" else 18
        open(f"{OUT}/{n}", "w").write(svg(PARTS, cols, bird, plate, ring, circle=(kind != "transparent-white"))); print(n)
