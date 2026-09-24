"""Builds the deck from the template: one slide per entry, only placeholders the layout has."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO

from loguru import logger
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

from src.features.praesentation import vorlage
from src.features.praesentation.schemas import Body, Slide
from src.features.praesentation.teilung import zeilen
from src.features.praesentation.vorlage import EMU_PER_PT, Analyse, Feld, Layout
from src.services.screencast.pptx import _load_font

_CHART = {"bar": XL_CHART_TYPE.COLUMN_CLUSTERED, "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE}
_OHNE_RANDTEXT = ("deckblatt", "abschluss")
# The AI notice in the bottom right corner: a fixed size, in dark grey.
HINWEIS_PT = 10.0
HINWEIS_GRAU = RGBColor(0x59, 0x59, 0x59)
_HINWEIS_BREITE = Emu(3 * 914400)
_HINWEIS_HOEHE = Emu(int(0.25 * 914400))
_HINWEIS_RAND = Emu(int(0.3 * 914400))
BILD_QUALITAET = 90
# The line factor the splitter measures with, kept in step with it.
_ZEILE = 1.2
# A heading may lose at most this much of its size, a longer title is the only cure below that.
_MIN_ANTEIL = 0.6


def bild_schluessel(slide_id: str, slot: int | str) -> str:
    return f"{slide_id}_{slot}"


def layout_index(a: Analyse, s: Slide, zaehler: dict[str, int]) -> int:
    """The stored layout of a slide, or the next one of its role."""
    if s.layout is not None and any(l.index == s.layout for l in a.layouts):
        return s.layout
    return vorlage.layout_fuer(a, s.role, zaehler).index


def baue(vorlage_bytes: bytes, a: Analyse, slides: list[Slide], bilder: dict[str, bytes],
         titel: str, notizen: bool, hinweis: str = "", nummern: list[int] | None = None) -> bytes:
    """The deck, ``nummern`` gives each slide its number when only part of the deck is built."""
    prs = Presentation(BytesIO(vorlage_bytes))
    _leeren(prs)
    zaehler: dict[str, int] = {}
    for i, s in enumerate(slides):
        layout = a.layout(layout_index(a, s, zaehler))
        _folie(prs, layout, s, bilder, titel, notizen, hinweis, a.typeface)
        if s.role != "deckblatt":
            _foliennummer(prs.slides[-1], nummern[i] if nummern else i + 1)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


def _leeren(prs) -> None:
    liste = prs.slides._sldIdLst
    for sld in list(liste):
        prs.part.drop_rel(sld.rId)
        liste.remove(sld)


def _ph(slide, idx: int):
    try:
        return slide.placeholders[idx]
    except KeyError:
        return None


def _entferne(shape) -> None:
    el = shape._element
    el.getparent().remove(el)


def _setze_text(ph, absaetze: list[str]) -> None:
    tf = ph.text_frame
    tf.text = absaetze[0] if absaetze else ""
    for z in absaetze[1:]:
        p = tf.add_paragraph()
        p.text = z
        p.level = 0


def _passende_groesse(text: str, feld: Feld, typeface: str) -> float | None:
    """The largest size up to the template's at which the text still fits, None when it already does.

    The template sizes its title for the words it expects. A longer one wraps into the
    line below, and on a cover that line is the subtitle.
    """
    if not text or not typeface or feld.size_pt <= 0:
        return None
    breite = (feld.width - feld.inset_h) / EMU_PER_PT
    hoehe = (feld.height - feld.inset_v) / EMU_PER_PT
    if breite <= 0 or hoehe <= 0:
        return None
    # Caps and bold are what the layout really renders, the plain string measures far too narrow.
    gemessen = text.upper() if feld.caps else text
    name = f"{typeface}:bold" if feld.bold else typeface
    untergrenze = max(8.0, feld.size_pt * _MIN_ANTEIL)
    groesse = feld.size_pt
    while True:
        try:
            font = _load_font(name, round(groesse))
        except OSError as e:
            logger.warning("Schriftmass übersprungen, {} nicht ladbar: {}", name, e)
            return None
        if zeilen([gemessen], font, breite) * groesse * _ZEILE <= hoehe or groesse <= untergrenze:
            break
        groesse = max(untergrenze, groesse - 1.0)
    return None if groesse >= feld.size_pt else groesse


def _setze_kopf(ph, feld: Feld, text: str, typeface: str) -> None:
    """A heading, shrunk just enough that it never reaches what sits below it."""
    _setze_text(ph, [text])
    groesse = _passende_groesse(text, feld, typeface)
    if groesse is None:
        return
    for absatz in ph.text_frame.paragraphs:
        for lauf in absatz.runs:
            lauf.font.size = Pt(groesse)


def _zuschnitt(data: bytes, aspect: float) -> BytesIO:
    """Centre crop to the field's aspect, so a banner field never squeezes a square picture."""
    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    if w / h > aspect:
        nw = max(1, int(h * aspect))
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = max(1, int(w / aspect))
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    out = BytesIO()
    # JPEG, not PNG: eight painterly illustrations as PNG push a deck past 25 MB for no visible gain.
    im.save(out, format="JPEG", quality=BILD_QUALITAET, optimize=True, progressive=True)
    out.seek(0)
    return out


