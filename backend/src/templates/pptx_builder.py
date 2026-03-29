"""THL PPTX Builder — 12 layouts + user template support.

Two modes:
1. Template mode: User provides PPTX with tagged slides (notes: #deckblatt, etc.)
   → Template slides are cloned as visual base, content is overlaid.
   → #headerfooter tag: branding shell used for ALL slides without own template.
2. Fallback mode: System-built layouts with THL branding (no template needed).

Tags in slide notes:
  #deckblatt         — Cover/title slide
  #kapitel           — Chapter/section divider
  #abschluss         — Closing slide
  #headerfooter      — Branding shell (header/footer/logos) for all other slides
  #content           — Content slide template (can combine with #headerfooter)
  #statement, #icon_grid, #vergleich, #zitat, #zweispalten,
  #zusammenfassung, #statistik, #zeitstrahl — specific layout templates
"""

import io
import os
import re
import tempfile
from copy import deepcopy

from lxml import etree
from pptx import Presentation as PptxPresentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

# ── Colors ──────────────────────────────────────────────────────────────────
BLACK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x6B, 0x72, 0x80)
THL_RED = RGBColor(0xE3, 0x00, 0x2B)
BRAND_BLUE = RGBColor(0x00, 0x42, 0x61)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF3, 0xF4, 0xF6)
LIGHT_BLUE = RGBColor(0xEF, 0xF6, 0xFF)
TEAL = RGBColor(0x0E, 0x74, 0x90)

FONT = "Arial"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo-thl.jpg")

# Default slide dimensions (fallback, 16:9)
SW = Inches(13.333)
SH = Inches(7.5)
FOOTER_H = Inches(0.35)

ALL_TAGS = {
    "deckblatt", "kapitel", "abschluss", "headerfooter",
    "content", "statement", "icon_grid", "vergleich", "zitat",
    "zweispalten", "zusammenfassung", "statistik", "zeitstrahl",
}


# ── Drawing helpers ─────────────────────────────────────────────────────────

def _add_logo(sl):
    if os.path.exists(LOGO_PATH):
        sl.shapes.add_picture(LOGO_PATH, Inches(11.0), Inches(0.25), Inches(1.9))


def _add_footer(sl):
    sh = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, SH - FOOTER_H, SW, FOOTER_H)
    sh.fill.solid()
    sh.fill.fore_color.rgb = THL_RED
    sh.line.fill.background()


def _brand(sl):
    _add_footer(sl)
    _add_logo(sl)


def _txt(sl, left, top, w, h, text, size=18, bold=False, color=BLACK,
         align=PP_ALIGN.LEFT, italic=False):
    if not text:
        return None
    tb = sl.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    r.font.name = FONT
    return tb


def _bullets(sl, left, top, w, h, items, size=15, color=BLACK,
             bullet_color=THL_RED, spacing=8):
    if not items:
        return None
    tb = sl.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, txt in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(spacing)
        p.space_after = Pt(3)
        r1 = p.add_run()
        r1.text = "\u2022  "
        r1.font.size = Pt(size)
        r1.font.bold = True
        r1.font.color.rgb = bullet_color
        r1.font.name = FONT
        r2 = p.add_run()
        r2.text = txt
        r2.font.size = Pt(size)
        r2.font.color.rgb = color
        r2.font.name = FONT
    return tb


def _box(sl, left, top, w, h, color):
    sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def _rect(sl, left, top, w, h, color):
    sh = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def _img(sl, img_bytes, left, top, max_w, max_h):
    from PIL import Image as PILImage
    pil = PILImage.open(io.BytesIO(img_bytes))
    iw, ih = pil.size
    if not iw or not ih:
        return
    img_ratio = iw / ih
    box_ratio = max_w / max_h
    if img_ratio > box_ratio:
        final_w = max_w
        final_h = int(max_w / img_ratio)
    else:
        final_h = max_h
        final_w = int(max_h * img_ratio)
    ox = (max_w - final_w) // 2
    oy = (max_h - final_h) // 2
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img_bytes)
        path = tmp.name
    try:
        sl.shapes.add_picture(path, left + ox, top + oy, final_w, final_h)
    finally:
        os.unlink(path)


def _slide_num(sl, idx):
    _txt(sl, Inches(12.3), Inches(6.85), Inches(0.8), Inches(0.3),
         str(idx + 1), size=8, color=MUTED, align=PP_ALIGN.RIGHT)


# ── Template parsing ────────────────────────────────────────────────────────

