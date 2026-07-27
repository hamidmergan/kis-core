"""Gemeinsamer Textzugriff auf PPTX-Dateien.

Extraktion (Skriptquelle) und Übersetzung müssen exakt dieselben Textstellen
sehen. Solange beide ihre eigene Shape-Schleife hatten, sind sie auseinander
gelaufen: SmartArt und Diagramme lagen in keiner der beiden.

Der Grund ist der Dateiaufbau. Eine Folie enthält für SmartArt nur einen
<p:graphicFrame> mit <dgm:relIds>, der Text steht in ppt/diagrams/dataN.xml.
Bei Diagrammen steht der sichtbare Text in ppt/charts/chartN.xml. Wer nur das
Folien-XML durchsucht, findet beides nicht.

Die Funktionen hier liefern beides an einer Stelle:
  iter_shape_paragraphs   Absätze aus Textrahmen, Tabellen und Gruppen
  iter_linked_text_nodes  Textknoten aus SmartArt- und Diagramm-Teilen
Beide Rückgaben haben ein les- und schreibbares .text, damit Extraktion und
Übersetzung denselben Weg nehmen.
"""

from collections.abc import Iterator
from typing import Any

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE

_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_A_T = f"{{{_A_NS}}}t"
_C_V = f"{{{_C_NS}}}v"
_C_STR_CACHE = f"{{{_C_NS}}}strCache"

_DIAGRAM_DATA_RELTYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
)

# Der geparste Diagrammbaum wird am Part zwischengespeichert, damit mehrere
# Durchläufe (lesen, dann schreiben) dieselben Elemente sehen.
_TREE_ATTR = "_kis_diagram_tree"


# ── Folien ──────────────────────────────────────────────────────────────────

def is_hidden_slide(slide) -> bool:
    """True, wenn die Folie in PowerPoint ausgeblendet ist (show="0")."""
    return slide._element.get("show") == "0"


def iter_visible_slides(presentation) -> Iterator[Any]:
    """Nur die Folien, die LibreOffice auch exportiert.

    Ausgeblendete Folien landen nicht im PDF. Zählt man sie beim Text mit,
    bekommt ab der ersten versteckten Folie jedes Bild das Skript der falschen
    Folie und das Ende des Videos fehlt.
    """
    for slide in presentation.slides:
        if not is_hidden_slide(slide):
            yield slide


# ── Absätze in Shapes ───────────────────────────────────────────────────────

def iter_shape_paragraphs(shape) -> Iterator[Any]:
    """Alle Absätze einer Form, inklusive Tabellenzellen und verschachtelter Gruppen."""
    if shape.has_text_frame:
        yield from shape.text_frame.paragraphs
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                yield from cell.text_frame.paragraphs
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            yield from iter_shape_paragraphs(subshape)


def iter_slide_paragraphs(slide) -> Iterator[Any]:
    """Absätze aller Formen einer Folie."""
    for shape in slide.shapes:
        yield from iter_shape_paragraphs(shape)


# ── Text in verlinkten Teilen (SmartArt, Diagramme) ─────────────────────────

def _diagram_tree(part):
    tree = getattr(part, _TREE_ATTR, None)
    if tree is None:
        tree = etree.fromstring(part.blob)
        setattr(part, _TREE_ATTR, tree)
    return tree


def _iter_diagram_nodes(slide, touched_parts: set | None) -> Iterator[Any]:
    """<a:t>-Elemente aus dem Datenteil jedes SmartArt-Diagramms der Folie."""
    for rel in slide.part.rels.values():
        if rel.reltype != _DIAGRAM_DATA_RELTYPE or rel.is_external:
            continue
        part = rel.target_part
        try:
            tree = _diagram_tree(part)
        except etree.XMLSyntaxError:
            continue
        if touched_parts is not None:
            touched_parts.add(part)
        yield from tree.iter(_A_T)


def _iter_chart_nodes(shape) -> Iterator[Any]:
    """Sichtbarer Text eines Diagramms: Titel, Achsentitel, Reihen- und Kategorienamen.

    Zahlen bleiben außen vor. Die stehen ebenfalls in <c:v>, aber unter
    <c:numCache> statt <c:strCache>.
    """
    chart_element = shape.chart.part._element
    yield from chart_element.iter(_A_T)
    for value in chart_element.iter(_C_V):
        cache = value.getparent().getparent() if value.getparent() is not None else None
        if cache is not None and cache.tag == _C_STR_CACHE:
            yield value


def iter_linked_text_nodes(slide, touched_parts: set | None = None) -> Iterator[Any]:
    """Textknoten, die nicht im Folien-XML stehen: SmartArt und Diagramme.

    ``touched_parts`` sammelt die SmartArt-Teile, die danach über
    ``flush_diagram_parts`` zurückgeschrieben werden müssen. Beim reinen Lesen
    kann der Parameter weggelassen werden.
    """
    yield from _iter_diagram_nodes(slide, touched_parts)
    for shape in _iter_all_shapes(slide.shapes):
        if getattr(shape, "has_chart", False):
            yield from _iter_chart_nodes(shape)


def _iter_all_shapes(shapes) -> Iterator[Any]:
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_all_shapes(shape.shapes)


def flush_diagram_parts(touched_parts) -> None:
    """Geänderte SmartArt-Bäume zurück in die Datei schreiben.

    Die Diagrammteile sind für python-pptx unbekannte Teile und werden als
    reines Blob gehalten. Ohne dieses Zurückschreiben landen Änderungen am
    Baum nie in der gespeicherten PPTX.
    """
    for part in touched_parts:
        tree = getattr(part, _TREE_ATTR, None)
        if tree is None:
            continue
        part._blob = etree.tostring(
            tree, xml_declaration=True, encoding="UTF-8", standalone=True
        )
