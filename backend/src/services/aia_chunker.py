"""Document chunker for KI Tutor - extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

import time

from loguru import logger


class PdfNoReadableTextError(ValueError):
    """Raised when a PDF has no extractable text (typical for scanned PDFs).

    The Celery task that catches this maps it to a localized error_message
    using the source's creator locale. Carries no message body - the route /
    task is the only place that knows which locale to render in.
    """


class OcrFailedError(RuntimeError):
    """Raised when OCR for a page fails after all retries (incl. transient 429s).

    The page-level retry below has already waited and re-OCR'd the same page up
    to ``OCR_MAX_ATTEMPTS`` times. When it still fails we raise this instead of
    silently dropping the page, so the indexing task marks the source 'failed'
    with a localized message and the user can re-trigger later via the existing
    retry button. The message deliberately carries no "429" so the task does NOT
    re-run the whole document (the page-level retries already covered that).
    """

    def __init__(self, page_number: int):
        self.page_number = page_number
        super().__init__(f"OCR failed for page {page_number} after retries")


# Per-page OCR retry budget. Transient upstream errors (rate limits, timeouts,
# 5xx) are retried with exponential backoff before the page - and the whole
# source - is failed loudly. Kept small: the OCR endpoint is shared, so a long
# per-page retry storm would only deepen the contention it is reacting to.
OCR_MAX_ATTEMPTS = 5

_TRANSIENT_OCR_MARKERS = (
    "429", "rate limit", "too many requests",
    "timeout", "timed out",
    "502", "503", "504", "bad gateway", "service unavailable", "gateway timeout",
)


def _is_transient_ocr_error(e: Exception) -> bool:
    """True for upstream errors worth re-trying the SAME page (429/5xx/timeout).

    String-based on purpose: OCR providers raise heterogeneous exception types
    (httpx.HTTPStatusError, openai errors, RuntimeError) but all surface the
    status/cause in their message. Mirrors the task-level rate-limit check.
    """
    msg = str(e).lower()
    return any(m in msg for m in _TRANSIENT_OCR_MARKERS)


def _ocr_image_with_retry(provider, png_bytes, page_number, *, attempts=OCR_MAX_ATTEMPTS, sleep=time.sleep):
    """OCR one page image, retrying transient failures with exponential backoff.

    Non-transient errors fail fast (retrying a deterministic error is pointless).
    Either way, exhausting the budget raises ``OcrFailedError`` so nothing is
    silently lost from the index. ``sleep`` is injectable for tests.
    """
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
    raise OcrFailedError(page_number) from last_exc

# 1000 chars ≈ 250-333 tokens (German); 200 char overlap = 20% (LangChain default).
# All supported embedding models (nomic-embed-text 2048 ctx, e5-mistral 4096 ctx) handle this comfortably.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _clean(text: str) -> str:
    """Strip NUL bytes - Postgres TEXT columns reject them."""
    return text.replace("\x00", "") if text else text


def _merge_small_fragments(chunks: list[str], min_chars: int) -> list[str]:
    """Fold sub-*min_chars* fragments into a neighbour.

    A split page can leave a tiny trailing scrap (a running-header line or the
    last few overlap chars) as its own chunk; such a fragment carries no real
    standalone meaning and becomes a "magnet" in vector search that mis-ranks for
    thin queries. Folding it into the adjacent chunk keeps every character and,
    since this runs per page, does not affect page attribution. A page that is
    simply short stays a single chunk (nothing to merge)."""
    if len(chunks) <= 1:
        return chunks
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < min_chars:
            merged[-1] = (merged[-1] + " " + c).strip()
        else:
            merged.append(c)
    # A tiny leading fragment had no predecessor above; fold it forward instead.
    if len(merged) > 1 and len(merged[0]) < min_chars:
        merged[1] = (merged[0] + " " + merged[1]).strip()
        merged.pop(0)
    return merged


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks of chunk_size chars, breaking at whitespace."""
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Break at last whitespace to avoid cutting words
        if end < len(text):
            last_space = chunk.rfind(" ")
            if last_space > chunk_size // 2:
                chunk = chunk[:last_space]
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        next_start = start + len(chunk) - overlap
        if next_start <= start:
            break
        start = next_start
    # Fold away tiny leftover fragments (< 10% of a full chunk) so a split page
    # does not seed the index with header-scrap magnets. Threshold is relative to
    # chunk_size so tiny test sizes are unaffected.
    return _merge_small_fragments(chunks, max(1, chunk_size // 10))


ProgressCallback = "Callable[[str, int | None, int | None], None] | None"


def extract_chunks(
    file_path: str,
    file_type: str,
    progress_cb=None,
) -> list[dict]:
    """Extract text chunks from a document file.

    Args:
        file_path:   Absolute path to the file on disk.
        file_type:   One of "pdf", "docx", "pptx", "txt", "md".
        progress_cb: Optional callback ``fn(stage, page=None, total=None)``
                     invoked when the extractor enters a new stage. Used by
                     the indexing task to surface per-page OCR progress in
                     the UI without coupling the chunker to the DB.

    Returns:
        List of dicts with keys:
          - page_number (int, 1-indexed)
          - content    (str)
    """
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(file_path, CHUNK_SIZE, CHUNK_OVERLAP, progress_cb)
    if ft == "docx":
        return _extract_docx(file_path, CHUNK_SIZE)
    if ft == "pptx":
        return _extract_pptx(file_path, CHUNK_SIZE, CHUNK_OVERLAP)
    if ft in ("txt", "md"):
        return _extract_text(file_path, CHUNK_SIZE, CHUNK_OVERLAP)
    if ft in ("mp3", "mp4", "wav", "flac", "m4a", "webm"):
        raise ValueError(
            "Audio/Video files must be transcribed first - use segments_to_chunks() instead."
        )
    raise ValueError(f"Unsupported file_type: {file_type!r}")




# ── Format-specific extractors ────────────────────────────────────────────────

# Trigger OCR when raster images cover >= this fraction of the page area.
# Bitmap-coverage heuristic skips logos/decorative icons (typically < 5%) and
# only OCRs pages dominated by screenshots or full-page scans. Title slides
# with a header logo and short text no longer trigger spurious vision calls.
_OCR_IMAGE_COVERAGE_THRESHOLD = 0.20


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
) -> list[dict]:
    import io
    import pypdfium2 as pdfium
    chunks: list[dict] = []
    doc = pdfium.PdfDocument(file_path)
    total_pages = len(doc)

    # Lazy-init OCR provider once per PDF. None means OCR toggle is off or
    # the configured provider couldn't be constructed - either way, skip OCR.
    ocr_provider = None
    ocr_checked = False

    if progress_cb:
        progress_cb("parsing", None, None)

    for page_num in range(total_pages):
        page = doc[page_num]
        textpage = page.get_textpage()
        raw_text = textpage.get_text_range() or ""
        text = _clean(raw_text).strip()

        # Bitmap-coverage heuristic: only OCR pages where raster images
        # dominate the layout (screenshots, scans). Small header/footer logos
        # fall below the threshold and are correctly ignored, even on pages
        # with little or no text-layer content.
        coverage = _bitmap_coverage(page)
        should_ocr = coverage >= _OCR_IMAGE_COVERAGE_THRESHOLD

        # Resolve the OCR provider lazily on the first page that wants OCR, so the
        # log below reports whether OCR ACTUALLY ran (provider present) and not just
        # the coverage heuristic. None = OCR toggle off / provider missing -> skip.
        if should_ocr and not ocr_checked:
            try:
                from src.services.aia_ocr import get_ocr_provider
                ocr_provider = get_ocr_provider()
            except Exception as e:
                logger.warning("OCR provider lookup failed: {}", e)
                ocr_provider = None
            ocr_checked = True

        # ocr_wanted = page is image-heavy enough to be an OCR candidate;
        # ocr_ran = it was AND OCR is actually enabled/available, i.e. text below
        # really came from OCR. Logging only the heuristic before made a disabled
        # toggle look like OCR had run.
        ocr_ran = should_ocr and ocr_provider is not None
        logger.info(
            "PDF page {}: text={} chars, image_coverage={:.1%}, ocr_wanted={}, ocr_ran={}",
            page_num + 1, len(text), coverage, should_ocr, ocr_ran,
        )

        if should_ocr:
            if ocr_provider is not None:
                if progress_cb:
                    progress_cb("ocr", page_num + 1, total_pages)
                # Render is local and deterministic - a failure here can't be
                # fixed by retrying, so log and skip (no OCR for this page).
                png_bytes = None
                try:
                    # 200 DPI = scale factor 200/72 since pdfium native resolution is 72 DPI
                    bitmap = page.render(scale=200 / 72)
                    pil = bitmap.to_pil()
                    buf = io.BytesIO()
                    pil.save(buf, format="PNG")
                    png_bytes = buf.getvalue()
                except Exception as e:
                    logger.warning("OCR page {}: render failed, skipping: {}", page_num + 1, e)

                if png_bytes is not None:
                    # The OCR call itself retries transient 429/5xx/timeouts and,
                    # if still failing, raises OcrFailedError - which propagates
                    # out so the task fails the source loudly (retry button)
                    # instead of silently dropping the page from the index.
                    ocr_text = _clean(
                        _ocr_image_with_retry(ocr_provider, png_bytes, page_num + 1)
                    ).strip()
                    if ocr_text:
                        logger.info(
                            "PDF page {}: OCR extracted {} chars (text-layer had {})",
                            page_num + 1, len(ocr_text), len(text),
                        )
                        # Merge text-layer remnants + OCR output; OCR wins if empty layer
                        text = (text + "\n" + ocr_text).strip() if text else ocr_text

        for sub in _split_text(text, chunk_size, overlap):
            chunks.append({"page_number": page_num + 1, "content": sub})
        textpage.close()
        page.close()
    doc.close()
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
        text = _clean(para.text).strip()
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
                    t = _clean(para.text).strip()
                    if t:
                        parts.append(t)
        content = " ".join(parts).strip()
        if not content:
            chunks.append({"page_number": slide_num, "content": "[Leere Seite]"})
        else:
            for sub in _split_text(content, chunk_size, overlap):
                chunks.append({"page_number": slide_num, "content": sub})
    return chunks




def _extract_text(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = _clean(f.read())

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


def is_media_file(file_type: str) -> bool:
    """Check if file_type is an audio/video format."""
    return file_type.lower().lstrip(".") in _AUDIO_EXTENSIONS


def segments_to_chunks(segments: list[dict]) -> list[dict]:
    """Merge Whisper segments into embedding-optimal chunks with timestamps.

    Args:
        segments: List of dicts with keys: start (float), end (float), text (str).

    Returns:
        List of dicts with keys:
          - page_number (int, sequential 1-indexed)
          - content     (str)
          - start_time  (float, seconds)
          - end_time    (float, seconds)
    """
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

        # Check if adding this segment exceeds CHUNK_SIZE
        combined = (current_text + " " + text).strip() if current_text else text
        if len(combined) > CHUNK_SIZE and current_text:
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