def _get_slide_tags(slide) -> set[str]:
    """Read all #tags from slide notes."""
    try:
        notes = slide.notes_slide.notes_text_frame.text.strip()
    except Exception:
        return set()
    tags = set()
    for word in notes.split():
        if word.startswith("#"):
            tag = word[1:].lower().strip()
            if tag in ALL_TAGS:
                tags.add(tag)
    return tags


def _clone_slide(prs, src_idx):
    """Clone a slide within the same presentation. Returns the new slide."""
    src_slide = prs.slides[src_idx]
    new_slide = prs.slides.add_slide(src_slide.slide_layout)

    # Remove auto-generated shapes
    sp_tree = new_slide.shapes._spTree
    to_remove = [
        child for child in sp_tree
        if etree.QName(child).localname not in ("nvGrpSpPr", "grpSpPr")
    ]
    for child in to_remove:
        sp_tree.remove(child)

    # Copy shapes from source
    for child in src_slide.shapes._spTree:
        if etree.QName(child).localname not in ("nvGrpSpPr", "grpSpPr"):
            sp_tree.append(deepcopy(child))

    # Copy background
    nsmap = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    src_bg = src_slide._element.find("p:bg", nsmap)
    if src_bg is not None:
        dest_bg = new_slide._element.find("p:bg", nsmap)
        if dest_bg is not None:
            new_slide._element.remove(dest_bg)
        new_slide._element.insert(0, deepcopy(src_bg))

    # Copy image relationships
    for key, rel in src_slide.part.rels.items():
        if "image" in rel.reltype and not rel.is_external:
            try:
                new_slide.part.relate_to(rel.target_part, rel.reltype, rId=key)
            except Exception:
                new_slide.part.relate_to(rel.target_part, rel.reltype)

    return new_slide


def _ph(sl, idx):
    """Get placeholder by index, return None if not found."""
    for shape in sl.shapes:
        try:
            if shape.placeholder_format and shape.placeholder_format.idx == idx:
                return shape
        except ValueError:
            continue
    return None


def _set_ph_text(ph, text, size=18, bold=False, color=BLACK):
    """Fill a placeholder with formatted text."""
    if not ph or not text:
        return
    ph.text = text
    for p in ph.text_frame.paragraphs:
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = FONT


def _insert_picture_ph(sl, idx, img_bytes):
    """Insert image into a picture placeholder."""
    ph = _ph(sl, idx)
    if not ph:
        return False
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img_bytes)
        path = tmp.name
    try:
        ph.insert_picture(path)
        return True
    except Exception:
        return False
    finally:
        os.unlink(path)


def _analyze_template(slide) -> dict:
    """Analyze a template slide and return placeholder info.

    Returns dict with placeholder positions/sizes keyed by idx.
    Also computes the 'free area' below the last known placeholder.
    """
    phs = {}
    footer_top = None

    for shape in slide.shapes:
        try:
            ph_fmt = shape.placeholder_format
        except ValueError:
            continue
        if ph_fmt is None:
            continue
        idx = ph_fmt.idx
        phs[idx] = {
            "left": shape.left, "top": shape.top,
            "width": shape.width, "height": shape.height,
        }
        # Track footer/slide-number placeholders (idx 2,3,4,5)
        if idx in (2, 3, 4, 5):
            ft = shape.top
            if footer_top is None or ft < footer_top:
                footer_top = ft

    # Compute free content area (below title/subtitle placeholder, above footer)
    # Title placeholder is usually idx 0 or idx 13
    title_ph = phs.get(0) or phs.get(13)
    if title_ph:
        content_top = title_ph["top"] + title_ph["height"] + Inches(0.3)
        content_left = title_ph["left"]
        content_w = title_ph["width"]
    else:
        content_top = Inches(1.8)
        content_left = Inches(0.4)
        content_w = Inches(11.3)

    content_bottom = (footer_top - Inches(0.2)) if footer_top else Inches(6.5)
    content_h = max(content_bottom - content_top, Inches(1.0))

    return {
        "phs": phs,
        "content_left": content_left,
        "content_top": content_top,
        "content_w": content_w,
        "content_h": content_h,
    }


# ── Fallback layout renderers (no template, system branding) ────────────────

