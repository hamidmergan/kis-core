from io import BytesIO

from loguru import logger
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from src.services.translation import TranslationService
from src.utils.text import _RunRef, apply_translations, collect_paragraph_runs


def _iter_pptx_paragraphs(shape):
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            yield paragraph
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    yield paragraph
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            yield from _iter_pptx_paragraphs(subshape)


def translate_pptx(
    content: bytes, source_lang: str, target_lang: str, service: TranslationService
) -> bytes:
    """Translate text in a PPTX file preserving layout - single batch DeepL call."""
    try:
        presentation = Presentation(BytesIO(content))
        refs: list[_RunRef] = []

        # Normal slide shapes
        for slide in presentation.slides:
            for shape in slide.shapes:
                for para in _iter_pptx_paragraphs(shape):
                    if para.text and para.text.strip():
                        collect_paragraph_runs(para, refs)

            # Speaker notes
            if slide.has_notes_slide:
                for shape in slide.notes_slide.shapes:
                    for para in _iter_pptx_paragraphs(shape):
                        if para.text and para.text.strip():
                            collect_paragraph_runs(para, refs)

        # Slide masters + layouts
        for slide_master in presentation.slide_masters:
            for shape in slide_master.shapes:
                for para in _iter_pptx_paragraphs(shape):
                    if para.text and para.text.strip():
                        collect_paragraph_runs(para, refs)
            for layout in slide_master.slide_layouts:
                for shape in layout.shapes:
                    for para in _iter_pptx_paragraphs(shape):
                        if para.text and para.text.strip():
                            collect_paragraph_runs(para, refs)

        if refs:
            texts = [r.encoded for r in refs]
            translated = service.translate_batch(texts, source_lang, target_lang)
            apply_translations(refs, translated)

        output = BytesIO()
        presentation.save(output)
        output.seek(0)
        return output.getvalue()

    except ValueError:
        raise
    except Exception as e:
        logger.exception("Error processing PPTX file")
        raise ValueError(f"Error processing PPTX file: {e}")
