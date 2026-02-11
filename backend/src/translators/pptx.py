from io import BytesIO

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from src.services.translation import TranslationService
from src.utils.text import translate_paragraph_preserve_runs


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
    """Translate text in a PPTX file preserving layout."""
    try:
        presentation = Presentation(BytesIO(content))
        any_text = False

        # 1. Normal slide shapes
        for slide in presentation.slides:
            for shape in slide.shapes:
                for para in _iter_pptx_paragraphs(shape):
                    raw_text = para.text
                    if not raw_text or not raw_text.strip():
                        continue
                    any_text = True
                    try:
                        translate_paragraph_preserve_runs(para, source_lang, target_lang, service)
                    except Exception as e:
                        raise ValueError(f"Fehler beim Übersetzen von PPTX-Absatz: {str(e)}")

            # 2. Speaker notes
            if slide.has_notes_slide:
                notes_slide = slide.notes_slide
                for shape in notes_slide.shapes:
                    for para in _iter_pptx_paragraphs(shape):
                        raw_text = para.text
                        if not raw_text or not raw_text.strip():
                            continue
                        any_text = True
                        try:
                            translate_paragraph_preserve_runs(
                                para, source_lang, target_lang, service
                            )
                        except Exception:
                            pass

        # 3. Slide masters
        for slide_master in presentation.slide_masters:
            for shape in slide_master.shapes:
                for para in _iter_pptx_paragraphs(shape):
                    raw_text = para.text
                    if not raw_text or not raw_text.strip():
                        continue
                    any_text = True
                    try:
                        translate_paragraph_preserve_runs(para, source_lang, target_lang, service)
                    except Exception:
                        pass

            for layout in slide_master.slide_layouts:
                for shape in layout.shapes:
                    for para in _iter_pptx_paragraphs(shape):
                        raw_text = para.text
                        if not raw_text or not raw_text.strip():
                            continue
                        any_text = True
                        try:
                            translate_paragraph_preserve_runs(
                                para, source_lang, target_lang, service
                            )
                        except Exception:
                            pass

        output = BytesIO()
        presentation.save(output)
        if any_text:
            output.seek(0)
        return output.getvalue()

    except ValueError:
        raise
    except Exception as e:
        import traceback
        raise ValueError(
            f"Fehler beim Verarbeiten der PPTX-Datei: {str(e)}\n{traceback.format_exc()}"
        )