def _folie(prs, layout: Layout, s: Slide, bilder: dict[str, bytes], titel: str, notizen: bool,
           hinweis: str = "", typeface: str = "") -> None:
    slide = prs.slides.add_slide(prs.slide_masters[0].slide_layouts[layout.index])
    benutzt: set[int] = set()

    ueber = layout.der_art("ueberschrift")
    if ueber and s.title and (ph := _ph(slide, ueber[0].idx)) is not None:
        _setze_kopf(ph, ueber[0], s.title, typeface)
        benutzt.add(ueber[0].idx)

    zwischen = layout.der_art("zwischentitel")
    if s.role in _OHNE_RANDTEXT:
        if zwischen and s.subtitle and (ph := _ph(slide, zwischen[0].idx)) is not None:
            _setze_kopf(ph, zwischen[0], s.subtitle, typeface)
            benutzt.add(zwischen[0].idx)
    else:
        for feld, col in zip(zwischen, s.columns):
            if col.heading and (ph := _ph(slide, feld.idx)) is not None:
                _setze_kopf(ph, feld, col.heading, typeface)
                benutzt.add(feld.idx)

    flies = layout.der_art("fliesstext")
    if len(flies) == 1 and s.body is not None:
        if _body(slide, flies[0], s.body, bilder.get(bild_schluessel(s.id, "body"))):
            benutzt.add(flies[0].idx)
    elif len(flies) > 1:
        for feld, col in zip(flies, s.columns):
            if col.items and (ph := _ph(slide, feld.idx)) is not None:
                _setze_text(ph, col.items)
                benutzt.add(feld.idx)

    for k, feld in enumerate(layout.der_art("bild")):
        data = bilder.get(bild_schluessel(s.id, k))
        ph = _ph(slide, feld.idx)
        if data and ph is not None:
            ph.insert_picture(_zuschnitt(data, feld.aspect))
            benutzt.add(feld.idx)

    rand = sorted(layout.der_art("randtext"), key=lambda f: f.top)
    if rand and s.role not in _OHNE_RANDTEXT and (ph := _ph(slide, rand[0].idx)) is not None:
        _setze_text(ph, [titel])
        benutzt.add(rand[0].idx)

    for ph in list(slide.placeholders):
        if ph.placeholder_format.idx not in benutzt:
            _entferne(ph)

    if hinweis:
        _hinweis(prs, slide, hinweis, typeface)

    if notizen and s.notes:
        slide.notes_slide.notes_text_frame.text = s.notes


def _foliennummer(slide, nummer: int) -> None:
    """The layout's slide number field, copied onto the slide, since python-pptx leaves it out."""
    vorbild = next((ph for ph in slide.slide_layout.placeholders
                    if ph.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER), None)
    if vorbild is None:
        return
    el = deepcopy(vorbild._element)
    el.nvSpPr.cNvPr.id = max((sh.shape_id for sh in slide.shapes), default=1) + 1
    for t in el.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
        t.text = str(nummer)
    slide.shapes._spTree.append(el)


def _hinweis(prs, slide, text: str, typeface: str) -> None:
    """A right-aligned note in the bottom corner, its own box so no layout has to offer a field for it."""
    links = Emu(prs.slide_width - _HINWEIS_BREITE - _HINWEIS_RAND)
    oben = Emu(prs.slide_height - _HINWEIS_HOEHE - _HINWEIS_RAND)
    kasten = slide.shapes.add_textbox(links, oben, _HINWEIS_BREITE, _HINWEIS_HOEHE)
    rahmen = kasten.text_frame
    rahmen.word_wrap = False
    rahmen.margin_left = rahmen.margin_right = rahmen.margin_top = rahmen.margin_bottom = 0
    absatz = rahmen.paragraphs[0]
    absatz.alignment = PP_ALIGN.RIGHT
    lauf = absatz.add_run()
    lauf.text = text
    lauf.font.size = Pt(HINWEIS_PT)
    lauf.font.color.rgb = HINWEIS_GRAU
    if typeface:
        lauf.font.name = typeface


def _body(slide, feld: Feld, body: Body, bild: bytes | None) -> bool:
    """Fills the content field, True only when the placeholder itself holds the text."""
    ph = _ph(slide, feld.idx)
    if ph is None:
        return False
    if body.kind == "table" and body.rows:
        spalten = max([len(body.header)] + [len(r) for r in body.rows])
        zeilen = len(body.rows) + (1 if body.header else 0)
        tabelle = slide.shapes.add_table(zeilen, spalten, feld.left, feld.top, feld.width, feld.height).table
        start = 0
        if body.header:
            for c, kopf in enumerate(body.header[:spalten]):
                tabelle.cell(0, c).text = kopf
            start = 1
        for r, zeile in enumerate(body.rows):
            for c, wert in enumerate(zeile[:spalten]):
                tabelle.cell(start + r, c).text = wert
        return False
    if body.kind == "chart" and body.categories and body.series:
        daten = CategoryChartData()
        daten.categories = body.categories
        for serie in body.series:
            daten.add_series(serie.name or " ", serie.values)
        slide.shapes.add_chart(_CHART.get(body.chart_type, _CHART["bar"]),
                               feld.left, feld.top, feld.width, feld.height, daten)
        return False
    if body.kind == "image" and bild:
        slide.shapes.add_picture(_zuschnitt(bild, feld.aspect), feld.left, feld.top, feld.width, feld.height)
        return False
    if body.items:
        _setze_text(ph, body.items)
        return True
    return False
