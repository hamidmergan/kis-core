"""THL Corporate Design PPTX Builder — uses the official THL master template.

The template (template.pptx) provides:
- Slide Master with THL logo (top-right) + red footer bar on every slide
- Layout 0: Titelfolie (title + subtitle + 2 picture placeholders)
- Layout 2: Titel und Inhalt (title idx=0 + content idx=1 + footer idx=23)
- Layout 3: 1_Titel und Inhalt (title idx=0 + content idx=1 + red accent)
- Layout 4: Abschnittsüberschrift (title idx=0 only)

Slide size: 10.0 x 7.5 inches.
"""

import io
import os
import tempfile

from pptx import Presentation as PptxPresentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

BLACK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x6B, 0x72, 0x80)
THL_RED = RGBColor(0xE3, 0x00, 0x2B)
BRAND_BLUE = RGBColor(0x00, 0x42, 0x61)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF3, 0xF4, 0xF6)
LIGHT_BLUE = RGBColor(0xEF, 0xF6, 0xFF)
FONT = "Arial"

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "template.pptx")


def _ph(sl, idx):
    """Get placeholder by index, return None if not found."""
    try:
        return sl.placeholders[idx]
    except (KeyError, IndexError):
        return None


def _set_ph_text(sl, idx, text, size=18, bold=False, color=BLACK):
    """Set text on a placeholder with formatting."""
    ph = _ph(sl, idx)
    if not ph or not text:
        return
    ph.text = text
    for p in ph.text_frame.paragraphs:
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = FONT


def _clear_ph(sl, idx):
    """Clear a placeholder's text."""
    ph = _ph(sl, idx)
    if ph:
        ph.text = ""


def _fill_ph_bullets(sl, idx, items, size=16, color=BLACK):
    """Fill a placeholder with bullet points."""
    ph = _ph(sl, idx)
    if not ph or not items:
        return
    tf = ph.text_frame
    tf.clear()
    for i, txt in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(8)
        p.space_after = Pt(3)
        r = p.add_run()
        r.text = f"\u2022  {txt}"
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.name = FONT


def _txt(sl, left, top, w, h, text, size=18, bold=False, color=BLACK, align=PP_ALIGN.LEFT):
    """Add a free textbox."""
    tb = sl.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = FONT
    return tb