def _render_deckblatt(sl, s, img_bytes, branded):
    if not branded:
        _brand(sl)
    _txt(sl, Inches(0.8), Inches(1.5), Inches(7.5), Inches(3.0),
         s.get("title", ""), size=32, bold=True, color=BLACK)
    if s.get("subtitle"):
        _txt(sl, Inches(0.8), Inches(4.6), Inches(7.5), Inches(1.2),
             s["subtitle"], size=16, color=MUTED)
    if img_bytes:
        _img(sl, img_bytes, Inches(9.0), Inches(1.0), Inches(3.8), Inches(5.0))


def _render_kapitel(sl, s, section_counter, branded):
    if not branded:
        _rect(sl, 0, 0, SW, SH, BRAND_BLUE)
        _add_footer(sl)
        if os.path.exists(LOGO_PATH):
            sl.shapes.add_picture(LOGO_PATH, Inches(11.0), Inches(0.25), Inches(1.9))
    num = s.get("number", str(section_counter))
    _txt(sl, Inches(1.0), Inches(1.5), Inches(4), Inches(4),
         num, size=96, bold=True, color=THL_RED)
    _txt(sl, Inches(5.0), Inches(2.5), Inches(7.5), Inches(1.5),
         s.get("title", ""), size=28, bold=True, color=WHITE)
    if s.get("subtitle"):
        _txt(sl, Inches(5.0), Inches(4.2), Inches(7.5), Inches(1.2),
             s["subtitle"], size=15, color=RGBColor(0xBB, 0xD5, 0xE8))


def _render_abschluss(sl, s, branded):
    if not branded:
        _brand(sl)
    _txt(sl, Inches(2.0), Inches(2.5), Inches(9.3), Inches(1.5),
         s.get("title", "Vielen Dank."), size=36, bold=True, color=BLACK,
         align=PP_ALIGN.CENTER)
    if s.get("subtitle"):
        _txt(sl, Inches(2.0), Inches(4.2), Inches(9.3), Inches(1.0),
             s["subtitle"], size=16, color=MUTED, align=PP_ALIGN.CENTER)


def _render_content(sl, s, img_bytes, idx, branded,
                    cx=None, cy=None, cw=None, ch=None,
                    tx=None, ty=None, th=None):
    """Content: title + bullets, optional image right."""
    if not branded:
        _brand(sl)
    # Use detected area or defaults
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _th = th or Inches(1.0)
    _cx = cx or Inches(0.8)
    _cy = cy or Inches(2.8)
    _cw = cw or Inches(11.7)
    _ch = ch or Inches(3.6)

    has_img = img_bytes is not None
    title_w = int(_cw * 0.6) if has_img else _cw
    _txt(sl, _tx, _ty, title_w, _th,
         s.get("title", ""), size=22, bold=True, color=BLACK)
    bullet_w = int(_cw * 0.58) if has_img else _cw
    _bullets(sl, _cx, _cy, bullet_w, _ch,
             s.get("bullets", []), size=14)
    if has_img:
        img_left = _cx + int(_cw * 0.63)
        img_w = int(_cw * 0.35)
        _img(sl, img_bytes, img_left, _cy - Inches(0.5), img_w, _ch + Inches(0.5))
    _slide_num(sl, idx)


def _render_statement(sl, s, idx, branded,
                      tx=None, ty=None, cw=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.5)
    _cw = cw or Inches(11.7)
    _txt(sl, _tx, _ty, _cw, Inches(2.5),
         s.get("title", ""), size=26, bold=True, color=BLACK)
    if s.get("body"):
        _txt(sl, _tx, _ty + Inches(2.7), _cw, Inches(2.0),
             s["body"], size=14, color=MUTED)
    _slide_num(sl, idx)


