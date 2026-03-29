"""Generate the THL corporate PPTX template with styled slide master.

Creates a professional template with THL brand colors (#004261, #0E7490),
custom fonts, and decorative elements on each slide layout.

Layouts used by the presentation generator:
  0: Title Slide      — title + subtitle (dark bg)
  1: Title and Content — title + bullet list
  2: Section Header   — section divider (dark bg)
  3: Two Content      — title + 2 columns
  4: Comparison        — title + 2 labeled columns
  5: Title Only        — title + free space (for image slides)
  8: Picture w Caption — title + picture + caption text

Usage: docker exec kis-backend python -m src.templates.create_template
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
import copy
import os

# ── THL Brand ──
BRAND = RGBColor(0x00, 0x42, 0x61)
ACCENT = RGBColor(0x0E, 0x74, 0x90)
LIGHT_ACCENT = RGBColor(0x38, 0xBD, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x64, 0x74, 0x8B)
LIGHT_BG = RGBColor(0xF1, 0xF5, 0xF9)

FONT = "Calibri"
W = Inches(13.333)
H = Inches(7.5)


def _add_shape(slide_or_layout, shape_type, left, top, width, height, fill_color, opacity=None):
    """Add a shape to a slide or layout."""
    sp = slide_or_layout.shapes.add_shape(shape_type, left, top, width, height)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill_color
    sp.line.fill.background()
    if opacity is not None:
        ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        # Access the XML element for fill
        fill_elem = sp.fill._fill._element if hasattr(sp.fill._fill, '_element') else sp._element.find(f".//{{{ns}}}solidFill")
        if fill_elem is not None:
            for srgb in fill_elem.findall(f".//{{{ns}}}srgbClr"):
                alpha = etree.SubElement(srgb, f"{{{ns}}}alpha")
                alpha.set("val", str(int(opacity * 1000)))
    return sp


def _style_placeholder_font(ph, font_name=FONT, font_size=None, bold=None, color=None, align=None):
    """Style the default paragraph of a placeholder."""
    for p in ph.text_frame.paragraphs:
        if font_name:
            p.font.name = font_name
        if font_size:
            p.font.size = Pt(font_size)
        if bold is not None:
            p.font.bold = bold
        if color:
            p.font.color.rgb = color
        if align:
            p.alignment = align


def create_template():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H

    # ── Style each layout ──
    layouts = prs.slide_layouts

    # Layout 0: Title Slide — style placeholders
    title_layout = layouts[0]
    for ph in title_layout.placeholders:
        if ph.placeholder_format.idx == 0:  # Title
            _style_placeholder_font(ph, font_size=40, bold=True, color=WHITE,
                                    align=PP_ALIGN.LEFT)
        elif ph.placeholder_format.idx == 1:  # Subtitle
            _style_placeholder_font(ph, font_size=20, color=RGBColor(0x93, 0xC5, 0xFD),
                                    align=PP_ALIGN.LEFT)

    # Layout 1: Title and Content
    content_layout = layouts[1]
    for ph in content_layout.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=28, bold=True, color=BRAND)
        elif ph.placeholder_format.idx == 1:
            _style_placeholder_font(ph, font_size=18, color=DARK)

    # Layout 2: Section Header
    section_layout = layouts[2]
    for ph in section_layout.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=36, bold=True, color=WHITE,
                                    align=PP_ALIGN.CENTER)
        elif ph.placeholder_format.idx == 1:
            _style_placeholder_font(ph, font_size=16, color=RGBColor(0x93, 0xC5, 0xFD),
                                    align=PP_ALIGN.CENTER)

    # Layout 3: Two Content
    two_content = layouts[3]
    for ph in two_content.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=28, bold=True, color=BRAND)
        elif ph.placeholder_format.idx in (1, 2):
            _style_placeholder_font(ph, font_size=16, color=DARK)

    # Layout 4: Comparison
    comparison = layouts[4]
    for ph in comparison.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=28, bold=True, color=BRAND)
        elif ph.placeholder_format.idx in (1, 3):  # Column headers
            _style_placeholder_font(ph, font_size=16, bold=True, color=ACCENT)
        elif ph.placeholder_format.idx in (2, 4):  # Column content
            _style_placeholder_font(ph, font_size=15, color=DARK)

    # Layout 5: Title Only
    title_only = layouts[5]
    for ph in title_only.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=28, bold=True, color=BRAND)

    # Layout 8: Picture with Caption
    pic_layout = layouts[8]
    for ph in pic_layout.placeholders:
        if ph.placeholder_format.idx == 0:
            _style_placeholder_font(ph, font_size=24, bold=True, color=BRAND)
        elif ph.placeholder_format.idx == 2:
            _style_placeholder_font(ph, font_size=14, color=MUTED)

    # ── Create example slides to verify template ──

    # Slide 1: Title
    slide = prs.slides.add_slide(layouts[0])
    # Add dark background manually (layout bg doesn't always work)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, H, BRAND)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.06), LIGHT_ACCENT)
    _add_shape(slide, MSO_SHAPE.OVAL, Inches(10), Inches(-1), Inches(4), Inches(4), ACCENT, opacity=10)
    _add_shape(slide, MSO_SHAPE.OVAL, Inches(11.5), Inches(4), Inches(3), Inches(3), ACCENT, opacity=6)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, Inches(7.3), W, Inches(0.04), LIGHT_ACCENT)
    slide.placeholders[0].text = "Präsentationstitel"
    slide.placeholders[1].text = "Untertitel der Präsentation"
    # Bring placeholders to front
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 2: Content
    slide = prs.slides.add_slide(layouts[1])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.08), H, BRAND)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(0.08), 0, Inches(0.04), H, ACCENT)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(0.12), 0, Inches(13.2), Inches(1.2), LIGHT_BG)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.15), Inches(4), Inches(0.02), ACCENT)
    slide.placeholders[0].text = "Inhalt mit Aufzählung"
    tf = slide.placeholders[1].text_frame
    tf.text = "Erster Punkt der Präsentation"
    for text in ["Zweiter wichtiger Aspekt", "Dritter Punkt mit Details", "Vierter Punkt"]:
        p = tf.add_paragraph()
        p.text = text
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 3: Section Header
    slide = prs.slides.add_slide(layouts[2])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, H, BRAND)
    _add_shape(slide, MSO_SHAPE.OVAL, Inches(4), Inches(1), Inches(5.3), Inches(5.3), ACCENT, opacity=8)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(5.5), Inches(3.0), Inches(2.3), Inches(0.05), LIGHT_ACCENT)
    slide.placeholders[0].text = "Neuer Abschnitt"
    slide.placeholders[1].text = "Kurze Beschreibung des Abschnitts"
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 4: Two Content
    slide = prs.slides.add_slide(layouts[3])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.06), BRAND)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, Inches(0.06), W, Inches(0.02), ACCENT)
    slide.placeholders[0].text = "Zwei-Spalten-Folie"
    slide.placeholders[1].text_frame.text = "Linke Spalte Punkt 1"
    slide.placeholders[1].text_frame.add_paragraph().text = "Linke Spalte Punkt 2"
    slide.placeholders[2].text_frame.text = "Rechte Spalte Punkt 1"
    slide.placeholders[2].text_frame.add_paragraph().text = "Rechte Spalte Punkt 2"
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 5: Comparison
    slide = prs.slides.add_slide(layouts[4])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.06), BRAND)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, Inches(0.06), W, Inches(0.02), ACCENT)
    slide.placeholders[0].text = "Vergleich"
    slide.placeholders[1].text = "Kategorie A"
    slide.placeholders[2].text_frame.text = "Detail A1"
    slide.placeholders[2].text_frame.add_paragraph().text = "Detail A2"
    slide.placeholders[3].text = "Kategorie B"
    slide.placeholders[4].text_frame.text = "Detail B1"
    slide.placeholders[4].text_frame.add_paragraph().text = "Detail B2"
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 6: Title Only (for image slides)
    slide = prs.slides.add_slide(layouts[5])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.08), H, BRAND)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, Inches(0.08), 0, Inches(0.04), H, ACCENT)
    slide.placeholders[0].text = "Folie mit Bild"
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Slide 7: Summary (using Content layout with special styling)
    slide = prs.slides.add_slide(layouts[1])
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, H, ACCENT_BG)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.06), ACCENT)
    _add_shape(slide, MSO_SHAPE.RECTANGLE, 0, Inches(0.06), W, Inches(0.02), LIGHT_ACCENT)
    slide.placeholders[0].text = "Zusammenfassung"
    tf = slide.placeholders[1].text_frame
    tf.text = "Kernaussage 1"
    tf.add_paragraph().text = "Kernaussage 2"
    tf.add_paragraph().text = "Kernaussage 3"
    for ph in slide.placeholders:
        slide.shapes._spTree.append(ph._element)

    # Save
    out_path = os.path.join(os.path.dirname(__file__), "thl_template.pptx")
    prs.save(out_path)
    print(f"Template saved to: {out_path}")
    print(f"Total slides: {len(prs.slides)} (example slides for verification)")
    print("\nLayout mapping for generator:")
    print("  0 = Title Slide (dark bg, title + subtitle)")
    print("  1 = Content (accent bar, title + bullets)")
    print("  2 = Section Header (dark bg, centered)")
    print("  3 = Two Content (title + 2 columns)")
    print("  4 = Comparison (title + 2 labeled columns)")
    print("  5 = Title Only (for image + text slides)")
    print("  6 = Blank")
    print("  8 = Picture with Caption")


ACCENT_BG = RGBColor(0xF0, 0xF9, 0xFF)

if __name__ == "__main__":
    create_template()
