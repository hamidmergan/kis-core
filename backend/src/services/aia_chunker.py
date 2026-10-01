"""Document chunker for KI Tutor - extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

import re
import time

from src.services.text_pieces import (
    PIECE_CHARS,
    PIECE_OVERLAP,
    clean,
    split_text,
)

from loguru import logger


class PdfNoReadableTextError(ValueError):
    """Raised when a PDF has no readable text."""


class OcrFailedError(RuntimeError):
    """Raised when text recognition of a page fails for good."""

    def __init__(self, page_number: int):
        self.page_number = page_number
        super().__init__(f"OCR failed for page {page_number} after retries")


# How often a page is retried, deliberately kept small.
OCR_MAX_ATTEMPTS = 5

_TRANSIENT_OCR_MARKERS = (
    "429", "rate limit", "too many requests",
    "timeout", "timed out",
    "502", "503", "504", "bad gateway", "service unavailable", "gateway timeout",
)


def _is_transient_ocr_error(e: Exception) -> bool:
    """True for temporary errors that make a second attempt worthwhile."""
    msg = str(e).lower()
    return any(m in msg for m in _TRANSIENT_OCR_MARKERS)


def _ocr_image_with_retry(provider, png_bytes, page_number, *, attempts=OCR_MAX_ATTEMPTS, sleep=time.sleep):
    """Recognises a page, with growing waits on temporary errors."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return provider.ocr_image(png_bytes, "image/png")
        except Exception as e:
            last_exc = e
            if _is_transient_ocr_error(e) and attempt < attempts - 1:
                wait = min(2 ** attempt, 30)  # 1s, 2s, 4s, 8s, capped 30s
                logger.warning(
                    "OCR page {} transient error (attempt {}/{}), retrying in {}s: {}",
                    page_number, attempt + 1, attempts, wait, e,
                )
                sleep(wait)
                continue
            break
    # The cause belongs in the log, otherwise a wrong key looks like a bad page.
    logger.warning("OCR page {} failed: {}", page_number, last_exc)
    raise OcrFailedError(page_number) from last_exc


# How many pages may fail before text recognition is switched off entirely.
OCR_MAX_FAILED_PAGES = 2


class _OcrRun:
    """Bookkeeping of text recognition for a document, none of it raises."""

    def __init__(self, provider, *, sleep=time.sleep):
        self._provider = provider
        self._sleep = sleep
        self._failed = 0
        self._given_up = False
        self.done = 0
        self.open: list[int] = []

    def wants(self, page_number: int) -> bool:
        """True when this page should really be rendered and sent."""
        if self._provider is None or self._given_up:
            self.open.append(page_number)
            return False
        return True

    def mark_open(self, page_number: int) -> None:
        """Books a page as open without blaming text recognition."""
        self.open.append(page_number)

    def ocr_page(self, png_bytes: bytes, page_number: int) -> str:
        """Recognise one page. Returns "" when it did not come through."""
        try:
            text = _ocr_image_with_retry(
                self._provider, png_bytes, page_number, sleep=self._sleep
            )
        except OcrFailedError:
            self._failed += 1
            self.open.append(page_number)
            if self._failed >= OCR_MAX_FAILED_PAGES:
                self._given_up = True
                logger.warning(
                    "OCR: {} page(s) failed, switching OCR off for the rest of this "
                    "document (the source stays usable, open pages can be caught up later)",
                    self._failed,
                )
            return ""
        self.done += 1
        return text

    def report(self) -> dict | None:
        if not self.done and not self.open:
            return None
        return {
            "enabled": self._provider is not None,
            "done": self.done,
            "open": self.open,
        }




# This much text of its own a bullet group needs to be indexed alone.
SLIDE_GROUP_MIN_CHARS = 120


def extract_chunks(
    file_path: str,
    file_type: str,
    progress_cb=None,
    ocr_report: dict | None = None,
) -> list[dict]:
    """Gets the text sections out of a file, with the page number."""
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(file_path, PIECE_CHARS, PIECE_OVERLAP, progress_cb, ocr_report)
    if ft == "docx":
        return _extract_docx(file_path, PIECE_CHARS)
    if ft == "pptx":
        return _extract_pptx(file_path, PIECE_CHARS, PIECE_OVERLAP)
    if ft in ("txt", "md"):
        return _extract_text(file_path, PIECE_CHARS, PIECE_OVERLAP)
    if ft in ("mp3", "mp4", "wav", "flac", "m4a", "webm"):
        raise ValueError(
            "Audio/Video files must be transcribed first - use segments_to_chunks() instead."
        )
    raise ValueError(f"Unsupported file_type: {file_type!r}")




