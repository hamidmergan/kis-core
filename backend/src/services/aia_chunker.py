"""Document chunker for KI Tutor - extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

import re
import time
import unicodedata

from loguru import logger


class PdfNoReadableTextError(ValueError):
    """Raised when a PDF has no extractable text (typical for scanned PDFs).

    The Celery task that catches this maps it to a localized error_message
    using the source's creator locale. Carries no message body - the route /
    task is the only place that knows which locale to render in.
    """


class OcrFailedError(RuntimeError):
    """Raised when OCR for a page fails after all retries (incl. transient 429s).

    Internal signal between ``_ocr_image_with_retry`` and ``_OcrRun`` only. It
    does NOT escape the chunker: a page that will not come through keeps its
    text layer and is booked as "open" in the run's report. OCR is a bonus, and
    a shared, rate-limited service must never be able to kill an upload.
    """

    def __init__(self, page_number: int):
        self.page_number = page_number
        super().__init__(f"OCR failed for page {page_number} after retries")


# Per-page OCR retry budget. Transient upstream errors (rate limits, timeouts,
# 5xx) are retried with exponential backoff before the page is given up on and
# booked as open. Kept small: the OCR endpoint is shared, so a long per-page
# retry storm would only deepen the contention it is reacting to.
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
    Either way, exhausting the budget raises ``OcrFailedError``, which ``_OcrRun``
    turns into an open page in its report. ``sleep`` is injectable for tests.
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


# How many pages may fail before OCR is switched off for the REST of the document.
# The per-page backoff above is the expensive part (~31s of pure waiting per page,
# holding a Celery slot), so a service that dropped two pages in a row is down, not
# busy - and grinding through the remaining pages only deepens the contention and
# stalls every other upload behind it.
OCR_MAX_FAILED_PAGES = 2


class _OcrRun:
    """OCR bookkeeping for ONE document: what ran, what did not, when to stop.

    The caller asks ``wants(page)`` before rendering, hands the PNG to
    ``ocr_page(...)`` and gets the recognised text back - or ``""`` when the page
    did not come through. Nothing raises: the page simply keeps its text layer.

    ``report()`` is what the source row later shows. ``None`` means the document
    had no OCR candidate at all, so there is nothing to say about it.
    """

    def __init__(self, provider, *, sleep=time.sleep):
        self._provider = provider
        self._sleep = sleep
        self._failed = 0
        self._given_up = False
        self.done = 0
        self.open: list[int] = []

    def wants(self, page_number: int) -> bool:
        """True when this candidate page should actually be rendered and sent.

        False when OCR is off/unconfigured or the run has given up. Either way the
        page is booked as open, so it can be caught up later once OCR is available.
        """
        if self._provider is None or self._given_up:
            self.open.append(page_number)
            return False
        return True

    def mark_open(self, page_number: int) -> None:
        """Book a candidate page as open without blaming the OCR service.

        Used when the page could not even be rendered - not a service failure, so
        it must not count towards the give-up budget.
        """
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


# 1000 chars ≈ 250-333 tokens (German); 200 char overlap = 20% (LangChain default).
# All supported embedding models (nomic-embed-text 2048 ctx, e5-mistral 4096 ctx) handle this comfortably.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# Ein mit LaTeX gesetztes PDF malt Akzente als EIGENE Glyphe neben den Grundbuchstaben,
# nicht als ein zusammengesetztes Zeichen. Die Textebene gibt sie darum als freistehendes
# Zeichen aus, mal vor und mal hinter dem Buchstaben: "Komplement¨armenge", "H¨aufigkeit",
# "A¯". Das trifft nicht nur die Anzeige. Es trifft vor allem die Vektorsuche, weil
# "H¨aufigkeit" nicht mehr auf eine Frage nach "Häufigkeit" passt, und jedes Werkzeug,
# das auf denselben Chunks arbeitet.
#
# Welches freistehende Zeichen zu welchem kombinierenden gehoert, steht in den
# Unicode-Daten selbst (Zerlegung "<compat> 0020 XXXX"). Die Tabelle wird daraus
# abgeleitet statt von Hand gepflegt: so gilt sie in jeder Sprache und nimmt echte
# Zeichen wie "°", "²" oder "×" nicht versehentlich mit. Abgesucht wird nur der
# Bereich, in dem PDF-Extraktoren solche Zeichen ueberhaupt ausgeben (Latin-1 plus
# Spacing Modifier Letters).
_ACCENT_SCAN_RANGE = range(0x00A0, 0x0300)

# Der Akut bleibt bewusst draussen. Er wird in normalem Text als Apostroph getippt
# ("geht´s"), und dort waere ein Zusammenziehen zu "gehtś" eine Verschlimmbesserung.
# Bei ihm ist der Schaden durch ein falsches Zusammenziehen groesser als der Nutzen.
_ACCENT_EXCLUDED = {"´"}


def _spacing_accent_marks() -> dict[str, str]:
    """Freistehender Akzent -> kombinierender Akzent, aus den Unicode-Daten abgeleitet."""
    marks: dict[str, str] = {}
    for code_point in _ACCENT_SCAN_RANGE:
        char = chr(code_point)
        if char in _ACCENT_EXCLUDED:
            continue
        parts = unicodedata.decomposition(char).split()
        if len(parts) == 3 and parts[0] == "<compat>" and parts[1] == "0020":
            marks[char] = chr(int(parts[2], 16))
    return marks


_SPACING_ACCENTS = _spacing_accent_marks()
_SPACING_ACCENT_RE = re.compile(f"[{re.escape(''.join(_SPACING_ACCENTS))}]")


def _attach_spacing_accents(text: str) -> str:
    """Haenge jeden freistehenden Akzent an den Buchstaben, zu dem er gehoert."""
    out: list[str] = []
    index = 0
    end = len(text)
    while index < end:
        char = text[index]
        mark = _SPACING_ACCENTS.get(char)
        if mark:
            # Der FOLGENDE Buchstabe hat Vorrang. In "Komplement¨armenge" steht auf
            # beiden Seiten einer, gemeint ist aber das "a".
            if index + 1 < end and text[index + 1].isalpha():
                out.append(text[index + 1] + mark)
                index += 2
                continue
            # Sonst der vorangehende: "A¯", "p(A¯)".
            if out and out[-1][-1:].isalpha():
                out[-1] += mark
                index += 1
                continue
            # Kein Buchstabe daneben, also nicht sicher zuzuordnen. In "Fur jedes
            # Ereignis ¨ A" gehoert das Zeichen mehrere Woerter zurueck zu "Fur".
            # Lieber stehen lassen als falsch anhaengen.
        out.append(char)
        index += 1
    return "".join(out)


def _clean(text: str) -> str:
    """Strip NUL bytes and reunite accents the PDF text layer left standing alone.

    NUL bytes go because Postgres TEXT columns reject them. The accent repair is
    described at ``_SPACING_ACCENTS`` above. The closing NFC pass does two jobs: it
    fuses the reattached mark into a single character where one exists ("a" plus
    combining diaeresis becomes "ä"), and it folds the lookalike code points that
    the same PDFs emit onto their canonical twin (the Ohm sign becomes an Omega),
    so equal-looking text also compares and embeds as equal.
    """
    if not text:
        return text
    text = text.replace("\x00", "")
    if _SPACING_ACCENT_RE.search(text):
        text = _attach_spacing_accents(text)
    return unicodedata.normalize("NFC", text)


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


# A bullet group must carry at least this much of its own text to be indexed on its
# own; thinner ones travel with their neighbour. Sits above the 100-char floor the
# citation attribution applies, so a group that survives here can also be cited.
SLIDE_GROUP_MIN_CHARS = 120


def extract_chunks(
    file_path: str,
    file_type: str,
    progress_cb=None,
    ocr_report: dict | None = None,
) -> list[dict]:
    """Extract text chunks from a document file.

    Args:
        file_path:   Absolute path to the file on disk.
        file_type:   One of "pdf", "docx", "pptx", "txt", "md".
        progress_cb: Optional callback ``fn(stage, page=None, total=None)``
                     invoked when the extractor enters a new stage. Used by
                     the indexing task to surface per-page OCR progress in
                     the UI without coupling the chunker to the DB.
        ocr_report:  Optional dict filled in with ``{"enabled", "done", "open"}``
                     when the document had OCR candidate pages. Left untouched
                     otherwise, so "no key" and "nothing to report" are the same
                     thing to the caller. PDF only - no other type OCRs.

    Returns:
        List of dicts with keys:
          - page_number (int, 1-indexed)
          - content    (str)
    """
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(file_path, CHUNK_SIZE, CHUNK_OVERLAP, progress_cb, ocr_report)
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

# Aufloesung des Seitenbilds, das an die Bilderkennung geht. pdfium rendert von Haus aus
# mit 72 DPI, der Faktor rechnet das um.
#
# Waren 200 DPI, das kostete stillschweigend Tabellenzellen. Im Kursplan zweier Seminar-
# PDFs fehlte die Zelle "25.03.2026, 17:30 Uhr", und damit im Zeitplan ein Termin, ohne
# dass es irgendwo aufgefallen waere. Am 13.08.2026 durchgemessen, dieselbe Seite, nur
# die Aufloesung veraendert:
#
#   300 250 175 150 144 120 100 DPI -> Zelle gelesen
#   200 DPI                        -> Zelle fehlt, 6 von 6 Laeufen
#
# Also kein Ausrutscher des Dienstes und auch nicht "je hoeher desto besser", sondern
# genau dieser eine Wert. 150 DPI liegt bei der Aufloesung, mit der solche Modelle
# ueblicherweise arbeiten, las in der Messung jede Seite mindestens so gut wie 200 DPI
# und schickt dabei ein Drittel weniger Daten ueber die geteilte Leitung.
_OCR_RENDER_DPI = 150


def _render_ocr_png(page, page_number: int) -> bytes | None:
    """Seitenbild fuer die Bilderkennung, oder None wenn das Rendern scheitert.

    Rendern ist lokal und liefert bei gleichem Eingang immer dasselbe. Ein Fehler hier
    laesst sich durch Wiederholen nicht heilen, deshalb faellt nur diese eine Seite aus.
    """
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


def _page_line_boxes(textpage) -> list:
    """The page's RAW text rects with their geometry, or [] when pdfium reports none.

    Raw on purpose: the running header is only stable in this form. Assembling rows first
    glues the footer's three text objects together on some pages and not on others (their
    baselines differ by fractions of a point), and a variant that only occurs on a few
    pages never looks like furniture. Rows are assembled AFTER the furniture is dropped.

    Empty is a normal answer (an image-only page), and every caller falls back to the
    plain text path for it — layout knowledge is a bonus, never a requirement.
    """
    from src.services.aia_pdf_layout import LineBox
    try:
        n = textpage.count_rects()
    except Exception as e:
        logger.warning("PDF layout: rect count failed, falling back to plain text: {}", e)
        return []
    boxes = []
    for i in range(n):
        try:
            left, top, right, bottom = textpage.get_rect(i)
            text = textpage.get_text_bounded(left=left, bottom=bottom, right=right, top=top)
        except Exception:
            continue
        text = _clean(text or "").strip()
        if text:
            boxes.append(LineBox(text=text, x=left, y=top))
    return boxes


def _extract_pdf(
    file_path: str,
    chunk_size: int,
    overlap: int,
    progress_cb=None,
    ocr_report: dict | None = None,
) -> list[dict]:
    import pypdfium2 as pdfium
    from src.services.aia_pdf_layout import (
        boilerplate_keys, is_boilerplate, merge_rows, slide_groups, strip_boilerplate_text,
    )
    chunks: list[dict] = []
    # Pass 1 collects every page, pass 2 cuts it up: the running header can only be
    # recognised once all pages are in, since "stands on most pages" is the whole
    # definition of it.
    page_texts: list[str] = []
    page_lines: list[list] = []
    doc = pdfium.PdfDocument(file_path)
    total_pages = len(doc)

    # Lazy-init OCR provider once per PDF. None means OCR toggle is off or
    # the configured provider couldn't be constructed - either way, skip OCR.
    ocr_run: _OcrRun | None = None

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
        if should_ocr and ocr_run is None:
            try:
                from src.services.aia_ocr import get_ocr_provider
                provider = get_ocr_provider()
            except Exception as e:
                logger.warning("OCR provider lookup failed: {}", e)
                provider = None
            ocr_run = _OcrRun(provider)

        # ocr_tried = the page is an OCR candidate AND OCR is enabled/available
        # and the run has not given up. The log below reports ocr_ran from
        # ocr_merged, i.e. text really came back: logging only the heuristic
        # made a disabled toggle look like OCR had run.
        ocr_tried = should_ocr and ocr_run.wants(page_num + 1)
        ocr_merged = False

        if ocr_tried:
            if progress_cb:
                progress_cb("ocr", page_num + 1, total_pages)
            png_bytes = _render_ocr_png(page, page_num + 1)

            if png_bytes is None:
                ocr_run.mark_open(page_num + 1)
            else:
                # A page that will not come through returns "" and is booked as
                # open. It keeps its text layer, the source stays usable, and the
                # owner can catch the page up later from the source menu.
                ocr_text = _clean(ocr_run.ocr_page(png_bytes, page_num + 1)).strip()
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

        # Geometry is read from the TEXT LAYER only. An OCR'd page has no rects for the
        # text that matters, so it keeps the plain path and loses nothing. A page whose
        # OCR did NOT come through has only its text layer, so it keeps its geometry.
        page_lines.append([] if ocr_merged else _page_line_boxes(textpage))
        page_texts.append(text)
        textpage.close()
        page.close()
    doc.close()

    # Pass 2. A bullet-structured slide is cut per top-level bullet group: as one
    # page-sized chunk its embedding is the average of everything on the slide, and the
    # one bullet a reader is after barely registers (measured 0.513 vs 0.205 against the
    # sentence it backs). Everything else keeps the whole-page path and only loses its
    # running header, since re-ordering prose by geometry would interleave a two-column
    # statute.
    boiler = boilerplate_keys(page_lines, page_texts)
    n_grouped = 0
    for i, (lines, text) in enumerate(zip(page_lines, page_texts)):
        # Drop the furniture on the RAW rects, then assemble rows: a glyph and its words
        # only become one line once the header fragments are out of the way.
        kept = merge_rows([b for b in lines if not is_boilerplate(b.text, boiler)])
        groups = slide_groups(kept, min_chars=SLIDE_GROUP_MIN_CHARS) if kept else []
        if groups:
            n_grouped += 1
            parts = groups
        else:
            parts = [strip_boilerplate_text(text, boiler)]
        for part in parts:
            for sub in _split_text(part, chunk_size, overlap):
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
