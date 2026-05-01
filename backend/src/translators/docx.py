from io import BytesIO

from docx import Document
from loguru import logger

from src.services.translation import TranslationService
from src.utils.text import _RunRef, apply_translations, collect_paragraph_runs


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
    """Translate text in a DOCX file preserving layout - single batch DeepL call."""
    try:
        doc = Document(BytesIO(content))
        refs: list[_RunRef] = []

        seen_paragraphs = set()
        for para in _iter_docx_paragraphs_with_header_footer(doc):
            if id(para) in seen_paragraphs:
                continue
            seen_paragraphs.add(id(para))
            if para.text and para.text.strip():
                collect_paragraph_runs(para, refs)

        if refs:
            texts = [r.encoded for r in refs]
            translated = service.translate_batch(texts, source_lang, target_lang)
            apply_translations(refs, translated)

        output = BytesIO()
        doc.save(output)
        output.seek(0)
        return output.getvalue()

    except ValueError:
        raise
    except Exception as e:
        logger.exception("Error processing DOCX file")
        raise ValueError(f"Error processing DOCX file: {e}")