# ── Format-specific extractors ────────────────────────────────────────────────

# From this image share on text recognition runs, small logos do not trigger it.
_OCR_IMAGE_COVERAGE_THRESHOLD = 0.20

# Resolution of the page image for image recognition, measured instead of guessed.
_OCR_RENDER_DPI = 150


def _render_ocr_png(page, page_number: int) -> bytes | None:
    """Page image for image recognition, or None when rendering fails."""
    import io as _io
    try:
        pil = page.render(scale=_OCR_RENDER_DPI / 72).to_pil()
        buf = _io.BytesIO()
        pil.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning("OCR page {}: render failed, skipping: {}", page_number, e)
        return None


def _bitmap_coverage(page) -> float:
    """Return the fraction of page area covered by raster image objects."""
    import pypdfium2.raw as pdfium_c
    page_w = page.get_width()
    page_h = page.get_height()
    page_area = page_w * page_h
    if page_area <= 0:
        return 0.0
    total = 0.0
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        try:
            left, bottom, right, top = obj.get_bounds()
        except Exception:
            continue
        w = max(0.0, right - left)
        h = max(0.0, top - bottom)
        total += w * h
    return min(total / page_area, 1.0)


def _extract_pdf(
    file_path: str,
    chunk_size: int,
    overlap: int,
    progress_cb=None,
    ocr_report: dict | None = None,
) -> list[dict]:
    import pypdfium2 as pdfium
    from src.services.pdf_layout import (
        line_boxes,
        boilerplate_keys, is_boilerplate, merge_rows, slide_groups, strip_boilerplate_text,
    )
    chunks: list[dict] = []
    # Collect all pages first, then cut, the header only shows in the whole.
    page_texts: list[str] = []
    page_lines: list[list] = []
    doc = pdfium.PdfDocument(file_path)
    total_pages = len(doc)

    # The text recognition provider is fetched on demand, None means skipped.
    ocr_run: _OcrRun | None = None

    if progress_cb:
        progress_cb("parsing", None, None)

    for page_num in range(total_pages):
        page = doc[page_num]
        textpage = page.get_textpage()
        raw_text = textpage.get_text_range() or ""
        text = clean(raw_text).strip()

        # Only pages that are mostly image go into text recognition.
        coverage = _bitmap_coverage(page)
        should_ocr = coverage >= _OCR_IMAGE_COVERAGE_THRESHOLD

        # The provider is only resolved at the first candidate page.
        if should_ocr and ocr_run is None:
            try:
                from src.services.aia_ocr import get_ocr_provider
                provider = get_ocr_provider()
            except Exception as e:
                logger.warning("OCR provider lookup failed: {}", e)
                provider = None
            ocr_run = _OcrRun(provider)

        # The log reports whether text really came back, not just the pre-check.
        ocr_tried = should_ocr and ocr_run.wants(page_num + 1)
        ocr_merged = False

        if ocr_tried:
            if progress_cb:
                progress_cb("ocr", page_num + 1, total_pages)
            png_bytes = _render_ocr_png(page, page_num + 1)

            if png_bytes is None:
                ocr_run.mark_open(page_num + 1)
            else:
                # A page that did not get through keeps its text layer and counts as open.
                ocr_text = clean(ocr_run.ocr_page(png_bytes, page_num + 1)).strip()
                if ocr_text:
                    ocr_merged = True
                    logger.info(
                        "PDF page {}: OCR extracted {} chars (text-layer had {})",
                        page_num + 1, len(ocr_text), len(text),
                    )
                    # Merge text-layer remnants + OCR output; OCR wins if empty layer
                    text = (text + "\n" + ocr_text).strip() if text else ocr_text

        logger.info(
            "PDF page {}: text={} chars, image_coverage={:.1%}, ocr_wanted={}, ocr_ran={}",
            page_num + 1, len(text), coverage, should_ocr, ocr_merged,
        )

        # The position is only read from the text layer, recognised pages take the simple path.
        page_lines.append([] if ocr_merged else line_boxes(textpage))
        page_texts.append(text)
        textpage.close()
        page.close()
    doc.close()

    # A slide with bullets is cut per group, otherwise the whole page path stays.
    boiler = boilerplate_keys(page_lines, page_texts)
    n_grouped = 0
    for i, (lines, text) in enumerate(zip(page_lines, page_texts)):
        # Subtract the header from the raw boxes first, then form lines.
        kept = merge_rows([b for b in lines if not is_boilerplate(b.text, boiler)])
        groups = slide_groups(kept, min_chars=SLIDE_GROUP_MIN_CHARS) if kept else []
        if groups:
            n_grouped += 1
            parts = groups
        else:
            parts = [strip_boilerplate_text(text, boiler)]
        for part in parts:
            for sub in split_text(part, chunk_size, overlap):
                chunks.append({"page_number": i + 1, "content": sub})
    logger.info(
        "PDF chunking: {} page(s), {} cut by bullet group, {} boilerplate line(s) dropped → {} chunks",
        total_pages, n_grouped, len(boiler), len(chunks),
    )
    if ocr_report is not None and ocr_run is not None:
        report = ocr_run.report()
        if report:
            ocr_report.update(report)
            logger.info("PDF OCR report: {}", report)
    if not chunks:
        raise PdfNoReadableTextError()
    return chunks


