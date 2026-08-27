"""PPTX fixtures for the screencast tests, with hand-written SmartArt."""

import zipfile
from io import BytesIO

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

SMARTART_TEXTS = ("Kategorien für Publikumsfragen", "Verständnisfrage", "Vertiefungsfrage")
CHART_TITLE = "Umsatz pro Quartal"
CHART_CATEGORIES = ("Erstes Quartal", "Zweites Quartal")

_DATA1 = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<dgm:ptLst>
<dgm:pt modelId="{{1}}" type="doc"/>
{points}
</dgm:ptLst>
<dgm:cxnLst/><dgm:bg/><dgm:whole/>
</dgm:dataModel>"""

_POINT = (
    '<dgm:pt modelId="{{{i}}}"><dgm:t><a:bodyPr/><a:lstStyle/>'
    '<a:p><a:r><a:t>{text}</a:t></a:r></a:p></dgm:t></dgm:pt>'
)

_GRAPHIC_FRAME = """<p:graphicFrame
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram">
<p:nvGraphicFramePr><p:cNvPr id="99" name="Diagramm 1"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
<p:xfrm><a:off x="1000000" y="1000000"/><a:ext cx="4000000" cy="3000000"/></p:xfrm>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/diagram">
<dgm:relIds r:dm="rId101" r:lo="rId102" r:qs="rId103" r:cs="rId104"/>
</a:graphicData></a:graphic></p:graphicFrame>"""

_DIAGRAM_RELS = (
    '<Relationship Id="rId101" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData" Target="../diagrams/data1.xml"/>'
    '<Relationship Id="rId102" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout" Target="../diagrams/layout1.xml"/>'
    '<Relationship Id="rId103" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramQuickStyle" Target="../diagrams/quickStyle1.xml"/>'
    '<Relationship Id="rId104" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramColors" Target="../diagrams/colors1.xml"/>'
)

_DIAGRAM_CONTENT_TYPES = (
    '<Override PartName="/ppt/diagrams/data1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"/>'
    '<Override PartName="/ppt/diagrams/layout1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"/>'
    '<Override PartName="/ppt/diagrams/quickStyle1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramStyle+xml"/>'
    '<Override PartName="/ppt/diagrams/colors1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramColors+xml"/>'
)

_STUB_PARTS = {
    "ppt/diagrams/layout1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<dgm:layoutDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"/>',
    "ppt/diagrams/quickStyle1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<dgm:styleDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"/>',
    "ppt/diagrams/colors1.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<dgm:colorsDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram"/>',
}


def _blank_deck(slide_texts: list[str]) -> Presentation:
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for text in slide_texts:
        slide = prs.slides.add_slide(blank)
        if text:
            box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
            box.text_frame.text = text
    return prs


def _to_bytes(prs: Presentation) -> bytes:
    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()


def smartart_pptx(slide_text: str = "Normaler Text auf Folie 1") -> bytes:
    """Two slides: slide 1 with a normal text box, slide 2 with real SmartArt."""
    raw = _to_bytes(_blank_deck([slide_text, ""]))

    points = "\n".join(
        _POINT.format(i=i + 2, text=text) for i, text in enumerate(SMARTART_TEXTS)
    )
    data1 = _DATA1.format(points=points)

    out = BytesIO()
    with zipfile.ZipFile(BytesIO(raw)) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.decode().replace("</Types>", _DIAGRAM_CONTENT_TYPES + "</Types>").encode()
            elif item.filename == "ppt/slides/slide2.xml":
                data = data.decode().replace("</p:spTree>", _GRAPHIC_FRAME + "</p:spTree>").encode()
            elif item.filename == "ppt/slides/_rels/slide2.xml.rels":
                data = data.decode().replace("</Relationships>", _DIAGRAM_RELS + "</Relationships>").encode()
            zout.writestr(item, data)
        for name, content in _STUB_PARTS.items():
            zout.writestr(name, content)
        zout.writestr("ppt/diagrams/data1.xml", data1)
    return out.getvalue()


_FALLBACK_GROUP = """<p:grpSp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<p:nvGrpSpPr><p:cNvPr id="200" name="Fallback"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
<p:sp><p:nvSpPr><p:cNvPr id="201" name="t"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:grpSp>"""


def smartart_with_fallback_pptx() -> bytes:
    """SmartArt packaged the way PowerPoint really writes it."""
    data = smartart_pptx()
    with zipfile.ZipFile(BytesIO(data)) as zin:
        slide2 = zin.read("ppt/slides/slide2.xml").decode()
        start = slide2.index("<p:graphicFrame")
        end = slide2.index("</p:graphicFrame>") + len("</p:graphicFrame>")
        frame = slide2[start:end]
        wrapped = (
            '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
            '<mc:Choice xmlns:a14="urn:a14" Requires="a14">' + frame + "</mc:Choice>"
            "<mc:Fallback>" + _FALLBACK_GROUP.format(text=SMARTART_TEXTS[0]) + "</mc:Fallback>"
            "</mc:AlternateContent>"
        )
        new_slide = (slide2[:start] + wrapped + slide2[end:]).encode()

        out = BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                payload = new_slide if item.filename == "ppt/slides/slide2.xml" else zin.read(item.filename)
                zout.writestr(item, payload)
    return out.getvalue()


def chart_pptx() -> bytes:
    """One slide with a bar chart, title and categories are text in the chart part."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    data = CategoryChartData()
    data.categories = list(CHART_CATEGORIES)
    data.add_series("Reihe A", (19.2, 21.4))
    frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1), Inches(6), Inches(4), data
    )
    chart = frame.chart
    chart.has_title = True
    chart.chart_title.text_frame.text = CHART_TITLE
    return _to_bytes(prs)


def hidden_slide_pptx() -> bytes:
    """Three slides, the middle one is hidden (show="0")."""
    prs = _blank_deck(["Folie A", "Folie B versteckt", "Folie C"])
    prs.slides[1]._element.set("show", "0")
    return _to_bytes(prs)


def multi_run_paragraph_pptx() -> bytes:
    """One paragraph PowerPoint has split into several runs."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
    para = box.text_frame.paragraphs[0]
    for chunk in ("Der Vortrag ", "beginnt ", "um neun Uhr"):
        para.add_run().text = chunk
    return _to_bytes(prs)
