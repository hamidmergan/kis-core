from io import BytesIO

from docx import Document

from src.services.translation import TranslationService
from src.utils.text import translate_paragraph_preserve_runs


def _iter_docx_paragraphs(container):
    for paragraph in getattr(container, "paragraphs", []):
        yield paragraph
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_docx_paragraphs(cell)


def _iter_docx_paragraphs_with_header_footer(doc):
    yield from _iter_docx_paragraphs(doc)
    for section in doc.sections:
        for header in (section.header, section.first_page_header, section.even_page_header):
            yield from _iter_docx_paragraphs(header)
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            yield from _iter_docx_paragraphs(footer)


def translate_docx(
    content: bytes, source_lang: str, target_lang: str, service: TranslationService
) -> bytes:
    """Translate text in a DOCX file preserving layout, formatting and structure."""
    try:
        doc = Document(BytesIO(content))

        any_text = False
        seen_paragraphs = set()
        for para in _iter_docx_paragraphs_with_header_footer(doc):
            if id(para) in seen_paragraphs:
                continue
            seen_paragraphs.add(id(para))
            text = para.text
            if not text or not text.strip():
                continue
            any_text = True
            try:
                translate_paragraph_preserve_runs(para, source_lang, target_lang, service)
            except Exception as e:
                raise ValueError(f"Fehler beim Übersetzen eines Absatzes: {str(e)}")

        output = BytesIO()
        doc.save(output)
        if any_text:
            output.seek(0)
        return output.getvalue()

    except ValueError:
        raise
    except Exception as e:
        import traceback
        raise ValueError(
            f"Fehler beim Verarbeiten der DOCX-Datei: {str(e)}\n{traceback.format_exc()}"
        )
