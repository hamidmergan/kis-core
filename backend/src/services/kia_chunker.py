"""Document chunker for KI Tutor – extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

import re

from loguru import logger

# Chunk sizes per embedding provider:
#   ollama / nomic-embed-text: BERT 2048-token ctx, German ~2-3 chars/token
#     → 600 chars ≈ 240 tokens, safely within limit
#   kisski / e5-mistral-7b-instruct: 4096-token ctx, German ~3-4 chars/token
#     → 1000 chars ≈ 250-333 tokens, well within limit and matches original value
_CHUNK_PARAMS: dict[str, tuple[int, int]] = {
    "ollama":  (600,  80),
    "kisski": (1000, 100),
}
_CHUNK_PARAMS_DEFAULT = _CHUNK_PARAMS["ollama"]


def _get_chunk_params() -> tuple[int, int]:
    """Return (chunk_size, overlap) for the configured embedding provider."""
    import os
    provider = os.getenv("KIA_EMBEDDING_PROVIDER", "ollama")
    return _CHUNK_PARAMS.get(provider, _CHUNK_PARAMS_DEFAULT)


def _clean(text: str) -> str:
    """Strip NUL bytes — Postgres TEXT columns reject them."""
    return text.replace("\x00", "") if text else text


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
    return chunks


def extract_chunks(file_path: str, file_type: str) -> list[dict]:
    """Extract text chunks from a document file.

    Args:
        file_path: Absolute path to the file on disk.
        file_type:  One of "pdf", "docx", "pptx", "txt", "md".

    Returns:
        List of dicts with keys:
          - page_number (int, 1-indexed)
          - content    (str)
    """
    chunk_size, overlap = _get_chunk_params()
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(file_path, chunk_size, overlap)
    if ft == "docx":
        return _extract_docx(file_path, chunk_size)
    if ft == "pptx":
        return _extract_pptx(file_path, chunk_size, overlap)
    if ft in ("txt", "md"):
        return _extract_text(file_path, chunk_size, overlap)
    if ft in ("mp3", "mp4", "wav", "flac", "m4a", "webm"):
        raise ValueError(
            "Audio/Video files must be transcribed first – use segments_to_chunks() instead."
        )
    raise ValueError(f"Unsupported file_type: {file_type!r}")


def get_page_count(file_path: str, file_type: str) -> int:
    """Return the number of logical pages / chunks in a document."""
    return len(extract_chunks(file_path, file_type))


# ── Format-specific extractors ────────────────────────────────────────────────

_OCR_MIN_CHARS = 100        # fully image-only pages: always OCR
_OCR_MIXED_MAX_CHARS = 400  # page has images AND text-layer < this → also OCR
_OCR_IMAGE_AREA_FRAC = 0.15  # image covers >= 15% of page area → treat as "has images"


def _page_has_significant_image(page) -> bool:
    """True if the page contains a raster image covering ≥ _OCR_IMAGE_AREA_FRAC
    of the page area. Filters out small logos/icons.
    """
    try:
        rect = page.rect
        page_area = max(rect.width * rect.height, 1.0)
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 1:  # 1 = image block
                continue
            bbox = block.get("bbox") or [0, 0, 0, 0]
            w = max(bbox[2] - bbox[0], 0)
            h = max(bbox[3] - bbox[1], 0)
            if (w * h) / page_area >= _OCR_IMAGE_AREA_FRAC:
                return True
    except Exception:
        return False
    return False


def _extract_pdf(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    import fitz  # PyMuPDF
    chunks: list[dict] = []
    doc = fitz.open(file_path)

    # Lazy-init OCR provider once per PDF. None means OCR toggle is off or
    # the configured provider couldn't be constructed — either way, skip OCR.
    ocr_provider = None
    ocr_checked = False

    for page_num, page in enumerate(doc, start=1):
        text = _clean(page.get_text()).strip()

        # Trigger OCR on (a) near-empty pages (scanned docs) or (b) mixed pages
        # where a large image likely carries text the text-layer doesn't have.
        should_ocr = len(text) < _OCR_MIN_CHARS or (
            len(text) < _OCR_MIXED_MAX_CHARS and _page_has_significant_image(page)
        )

        if should_ocr:
            if not ocr_checked:
                try:
                    from src.services.kia_ocr import get_ocr_provider
                    ocr_provider = get_ocr_provider()
                except Exception as e:
                    logger.warning("OCR provider lookup failed: {}", e)
                    ocr_provider = None
                ocr_checked = True

            if ocr_provider is not None:
                try:
                    pix = page.get_pixmap(dpi=200)
                    png_bytes = pix.tobytes("png")
                    ocr_text = _clean(ocr_provider.ocr_image(png_bytes, "image/png")).strip()
                    if ocr_text:
                        logger.info(
                            "PDF page {}: OCR extracted {} chars (text-layer had {})",
                            page_num, len(ocr_text), len(text),
                        )
                        # Merge text-layer remnants + OCR output; OCR wins if empty layer
                        text = (text + "\n" + ocr_text).strip() if text else ocr_text
                except Exception as e:
                    logger.warning("OCR failed on page {}: {}", page_num, e)

        for sub in _split_text(text, chunk_size, overlap):
            chunks.append({"page_number": page_num, "content": sub})
    doc.close()
    if not chunks:
        raise ValueError(
            "Das PDF enthält keinen lesbaren Text. "
            "Gescannte PDFs werden aktuell nicht unterstützt. "
            "Bitte konvertiere das PDF zuerst mit einem OCR-Tool (z.B. Adobe Acrobat oder online unter smallpdf.com)."
        )
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


_STRUCTURAL_KEYWORDS = re.compile(
    r"^("
    r"table of contents|contents|inhaltsverzeichnis"
    r"|references|bibliography|literaturverzeichnis|quellenverzeichnis|literatur"
    r"|list of figures|list of tables|abbildungsverzeichnis|tabellenverzeichnis"
    r")$",
    re.IGNORECASE,
)

_TOC_DOTTED = re.compile(r"\.{4,}\s*\d+\s*$")          # "........12"
def _is_structural_page(blocks: list[dict]) -> bool:
    """Detect structural pages: TOC, references, list of figures/tables."""
    first = blocks[0]["content"].strip()
    if _STRUCTURAL_KEYWORDS.match(first):
        return True
    dotted = sum(1 for b in blocks if _TOC_DOTTED.search(b["content"]))
    if dotted >= 3:
        return True
    return False



def extract_page_texts(file_path: str) -> list[dict]:
    """Extract the visible text of each page from a PDF.

    Returns one entry per page with meaningful text content.
    Pages that are TOC, nearly empty, or contain only formulas/images are skipped.

    Returns list of dicts with keys:
      - page_number (int, 1-indexed)
      - content     (str)
    """
    import fitz
    doc = fitz.open(file_path)
    pages: list[dict] = []

    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict")

        # Collect all text blocks
        page_blocks = []
        for block in page_dict["blocks"]:
            if block["type"] != 0:  # skip images
                continue
            lines_text = []
            for line in block["lines"]:
                spans_text = "".join(span["text"] for span in line["spans"])
                lines_text.append(_clean(spans_text).strip())
            content = " ".join(ln for ln in lines_text if ln).strip()
            if content:
                page_blocks.append({"content": content, "bbox": block["bbox"]})

        if not page_blocks:
            continue

        # Skip structural pages (TOC, references, list of figures/tables)
        if _is_structural_page(page_blocks):
            logger.info("extract_page_texts: skipping structural page {}", page_num)
            continue

        # Join all text on the page
        full_text = " ".join(b["content"] for b in page_blocks).strip()

        # Strip leading page number (e.g. "11 Arbeitspaket..." → "Arbeitspaket...")
        full_text = re.sub(rf'^{page_num}\s+', '', full_text)
        word_count = len(full_text.split())

        # Skip pages with very little text (e.g. only formulas, images, page numbers)
        if word_count < 15:
            logger.info("extract_page_texts: skipping page {} ({} words)", page_num, word_count)
            continue

        pages.append({
            "page_number": page_num,
            "content": full_text,
        })

    doc.close()
    logger.info("extract_page_texts: {} pages with text extracted", len(pages))
    return pages


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
    chunk_size, _ = _get_chunk_params()
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

        # Check if adding this segment exceeds chunk_size
        combined = (current_text + " " + text).strip() if current_text else text
        if len(combined) > chunk_size and current_text:
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