def _extract_docx(file_path: str, chunk_size: int) -> list[dict]:
    from docx import Document
    doc = Document(file_path)
    chunks: list[dict] = []
    current = ""
    page_number = 1

    for para in doc.paragraphs:
        text = clean(para.text).strip()
        if not text:
            continue
        if len(current) + len(text) + 1 > chunk_size:
            chunks.append({"page_number": page_number, "content": current or "[Leere Seite]"})
            page_number += 1
            current = text
        else:
            current = (current + " " + text).strip() if current else text

    # flush last chunk
    if current or not chunks:
        chunks.append({"page_number": page_number, "content": current or "[Leere Seite]"})

    return chunks


def _extract_pptx(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    from pptx import Presentation
    prs = Presentation(file_path)
    chunks: list[dict] = []
    for slide_num, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = clean(para.text).strip()
                    if t:
                        parts.append(t)
        content = " ".join(parts).strip()
        if not content:
            chunks.append({"page_number": slide_num, "content": "[Leere Seite]"})
        else:
            for sub in split_text(content, chunk_size, overlap):
                chunks.append({"page_number": slide_num, "content": sub})
    return chunks




def _extract_text(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = clean(f.read())

    if not text.strip():
        return [{"page_number": 1, "content": "[Leere Seite]"}]

    chunks: list[dict] = []
    start = 0
    page_number = 1
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip() or "[Leere Seite]"
        chunks.append({"page_number": page_number, "content": chunk})
        page_number += 1
        start = end - overlap  # overlap with previous chunk
        if start >= len(text):
            break

    return chunks


# ── Audio/Video transcript chunking ─────────────────────────────────────────────

_AUDIO_EXTENSIONS = {"mp3", "mp4", "wav", "flac", "m4a", "webm"}
# A YouTube source has no file but a transcript, downstream it counts as media.
_TRANSCRIPT_TYPES = _AUDIO_EXTENSIONS | {"youtube"}


def is_media_file(file_type: str) -> bool:
    """True when the source carries a transcript with timestamps."""
    return file_type.lower().lstrip(".") in _TRANSCRIPT_TYPES


def segments_to_chunks(segments: list[dict]) -> list[dict]:
    """Groups Whisper segments into chunks with timestamps."""
    chunks: list[dict] = []
    current_text = ""
    current_start: float | None = None
    current_end: float = 0.0
    page_number = 1

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        if current_start is None:
            current_start = seg["start"]

        # Check if adding this segment exceeds PIECE_CHARS
        combined = (current_text + " " + text).strip() if current_text else text
        if len(combined) > PIECE_CHARS and current_text:
            # Flush current chunk
            chunks.append({
                "page_number": page_number,
                "content": current_text,
                "start_time": current_start,
                "end_time": current_end,
            })
            page_number += 1
            current_text = text
            current_start = seg["start"]
            current_end = seg["end"]
        else:
            current_text = combined
            current_end = seg["end"]

    # Flush remaining
    if current_text and current_start is not None:
        chunks.append({
            "page_number": page_number,
            "content": current_text,
            "start_time": current_start,
            "end_time": current_end,
        })

    logger.info("segments_to_chunks: {} segments → {} chunks", len(segments), len(chunks))
    return chunks