def _render_icon_grid(sl, s, idx, branded,
                      cx=None, cy=None, cw=None,
                      tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(0.8)
    _cy = cy or Inches(2.8)
    _cw = cw or Inches(11.7)

    _txt(sl, _tx, _ty, _cw, Inches(0.8),
         s.get("title", ""), size=22, bold=True, color=BLACK)

    items = s.get("items", [])[:4]
    half_w = _cw // 2
    grid = [
        (_cx, _cy),
        (_cx + half_w, _cy),
        (_cx, _cy + Inches(2.2)),
        (_cx + half_w, _cy + Inches(2.2)),
    ]
    colors = [THL_RED, BRAND_BLUE, TEAL, THL_RED]

    for i, item in enumerate(items):
        gx, gy = grid[i]
        circle = sl.shapes.add_shape(
            MSO_SHAPE.OVAL, gx, gy + Inches(0.05), Inches(0.22), Inches(0.22))
        circle.fill.solid()
        circle.fill.fore_color.rgb = colors[i % 4]
        circle.line.fill.background()
        _txt(sl, gx + Inches(0.4), gy, half_w - Inches(0.8), Inches(0.4),
             item.get("title", ""), size=13, bold=True, color=BLACK)
        _txt(sl, gx + Inches(0.4), gy + Inches(0.45), half_w - Inches(0.8), Inches(1.5),
             item.get("body", ""), size=11, color=MUTED)
    _slide_num(sl, idx)


def _render_vergleich(sl, s, idx, branded,
                      cx=None, cy=None, cw=None,
                      tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(0.6)
    _cy = cy or Inches(2.6)
    _cw = cw or Inches(12.0)

    _txt(sl, _tx, _ty, _cw, Inches(0.8),
         s.get("title", ""), size=22, bold=True, color=BLACK)

    box_w = (_cw - Inches(0.6)) // 2
    _box(sl, _cx, _cy, box_w, Inches(3.9), LIGHT_GRAY)
    if s.get("left_title"):
        _txt(sl, _cx + Inches(0.3), _cy + Inches(0.2), box_w - Inches(0.6), Inches(0.4),
             s["left_title"], size=13, bold=True, color=BRAND_BLUE)
    _bullets(sl, _cx + Inches(0.3), _cy + Inches(0.8), box_w - Inches(0.6), Inches(2.7),
             s.get("left_bullets", []), size=12, bullet_color=BRAND_BLUE)

    right_x = _cx + box_w + Inches(0.6)
    _box(sl, right_x, _cy, box_w, Inches(3.9), LIGHT_BLUE)
    if s.get("right_title"):
        _txt(sl, right_x + Inches(0.3), _cy + Inches(0.2), box_w - Inches(0.6), Inches(0.4),
             s["right_title"], size=13, bold=True, color=BRAND_BLUE)
    _bullets(sl, right_x + Inches(0.3), _cy + Inches(0.8), box_w - Inches(0.6), Inches(2.7),
             s.get("right_bullets", []), size=12, bullet_color=BRAND_BLUE)
    _slide_num(sl, idx)


def _render_zitat(sl, s, idx, branded,
                  cx=None, cy=None, cw=None,
                  tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(0.8)
    _cy = cy or Inches(2.6)
    _cw = cw or Inches(11.7)

    _txt(sl, _tx, _ty, _cw, Inches(0.8),
         s.get("title", ""), size=20, bold=True, color=BLACK)

    _box(sl, _cx, _cy, _cw, Inches(2.0), LIGHT_GRAY)
    _rect(sl, _cx, _cy, Inches(0.08), Inches(2.0), THL_RED)
    _txt(sl, _cx + Inches(0.5), _cy + Inches(0.3), _cw - Inches(1.0), Inches(1.5),
         f"\u201E{s.get('quote', '')}\u201C", size=15, italic=True, color=BLACK)

    if s.get("body"):
        _txt(sl, _cx, _cy + Inches(2.5), _cw, Inches(1.5),
             s["body"], size=13, color=MUTED)
    _slide_num(sl, idx)


def _render_zweispalten(sl, s, idx, branded,
                        cx=None, cy=None, cw=None,
                        tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(0.8)
    _cy = cy or Inches(2.8)
    _cw = cw or Inches(11.7)

    _txt(sl, _tx, _ty, _cw, Inches(0.8),
         s.get("title", ""), size=22, bold=True, color=BLACK)

    half_w = (_cw - Inches(0.5)) // 2
    _rect(sl, _cx + half_w + Inches(0.2), _cy, Inches(0.02), Inches(3.8), LIGHT_GRAY)

    if s.get("left_text"):
        _txt(sl, _cx, _cy, half_w, Inches(3.6), s["left_text"], size=13, color=BLACK)
    if s.get("left_bullets"):
        _bullets(sl, _cx, _cy, half_w, Inches(3.6), s["left_bullets"], size=12)

    right_x = _cx + half_w + Inches(0.5)
    if s.get("right_text"):
        _txt(sl, right_x, _cy, half_w, Inches(3.6), s["right_text"], size=13, color=BLACK)
    if s.get("right_bullets"):
        _bullets(sl, right_x, _cy, half_w, Inches(3.6), s["right_bullets"], size=12)
    _slide_num(sl, idx)


def _render_zusammenfassung(sl, s, idx, branded,
                            cx=None, cy=None, cw=None,
                            tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(0.8)
    _cy = cy or Inches(2.8)
    _cw = cw or Inches(11.7)

    _txt(sl, _tx, _ty, _cw, Inches(1.0),
         s.get("title", "Zusammenfassung"), size=24, bold=True, color=BLACK)
    _bullets(sl, _cx, _cy, _cw, Inches(3.7),
             s.get("bullets", []), size=15, spacing=12)
    _slide_num(sl, idx)


def _render_statistik(sl, s, idx, branded,
                      cx=None, cy=None, cw=None,
                      tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(1.5)
    _cw = cw or Inches(10.3)

    _txt(sl, _tx, _ty, _cw, Inches(0.8),
         s.get("title", ""), size=22, bold=True, color=BLACK)

    stats = s.get("stats", [])[:3]
    n = len(stats) or 1
    col_w = _cw // n

    for i, stat in enumerate(stats):
        sx = _cx + col_w * i
        _txt(sl, sx, Inches(3.0), col_w - Inches(0.3), Inches(1.2),
             str(stat.get("value", "")), size=48, bold=True, color=THL_RED,
             align=PP_ALIGN.CENTER)
        _txt(sl, sx, Inches(4.3), col_w - Inches(0.3), Inches(0.5),
             stat.get("label", ""), size=14, bold=True, color=BLACK,
             align=PP_ALIGN.CENTER)
        if stat.get("description"):
            _txt(sl, sx, Inches(4.9), col_w - Inches(0.3), Inches(1.0),
                 stat["description"], size=11, color=MUTED, align=PP_ALIGN.CENTER)
    _slide_num(sl, idx)


def _render_zeitstrahl(sl, s, idx, branded,
                       cx=None, cy=None, cw=None,
                       tx=None, ty=None):
    if not branded:
        _brand(sl)
    _tx = tx or Inches(0.8)
    _ty = ty or Inches(1.2)
    _cx = cx or Inches(1.1)
    _cy = cy or Inches(2.8)

    _txt(sl, _tx, _ty, Inches(11.7), Inches(0.8),
         s.get("title", ""), size=22, bold=True, color=BLACK)

    steps = s.get("steps", [])[:6]
    if not steps:
        return
    step_h = min(Inches(0.8), Inches(4.0) // max(len(steps), 1))

    for i, step in enumerate(steps):
        sy = _cy + step_h * i
        if i < len(steps) - 1:
            _rect(sl, _cx + Inches(0.28), sy + Inches(0.35),
                  Inches(0.04), step_h - Inches(0.05), LIGHT_GRAY)
        circle = sl.shapes.add_shape(
            MSO_SHAPE.OVAL, _cx, sy, Inches(0.6), Inches(0.6))
        circle.fill.solid()
        circle.fill.fore_color.rgb = THL_RED if i == 0 else BRAND_BLUE
        circle.line.fill.background()
        _txt(sl, _cx + Inches(0.05), sy + Inches(0.1), Inches(0.5), Inches(0.4),
             str(i + 1), size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        _txt(sl, _cx + Inches(0.9), sy, Inches(6.5), Inches(0.4),
             step.get("label", ""), size=14, bold=True, color=BLACK)
        if step.get("description"):
            _txt(sl, _cx + Inches(0.9), sy + Inches(0.35), Inches(6.5), Inches(0.4),
                 step["description"], size=11, color=MUTED)
    _slide_num(sl, idx)


# ── Layout dispatcher ───────────────────────────────────────────────────────

def _render_layout(sl, s, img_bytes, idx, section_counter, branded=False,
                   area=None):
    """Render content onto a slide using the appropriate layout.

    Args:
        branded: True if slide already has branding (from template clone).
        area: Optional (left, title_top, title_h, content_top, content_w, content_h)
              detected from template placeholders.
    """
    lay = s.get("layout", "content")

    # Extract area params for layouts that support them
    kw = {}
    if area:
        left, title_top, title_h, content_top, content_w, content_h = area
        kw = dict(tx=left, ty=title_top, cx=left, cy=content_top,
                  cw=content_w, ch=content_h)

    if lay == "deckblatt":
        _render_deckblatt(sl, s, img_bytes, branded)
    elif lay == "kapitel":
        _render_kapitel(sl, s, section_counter, branded)
    elif lay == "abschluss":
        _render_abschluss(sl, s, branded)
    elif lay == "statement":
        _render_statement(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("tx", "ty", "cw")})
    elif lay == "icon_grid":
        _render_icon_grid(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "vergleich":
        _render_vergleich(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "zitat":
        _render_zitat(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "zweispalten":
        _render_zweispalten(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "zusammenfassung":
        _render_zusammenfassung(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "statistik":
        _render_statistik(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    elif lay == "zeitstrahl":
        _render_zeitstrahl(sl, s, idx, branded, **{k: v for k, v in kw.items() if k in ("cx", "cy", "cw", "tx", "ty")})
    else:  # content
        _render_content(sl, s, img_bytes, idx, branded, **kw)


# ── Main builder ────────────────────────────────────────────────────────────

def build_pptx(pres_title: str, slides_data: list[dict],
               images: dict[int, bytes],
               template_path: str | None = None) -> bytes:
    """Build a PPTX presentation.

    Args:
        pres_title: Presentation title (metadata).
        slides_data: List of slide dicts with "layout" + content fields.
        images: Map of slide_index → PNG bytes for generated images.
        template_path: Optional path to a user-provided PPTX template.
    """
    if template_path and os.path.exists(template_path):
        return _build_with_template(pres_title, slides_data, images, template_path)
    return _build_fallback(pres_title, slides_data, images)


def _build_fallback(pres_title: str, slides_data: list[dict],
                    images: dict[int, bytes]) -> bytes:
    """Build PPTX entirely with system layouts + THL branding."""
    prs = PptxPresentation()
    prs.slide_width = SW
    prs.slide_height = SH
    blank = prs.slide_layouts[6]
    section_counter = 0

    for idx, s in enumerate(slides_data):
        if s.get("layout") == "kapitel":
            section_counter += 1
        sl = prs.slides.add_slide(blank)
        _render_layout(sl, s, images.get(idx), idx, section_counter, branded=False)
        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = s["notes"]

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _fill_template_slide(sl, s, img_bytes, idx, section_counter, tmpl_info):
    """Fill a cloned template slide by writing into its placeholders
    and placing content shapes in the free area below the title.

    tmpl_info comes from _analyze_template().
    """
    lay = s.get("layout", "content")
    cx = tmpl_info["content_left"]
    cy = tmpl_info["content_top"]
    cw = tmpl_info["content_w"]
    ch = tmpl_info["content_h"]
    phs = tmpl_info["phs"]

    # ── Fill title placeholder (ph 0 or ph 13) ─────────────────────────────
    title_text = s.get("title", "")
    title_ph = _ph(sl, 0)
    if not title_ph:
        title_ph = _ph(sl, 13)
    if title_ph and title_text:
        _set_ph_text(title_ph, title_text, size=22, bold=True, color=BLACK)

    # ── Fill subtitle placeholder (ph 1) ────────────────────────────────────
    subtitle_text = s.get("subtitle", "")
    subtitle_ph = _ph(sl, 1)
    if subtitle_ph and subtitle_text:
        _set_ph_text(subtitle_ph, subtitle_text, size=14, color=MUTED)

    # ── Fill image placeholder (ph 26) ──────────────────────────────────────
    if img_bytes and 26 in phs:
        _insert_picture_ph(sl, 26, img_bytes)

    # ── Fill slide number placeholder (ph 4) ────────────────────────────────
    sn_ph = _ph(sl, 4)
    if sn_ph:
        _set_ph_text(sn_ph, str(idx + 1), size=8, color=MUTED)

    # ── Layout-specific content in free area ────────────────────────────────
    if lay == "deckblatt":
        # Placeholders already filled above, add image if no ph 26
        if img_bytes and 26 not in phs:
            _img(sl, img_bytes, cx + int(cw * 0.6), cy, int(cw * 0.38), ch)

    elif lay == "kapitel":
        # Big number in content area
        num = s.get("number", str(section_counter))
        _txt(sl, cx, cy, Inches(2.5), Inches(2),
             num, size=72, bold=True, color=THL_RED)

    elif lay == "abschluss":
        pass  # Title/subtitle/image placeholders are enough

    elif lay == "content":
        has_img = img_bytes is not None and 26 not in phs
        bw = int(cw * 0.58) if has_img else cw
        _bullets(sl, cx, cy, bw, ch, s.get("bullets", []), size=14)
        if has_img:
            _img(sl, img_bytes, cx + int(cw * 0.63), cy, int(cw * 0.35), ch)

    elif lay == "statement":
        if s.get("body"):
            _txt(sl, cx, cy, cw, ch, s["body"], size=14, color=MUTED)

    elif lay == "icon_grid":
        items = s.get("items", [])[:4]
        half_w = cw // 2
        grid = [
            (cx, cy), (cx + half_w, cy),
            (cx, cy + Inches(2.2)), (cx + half_w, cy + Inches(2.2)),
        ]
        colors = [THL_RED, BRAND_BLUE, TEAL, THL_RED]
        for i, item in enumerate(items):
            gx, gy = grid[i]
            circle = sl.shapes.add_shape(
                MSO_SHAPE.OVAL, gx, gy + Inches(0.05), Inches(0.22), Inches(0.22))
            circle.fill.solid()
            circle.fill.fore_color.rgb = colors[i % 4]
            circle.line.fill.background()
            _txt(sl, gx + Inches(0.4), gy, half_w - Inches(0.8), Inches(0.4),
                 item.get("title", ""), size=13, bold=True, color=BLACK)
            _txt(sl, gx + Inches(0.4), gy + Inches(0.45), half_w - Inches(0.8), Inches(1.5),
                 item.get("body", ""), size=11, color=MUTED)

    elif lay == "vergleich":
        box_w = (cw - Inches(0.6)) // 2
        _box(sl, cx, cy, box_w, ch, LIGHT_GRAY)
        if s.get("left_title"):
            _txt(sl, cx + Inches(0.3), cy + Inches(0.2), box_w - Inches(0.6), Inches(0.4),
                 s["left_title"], size=13, bold=True, color=BRAND_BLUE)
        _bullets(sl, cx + Inches(0.3), cy + Inches(0.8), box_w - Inches(0.6), ch - Inches(1.2),
                 s.get("left_bullets", []), size=12, bullet_color=BRAND_BLUE)
        rx = cx + box_w + Inches(0.6)
        _box(sl, rx, cy, box_w, ch, LIGHT_BLUE)
        if s.get("right_title"):
            _txt(sl, rx + Inches(0.3), cy + Inches(0.2), box_w - Inches(0.6), Inches(0.4),
                 s["right_title"], size=13, bold=True, color=BRAND_BLUE)
        _bullets(sl, rx + Inches(0.3), cy + Inches(0.8), box_w - Inches(0.6), ch - Inches(1.2),
                 s.get("right_bullets", []), size=12, bullet_color=BRAND_BLUE)

    elif lay == "zitat":
        _box(sl, cx, cy, cw, Inches(2.0), LIGHT_GRAY)
        _rect(sl, cx, cy, Inches(0.08), Inches(2.0), THL_RED)
        _txt(sl, cx + Inches(0.5), cy + Inches(0.3), cw - Inches(1.0), Inches(1.5),
             f"\u201E{s.get('quote', '')}\u201C", size=15, italic=True, color=BLACK)
        if s.get("body"):
            _txt(sl, cx, cy + Inches(2.5), cw, Inches(1.5),
                 s["body"], size=13, color=MUTED)

    elif lay == "zweispalten":
        half_w = (cw - Inches(0.5)) // 2
        _rect(sl, cx + half_w + Inches(0.2), cy, Inches(0.02), ch, LIGHT_GRAY)
        if s.get("left_bullets"):
            _bullets(sl, cx, cy, half_w, ch, s["left_bullets"], size=12)
        if s.get("left_text"):
            _txt(sl, cx, cy, half_w, ch, s["left_text"], size=13, color=BLACK)
        rx = cx + half_w + Inches(0.5)
        if s.get("right_bullets"):
            _bullets(sl, rx, cy, half_w, ch, s["right_bullets"], size=12)
        if s.get("right_text"):
            _txt(sl, rx, cy, half_w, ch, s["right_text"], size=13, color=BLACK)

    elif lay == "zusammenfassung":
        _bullets(sl, cx, cy, cw, ch, s.get("bullets", []), size=15, spacing=12)

    elif lay == "statistik":
        stats = s.get("stats", [])[:3]
        n = len(stats) or 1
        col_w = cw // n
        for i, stat in enumerate(stats):
            sx = cx + col_w * i
            _txt(sl, sx, cy, col_w, Inches(1.2),
                 str(stat.get("value", "")), size=48, bold=True, color=THL_RED,
                 align=PP_ALIGN.CENTER)
            _txt(sl, sx, cy + Inches(1.3), col_w, Inches(0.5),
                 stat.get("label", ""), size=14, bold=True, color=BLACK,
                 align=PP_ALIGN.CENTER)
            if stat.get("description"):
                _txt(sl, sx, cy + Inches(1.9), col_w, Inches(1.0),
                     stat["description"], size=11, color=MUTED, align=PP_ALIGN.CENTER)

    elif lay == "zeitstrahl":
        steps = s.get("steps", [])[:6]
        if steps:
            step_h = min(Inches(0.8), ch // max(len(steps), 1))
            line_x = cx + Inches(0.28)
            for i, step in enumerate(steps):
                sy = cy + step_h * i
                if i < len(steps) - 1:
                    _rect(sl, line_x, sy + Inches(0.35),
                          Inches(0.04), step_h - Inches(0.05), LIGHT_GRAY)
                circle = sl.shapes.add_shape(
                    MSO_SHAPE.OVAL, cx, sy, Inches(0.6), Inches(0.6))
                circle.fill.solid()
                circle.fill.fore_color.rgb = THL_RED if i == 0 else BRAND_BLUE
                circle.line.fill.background()
                _txt(sl, cx + Inches(0.05), sy + Inches(0.1), Inches(0.5), Inches(0.4),
                     str(i + 1), size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
                _txt(sl, cx + Inches(0.9), sy, cw - Inches(1.0), Inches(0.4),
                     step.get("label", ""), size=14, bold=True, color=BLACK)
                if step.get("description"):
                    _txt(sl, cx + Inches(0.9), sy + Inches(0.35), cw - Inches(1.0), Inches(0.4),
                         step["description"], size=11, color=MUTED)

    else:
        # Unknown layout → treat as content
        _bullets(sl, cx, cy, cw, ch, s.get("bullets", []), size=14)


def _build_with_template(pres_title: str, slides_data: list[dict],
                         images: dict[int, bytes],
                         template_path: str) -> bytes:
    """Build PPTX using a user-provided template.

    Strategy:
      - Parse tags from template slide notes.
      - For each output slide, find the best matching template slide
        (exact tag → #content/#headerfooter fallback → system fallback).
      - Clone the template slide, fill its placeholders, add content
        shapes in the free area.
    """
    prs = PptxPresentation(template_path)

    # Parse template: tag → slide index (first match only)
    tag_to_idx: dict[str, int] = {}
    for i, slide in enumerate(prs.slides):
        tags = _get_slide_tags(slide)
        for tag in tags:
            if tag not in tag_to_idx:
                tag_to_idx[tag] = i

    # Position-based fallback if no tags at all
    if not tag_to_idx:
        n = len(prs.slides)
        if n >= 1:
            tag_to_idx["deckblatt"] = 0
        if n >= 3:
            tag_to_idx["abschluss"] = n - 1
            tag_to_idx["content"] = 1
        elif n == 2:
            tag_to_idx["abschluss"] = 1

    # Pre-analyze template slides for placeholder positions
    tmpl_infos: dict[int, dict] = {}
    for tag, tidx in tag_to_idx.items():
        if tidx not in tmpl_infos:
            tmpl_infos[tidx] = _analyze_template(prs.slides[tidx])

    original_count = len(prs.slides)
    section_counter = 0

    for idx, s in enumerate(slides_data):
        lay = s.get("layout", "content")
        img_bytes = images.get(idx)

        if lay == "kapitel":
            section_counter += 1

        # Find best template slide:
        # 1. Exact tag match
        # 2. #content or #headerfooter for content-type layouts
        # 3. #headerfooter as universal shell
        # 4. No match → system fallback
        tmpl_idx = tag_to_idx.get(lay)
        if tmpl_idx is None and lay not in ("deckblatt", "kapitel", "abschluss"):
            tmpl_idx = tag_to_idx.get("content")
        if tmpl_idx is None:
            tmpl_idx = tag_to_idx.get("headerfooter")

        if tmpl_idx is not None:
            sl = _clone_slide(prs, tmpl_idx)
            info = tmpl_infos[tmpl_idx]
            _fill_template_slide(sl, s, img_bytes, idx, section_counter, info)
        else:
            blank = prs.slide_layouts[6]
            sl = prs.slides.add_slide(blank)
            _render_layout(sl, s, img_bytes, idx, section_counter, branded=False)

        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = s["notes"]

    # Remove original template slides
    for _ in range(original_count):
        sld_id = prs.slides._sldIdLst[0]
        rId = sld_id.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rId:
            prs.part.drop_rel(rId)
        prs.slides._sldIdLst.remove(sld_id)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