def _bullets(sl, left, top, w, h, items, size=16, color=BLACK, spacing=8):
    """Add a free bullet list."""
    if not items:
        return
    tb = sl.shapes.add_textbox(left, top, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, txt in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(spacing)
        p.space_after = Pt(3)
        r = p.add_run()
        r.text = f"\u2022  {txt}"
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.name = FONT


def _img(sl, img_bytes, left, top, max_w, max_h):
    """Add image preserving aspect ratio."""
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


def _box(sl, left, top, w, h, color):
    sh = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    return sh


def build_pptx(pres_title: str, slides_data: list[dict], images: dict[int, bytes]) -> bytes:
    """Build THL Corporate PPTX using the master template."""
    prs = PptxPresentation(TEMPLATE_PATH)

    # Remove example slides
    while len(prs.slides) > 0:
        rId = prs.slides._sldIdLst[0].get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if rId:
            prs.part.drop_rel(rId)
        prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])

    layouts = prs.slide_layouts
    LAYOUT_TITLE = layouts[0]     # idx: 0=title, 1=subtitle, 21/22=pictures
    LAYOUT_MAIN = layouts[2]      # idx: 0=title, 1=content, 23=footer-text
    LAYOUT_ALT = layouts[3]       # idx: 0=title, 1=content (red accent)
    LAYOUT_SECTION = layouts[4]   # idx: 0=title

    section_counter = 0

    for idx, s in enumerate(slides_data):
        lay = s.get("layout", "content")
        img_bytes = images.get(idx)

        if lay == "title":
            sl = prs.slides.add_slide(LAYOUT_TITLE)
            _set_ph_text(sl, 0, s.get("title", ""), size=28, bold=True)
            _set_ph_text(sl, 1, s.get("subtitle", ""), size=16, color=MUTED)
            if img_bytes:
                # Try picture placeholders
                if not _insert_picture_ph(sl, 21, img_bytes):
                    _insert_picture_ph(sl, 22, img_bytes)

        elif lay == "section_number":
            sl = prs.slides.add_slide(LAYOUT_SECTION)
            section_counter += 1
            num = s.get("number", str(section_counter))
            ph = _ph(sl, 0)
            if ph:
                tf = ph.text_frame
                tf.clear()
                p = tf.paragraphs[0]
                r = p.add_run()
                r.text = num
                r.font.size = Pt(72)
                r.font.bold = True
                r.font.color.rgb = THL_RED
                r.font.name = FONT
                p2 = tf.add_paragraph()
                p2.space_before = Pt(12)
                r2 = p2.add_run()
                r2.text = s.get("title", "")
                r2.font.size = Pt(28)
                r2.font.bold = True
                r2.font.color.rgb = BLACK
                r2.font.name = FONT
                if s.get("subtitle"):
                    p3 = tf.add_paragraph()
                    p3.space_before = Pt(8)
                    r3 = p3.add_run()
                    r3.text = s["subtitle"]
                    r3.font.size = Pt(14)
                    r3.font.color.rgb = MUTED
                    r3.font.name = FONT

        elif lay == "statement":
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", ""), size=24, bold=True)
            _set_ph_text(sl, 1, s.get("body", ""), size=16, color=MUTED)

        elif lay == "icon_grid":
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", ""), size=22, bold=True)
            _clear_ph(sl, 1)  # hide default content placeholder
            items = s.get("items", [])[:4]
            grid = [
                (Inches(0.5), Inches(1.8)),
                (Inches(5.2), Inches(1.8)),
                (Inches(0.5), Inches(4.2)),
                (Inches(5.2), Inches(4.2)),
            ]
            for i, item in enumerate(items[:4]):
                gx, gy = grid[i]
                _txt(sl, gx, gy, Inches(0.3), Inches(0.3),
                     "\u2022", size=20, bold=True, color=THL_RED)
                _txt(sl, gx + Inches(0.4), gy, Inches(4), Inches(0.4),
                     item.get("title", ""), size=14, bold=True, color=BLACK)
                _txt(sl, gx + Inches(0.4), gy + Inches(0.5), Inches(4), Inches(1.3),
                     item.get("body", ""), size=11, color=MUTED)

        elif lay == "comparison":
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", ""), size=22, bold=True)
            _clear_ph(sl, 1)
            _box(sl, Inches(0.3), Inches(1.7), Inches(4.5), Inches(4.5), LIGHT_GRAY)
            if s.get("left_title"):
                _txt(sl, Inches(0.6), Inches(1.9), Inches(4), Inches(0.4),
                     s["left_title"], size=14, bold=True, color=BRAND_BLUE)
            _bullets(sl, Inches(0.6), Inches(2.5), Inches(3.9), Inches(3.2),
                     s.get("left_bullets", []), size=12, color=BLACK)
            _box(sl, Inches(5.2), Inches(1.7), Inches(4.5), Inches(4.5), LIGHT_BLUE)
            if s.get("right_title"):
                _txt(sl, Inches(5.5), Inches(1.9), Inches(4), Inches(0.4),
                     s["right_title"], size=14, bold=True, color=BRAND_BLUE)
            _bullets(sl, Inches(5.5), Inches(2.5), Inches(3.9), Inches(3.2),
                     s.get("right_bullets", []), size=12, color=BLACK)

        elif lay == "quote":
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", ""), size=20, bold=True)
            _clear_ph(sl, 1)
            _box(sl, Inches(0.8), Inches(1.8), Inches(8.4), Inches(2), LIGHT_GRAY)
            _txt(sl, Inches(1.2), Inches(2), Inches(7.6), Inches(1.6),
                 f"\u201E{s.get('quote', '')}\u201C", size=15, color=BLACK)
            if s.get("body"):
                _txt(sl, Inches(0.8), Inches(4.2), Inches(8.4), Inches(1.5),
                     s["body"], size=13, color=MUTED)

        elif lay == "summary":
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", "Zusammenfassung"), size=22, bold=True)
            _fill_ph_bullets(sl, 1, s.get("bullets", []), size=15)

        else:  # content (default)
            sl = prs.slides.add_slide(LAYOUT_MAIN)
            _set_ph_text(sl, 0, s.get("title", ""), size=22, bold=True)
            if img_bytes:
                # Narrow bullets + image right
                ph = _ph(sl, 1)
                if ph:
                    ph.width = Inches(5.5)
                _fill_ph_bullets(sl, 1, s.get("bullets", []), size=15)
                _img(sl, img_bytes, Inches(6.2), Inches(1.5), Inches(3.4), Inches(4.5))
            else:
                _fill_ph_bullets(sl, 1, s.get("bullets", []), size=16)

        if s.get("notes"):
            sl.notes_slide.notes_text_frame.text = s["notes"]

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
