import os
import tempfile
from io import BytesIO
from pathlib import Path

from fpdf import FPDF
from loguru import logger
from pypdf import PdfReader

from src.services.translation import TranslationService


def translate_pdf(
    content: bytes, source_lang: str, target_lang: str, service: TranslationService
) -> bytes:
    """Extract text from PDF, translate, and rebuild as simple PDF."""
    try:
        reader = PdfReader(BytesIO(content))
        translated_pages = []
        any_text = False

        for page in reader.pages:
            text = page.extract_text() or ""
            stripped = text.strip()
            if stripped:
                any_text = True
                translated = service.translate_text(stripped, source_lang, target_lang)
            else:
                translated = ""
            translated_pages.append(translated)

        if not any_text:
            return content

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", size=12)

        for page_text in translated_pages:
            pdf.add_page()
            if page_text:
                safe_text = page_text.encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(0, 10, txt=safe_text)

        raw_pdf = pdf.output(dest="S")
        if isinstance(raw_pdf, str):
            return raw_pdf.encode("latin-1")
        return bytes(raw_pdf)

    except ValueError:
        raise
    except Exception as e:
        logger.exception("Error processing PDF file")
        raise ValueError(f"Error processing PDF file: {e}")


def translate_document_via_deepl(
    content: bytes,
    filename: str,
    source_lang: str,
    target_lang: str,
    service: TranslationService,
) -> bytes:
    """Use DeepL Document Translation API directly (PDF/DOCX/PPTX)."""
    translator = service.deepl_client.raw

    try:
        if hasattr(translator, "translate_document_from_bytes"):
            handle = translator.translate_document_from_bytes(
                content, filename, target_lang=target_lang, source_lang=source_lang,
            )
        else:
            suffix = Path(filename).suffix or ""
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_out:
                tmp_out_path = tmp_out.name
            try:
                result = translator.translate_document_from_filepath(
                    tmp_path, output_path=tmp_out_path,
                    target_lang=target_lang, source_lang=source_lang,
                )
                if hasattr(result, "document_id"):
                    translator.translate_document_wait(result)
                    translated_path = translator.translate_document_download(
                        result, tmp_out_path
                    )
                    if isinstance(translated_path, (bytes, bytearray)):
                        return bytes(translated_path)
                    tmp_out_path = translated_path if translated_path else tmp_out_path
                with open(tmp_out_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                try:
                    os.remove(tmp_out_path)
                except OSError:
                    pass

        translator.translate_document_wait(handle)
        result = translator.translate_document_download(handle)
        return result if isinstance(result, (bytes, bytearray)) else bytes(result)
    except Exception as e:
        logger.exception("DeepL document translation error for '{}'", filename)
        raise ValueError(f"DeepL document translation error: {e}")
