"""Document chunker for KI Tutor – extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

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
    provider = os.getenv("TUTOR_EMBEDDING_PROVIDER", "ollama")
    return _CHUNK_PARAMS.get(provider, _CHUNK_PARAMS_DEFAULT)


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
    raise ValueError(f"Unsupported file_type: {file_type!r}")


def get_page_count(file_path: str, file_type: str) -> int:
    """Return the number of logical pages / chunks in a document."""
    return len(extract_chunks(file_path, file_type))


# ── Format-specific extractors ────────────────────────────────────────────────

def _extract_pdf(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    import fitz  # PyMuPDF
    chunks: list[dict] = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()
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
        text = para.text.strip()
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
                    t = para.text.strip()
                    if t:
                        parts.append(t)
        content = " ".join(parts).strip()
        if not content:
            chunks.append({"page_number": slide_num, "content": "[Leere Seite]"})
        else:
            for sub in _split_text(content, chunk_size, overlap):
                chunks.append({"page_number": slide_num, "content": sub})
    return chunks


def _is_toc_page(blocks: list[dict]) -> bool:
    """Detect if a page is a table of contents by looking for dotted leader patterns."""
    import re
    toc_pattern = re.compile(r'\.{4,}\s*\d+\s*$')  # "........12"
    matches = sum(1 for b in blocks if toc_pattern.search(b["content"]))
    return matches >= 3  # 3+ lines with dotted leaders = TOC page


def _get_dominant_font_size(block_dict: dict) -> float:
    """Get the most common font size in a block (by character count)."""
    size_chars: dict[float, int] = {}
    for line in block_dict.get("lines", []):
        for span in line.get("spans", []):
            size = round(span["size"], 1)
            size_chars[size] = size_chars.get(size, 0) + len(span["text"])
    if not size_chars:
        return 0.0
    return max(size_chars, key=size_chars.get)  # type: ignore[arg-type]


def _should_skip_block(bbox: tuple, content: str, font_size: float,
                       body_font_size: float, page_width: float, page_height: float) -> str | None:
    """Return a reason string if this block should be skipped, else None."""
    word_count = len(content.split())

    # Very short blocks (page numbers, single labels)
    if word_count < 5:
        return "too_short"

    # Headings: larger font than body AND short text
    if font_size > body_font_size + 0.5 and word_count < 25:
        return "heading"

    # Footnotes: smaller font AND positioned in bottom 15%
    rel_y1 = bbox[3] / page_height if page_height > 0 else 1
    if font_size < body_font_size - 0.5 and rel_y1 > 0.85:
        return "footnote"

    # Header/footer areas
    rel_y0 = bbox[1] / page_height if page_height > 0 else 0
    if (rel_y0 < 0.05 or rel_y1 > 0.95) and word_count < 15:
        return "header_footer"

    # Very narrow blocks (margin annotations)
    block_width = bbox[2] - bbox[0]
    if block_width < page_width * 0.2:
        return "narrow"

    return None


def extract_paragraphs_with_bbox(file_path: str) -> list[dict]:
    """Extract text paragraphs with bounding boxes from a PDF.

    Adjacent blocks with same font size and small vertical gaps are merged
    into visual paragraphs. Each visual paragraph gets exactly 1 summary.
    Headings, TOC pages, footnotes, and images are skipped.

    Returns list of dicts with keys:
      - page_number (int, 1-indexed)
      - block_index (int, 0-indexed within page)
      - bbox        (dict with x0, y0, x1, y1 in PDF coordinates)
      - content     (str)
    """
    import fitz
    doc = fitz.open(file_path)
    paragraphs: list[dict] = []

    # First pass: determine the body font size across the document
    all_font_sizes: dict[float, int] = {}
    for page in doc:
        page_dict = page.get_text("dict")
        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    size = round(span["size"], 1)
                    all_font_sizes[size] = all_font_sizes.get(size, 0) + len(span["text"])
    body_font_size = max(all_font_sizes, key=all_font_sizes.get) if all_font_sizes else 10.0  # type: ignore[arg-type]
    # Typical line height for the body font
    line_height = body_font_size * 1.4

    # Second pass: extract and merge paragraphs
    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        page_height = page.rect.height

        # Collect all text blocks with metadata
        page_blocks: list[dict] = []
        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue
            lines_text = []
            for line in block["lines"]:
                spans_text = "".join(span["text"] for span in line["spans"])
                lines_text.append(spans_text.strip())
            content = " ".join(line for line in lines_text if line).strip()
            if content:
                font_size = _get_dominant_font_size(block)
                page_blocks.append({
                    "bbox": block["bbox"],
                    "content": content,
                    "font_size": font_size,
                })

        # Skip TOC pages entirely
        if _is_toc_page(page_blocks):
            continue

        # Filter out non-paragraph blocks, then merge adjacent ones
        body_blocks: list[dict] = []
        for pb in page_blocks:
            skip = _should_skip_block(
                pb["bbox"], pb["content"], pb["font_size"],
                body_font_size, page_width, page_height,
            )
            if skip is None:
                body_blocks.append(pb)

        # Merge blocks that belong to the same visual paragraph:
        # - Small vertical gap (< 1.5x line height)
        # - Same font size (within 0.5pt)
        # Note: left margin check is relaxed — tables have different indents
        # but blocks within them belong together if they're vertically close
        merged: list[dict] = []
        for block in body_blocks:
            if not merged:
                merged.append({
                    "bboxes": [block["bbox"]],
                    "content": block["content"],
                    "font_size": block["font_size"],
                })
                continue

            prev = merged[-1]
            prev_bbox = prev["bboxes"][-1]
            curr_bbox = block["bbox"]

            gap = curr_bbox[1] - prev_bbox[3]  # vertical gap
            same_font = abs(block["font_size"] - prev["font_size"]) < 0.5
            # Horizontally overlapping = likely same column/paragraph area
            h_overlap = curr_bbox[2] > prev_bbox[0] and curr_bbox[0] < prev_bbox[2]

            if 0 <= gap < line_height * 0.8 and same_font and h_overlap:
                # Same paragraph — merge
                prev["bboxes"].append(curr_bbox)
                prev["content"] += " " + block["content"]
            else:
                # New paragraph
                merged.append({
                    "bboxes": [block["bbox"]],
                    "content": block["content"],
                    "font_size": block["font_size"],
                })

        # Build final paragraphs with tight bboxes
        # Skip paragraphs that are too short to benefit from a summary
        _MIN_SUMMARY_WORDS = 20
        for idx, m in enumerate(merged):
            word_count = len(m["content"].split())
            if word_count < _MIN_SUMMARY_WORDS:
                continue
            bboxes = m["bboxes"]
            paragraphs.append({
                "page_number": page_num,
                "block_index": idx,
                "bbox": {
                    "x0": min(b[0] for b in bboxes),
                    "y0": bboxes[0][1],
                    "x1": max(b[2] for b in bboxes),
                    "y1": bboxes[-1][3],
                },
                "content": m["content"],
            })

    doc.close()
    return paragraphs


def _extract_text(file_path: str, chunk_size: int, overlap: int) -> list[dict]:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

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
