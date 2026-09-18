"""Turns the summary tool's markdown result into a Word document, no other side effects."""

import io
import re

from docx import Document
from docx.document import Document as DocumentType
from docx.text.paragraph import Paragraph

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^( *)[-*]\s+(.*)$")
_NUMBER_RE = re.compile(r"^ *\d+\.\s+(.*)$")
_BOLD_SPLIT_RE = re.compile(r"(\*\*.+?\*\*)")
_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")

_BULLET_STYLES = ["List Bullet", "List Bullet 2", "List Bullet 3"]


def markdown_to_docx(text: str) -> bytes:
    """Render headings, nested bullets, numbered lists, tables and bold text as a real Word document."""
    document = Document()
    lines = text.splitlines()
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if "|" in line and i + 1 < total and _is_table_separator(lines[i + 1]):
            i = _add_table(document, lines, i)
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            _add_heading(document, level=len(heading.group(1)), text=heading.group(2).strip())
            i += 1
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            level = min(len(bullet.group(1)) // 4, len(_BULLET_STYLES) - 1)
            paragraph = document.add_paragraph(style=_BULLET_STYLES[level])
            _add_runs(paragraph, bullet.group(2).strip())
            i += 1
            continue
        numbered = _NUMBER_RE.match(line)
        if numbered:
            paragraph = document.add_paragraph(style="List Number")
            _add_runs(paragraph, numbered.group(1).strip())
            i += 1
            continue
        paragraph = document.add_paragraph()
        _add_runs(paragraph, line.strip())
        i += 1

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _add_heading(document: DocumentType, level: int, text: str) -> None:
    paragraph = document.add_heading(level=level)
    _add_runs(paragraph, text)


def _add_runs(paragraph: Paragraph, text: str) -> None:
    """Split *fett* markers into bold and plain runs, several per line allowed."""
    for part in _BOLD_SPLIT_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _add_table(document: DocumentType, lines: list[str], start: int) -> int:
    """Consume the header, separator and data rows starting at *start*, return the index after them."""
    header = _table_cells(lines[start])
    rows: list[list[str]] = []
    i = start + 2
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        rows.append(_table_cells(lines[i]))
        i += 1

    table = document.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Table Grid"
    for col, cell_text in enumerate(header):
        cell_paragraph = table.rows[0].cells[col].paragraphs[0]
        _add_runs(cell_paragraph, cell_text)
        for run in cell_paragraph.runs:
            run.bold = True
    for r, row in enumerate(rows, start=1):
        for col, cell_text in enumerate(row):
            if col >= len(header):
                continue
            _add_runs(table.rows[r].cells[col].paragraphs[0], cell_text)
    return i
