"""Document chunker for KI Tutor – extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

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


def _should_skip_block_pre(bbox: tuple, content: str,
                           page_width: float, page_height: float) -> str | None:
    """Pre-merge filter: only remove blocks that can NEVER belong to a paragraph."""
    word_count = len(content.split())

    # Single words / page numbers
    if word_count < 3:
        logger.info("PRE-SKIP [too_short] ({} words): {!r}", word_count, content[:80])
        return "too_short"

    # Header/footer areas (very top/bottom, short text)
    rel_y1 = bbox[3] / page_height if page_height > 0 else 1
    rel_y0 = bbox[1] / page_height if page_height > 0 else 0
    if (rel_y0 < 0.05 or rel_y1 > 0.95) and word_count < 10:
        logger.info("PRE-SKIP [header_footer] (y0={:.2f} y1={:.2f}): {!r}", rel_y0, rel_y1, content[:80])
        return "header_footer"

    # Very narrow blocks (margin annotations)
    block_width = bbox[2] - bbox[0]
    if block_width < page_width * 0.15:
        logger.info("PRE-SKIP [narrow] (w={:.0f} vs page={:.0f}, ratio={:.2f}): {!r}",
                      block_width, page_width, block_width / page_width, content[:80])
        return "narrow"

    return None


def _should_skip_merged(content: str, font_size: float,
                        body_font_size: float, bbox: dict,
                        page_width: float, page_height: float) -> str | None:
    """Post-merge filter: applied to the MERGED paragraph as a whole."""
    import re as _re
    word_count = len(content.split())

    # Too short for a useful summary
    if word_count < 10:
        return "too_short"

    # Footnotes — by content: starts with number/superscript, short explanatory text
    # e.g. "1 MINT steht für ...", "² Vgl. Müller (2020)"
    if word_count < 25 and _re.match(r"^[\d¹²³⁴⁵⁶⁷⁸⁹⁰]+[\s\)\.]\s*", content):
        return "footnote"

    # Headings: noticeably larger font AND very short (title only, no body text)
    if font_size > body_font_size + 1.0 and word_count < 12:
        return "heading"

    # Captions: "Abbildung N:", "Tabelle N:", "Figure N:", "Table N:" etc.
    if word_count < 25 and _re.match(r"^(Abbildung|Tabelle|Figure|Table|Abb\.)\s*\d", content):
        return "caption"

    # Header/footer areas
    rel_y1 = bbox["y1"] / page_height if page_height > 0 else 1
    rel_y0 = bbox["y0"] / page_height if page_height > 0 else 0
    if (rel_y0 < 0.05 or rel_y1 > 0.95) and word_count < 10:
        return "header_footer"

    # Very narrow merged block (margin annotations)
    block_width = bbox["x1"] - bbox["x0"]
    if block_width < page_width * 0.15 and word_count < 15:
        return "narrow"

    return None


def _extract_lines_flat(page_dict: dict) -> list[dict]:
    """Extract all text lines from a page as a flat list with metadata.

    Returns list of dicts with keys:
      - bbox   (tuple: x0, y0, x1, y1)
      - text   (str)
      - font_size (float, dominant font size of the line)
    """
    lines: list[dict] = []
    for block in page_dict["blocks"]:
        if block["type"] != 0:  # skip images
            continue
        for line in block["lines"]:
            text_parts = []
            size_chars: dict[float, int] = {}
            for span in line["spans"]:
                t = span["text"]
                text_parts.append(t)
                s = round(span["size"], 1)
                size_chars[s] = size_chars.get(s, 0) + len(t)
            text = "".join(text_parts).strip()
            if not text:
                continue
            font_size = max(size_chars, key=size_chars.get) if size_chars else 0.0  # type: ignore[arg-type]
            lines.append({
                "bbox": line["bbox"],
                "text": text,
                "font_size": font_size,
            })
    # Sort by vertical position (top to bottom)
    lines.sort(key=lambda ln: (ln["bbox"][1], ln["bbox"][0]))
    return lines


def _compute_median_line_gap(lines: list[dict]) -> float:
    """Compute the median vertical gap between consecutive lines on a page."""
    gaps: list[float] = []
    for i in range(1, len(lines)):
        gap = lines[i]["bbox"][1] - lines[i - 1]["bbox"][3]
        # Only consider small positive gaps (within-paragraph line spacing)
        if 0 < gap < 50:
            gaps.append(gap)
    if not gaps:
        return 5.0  # fallback
    gaps.sort()
    mid = len(gaps) // 2
    return gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2


def extract_paragraphs_with_bbox(file_path: str) -> list[dict]:
    """Extract text paragraphs with bounding boxes from a PDF.

    Uses line-level analysis: extracts all lines, computes the median
    line gap per page, and groups lines into paragraphs based on:
      1. Vertical gap > 1.5x median line gap  → new paragraph
      2. Font size change                      → new paragraph
      3. First-line indentation                → new paragraph
      4. Max length cap (1200 chars)           → new paragraph

    Each visual paragraph gets exactly 1 summary.
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

    # ── First pass: determine the body font size across the document ──
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

    _MAX_PARA_CHARS = 2500  # safety cap for truly broken PDFs; normal splitting is by gap/font/indent

    # ── Second pass: line-level paragraph detection ──
    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict")
        page_width = page.rect.width
        page_height = page.rect.height

        # ── Table detection ─────────────────────────────────────────
        table_rects: list[tuple] = []
        try:
            tables = page.find_tables()
            for table in tables.tables:
                table_rects.append(table.bbox)
            if table_rects:
                logger.info("find_tables p{}: {} tables found", page_num, len(table_rects))
        except Exception as e:
            logger.info("find_tables p{} failed: {}", page_num, e)

        def _line_in_table(line_bbox: tuple) -> int | None:
            cx = (line_bbox[0] + line_bbox[2]) / 2
            cy = (line_bbox[1] + line_bbox[3]) / 2
            for ti, tr in enumerate(table_rects):
                if tr[0] - 5 <= cx <= tr[2] + 5 and tr[1] - 5 <= cy <= tr[3] + 5:
                    return ti
            return None

        # Extract all lines flat (across block boundaries)
        all_lines = _extract_lines_flat(page_dict)

        if not all_lines:
            continue

        # TOC detection: reuse existing heuristic on block-level data
        page_blocks = []
        for block in page_dict["blocks"]:
            if block["type"] != 0:
                continue
            lines_text = []
            for line in block["lines"]:
                spans_text = "".join(span["text"] for span in line["spans"])
                lines_text.append(spans_text.strip())
            content = " ".join(ln for ln in lines_text if ln).strip()
            if content:
                page_blocks.append({"content": content, "bbox": block["bbox"]})
        if _is_toc_page(page_blocks):
            continue

        # Separate table lines from non-table lines
        table_buckets: dict[int, list[dict]] = {}
        content_lines: list[dict] = []
        for ln in all_lines:
            ti = _line_in_table(ln["bbox"])
            if ti is not None:
                table_buckets.setdefault(ti, []).append(ln)
            else:
                content_lines.append(ln)

        if not content_lines:
            # Page has only tables
            pass
        else:
            # Compute median line gap for this page
            median_gap = _compute_median_line_gap(content_lines)
            gap_threshold = median_gap * 1.5
            logger.info("p{}: {} lines, median_gap={:.1f}, threshold={:.1f}",
                        page_num, len(content_lines), median_gap, gap_threshold)

            # Determine the typical left margin (most common x0 among body-font lines)
            left_margins: dict[float, int] = {}
            for ln in content_lines:
                if abs(ln["font_size"] - body_font_size) < 1.0:
                    x0_rounded = round(ln["bbox"][0], 0)
                    left_margins[x0_rounded] = left_margins.get(x0_rounded, 0) + 1
            typical_left = max(left_margins, key=left_margins.get) if left_margins else content_lines[0]["bbox"][0]  # type: ignore[arg-type]
            indent_threshold = body_font_size * 1.5  # ~1.5 em indentation

            # ── Group lines into paragraphs ──
            grouped: list[list[dict]] = [[content_lines[0]]]

            for i in range(1, len(content_lines)):
                prev_line = content_lines[i - 1]
                curr_line = content_lines[i]

                gap = curr_line["bbox"][1] - prev_line["bbox"][3]
                font_changed = abs(curr_line["font_size"] - prev_line["font_size"]) >= 1.5
                # Indentation: current line starts notably further right than typical
                indented = (curr_line["bbox"][0] - typical_left) > indent_threshold
                # Current paragraph too long
                current_text_len = sum(len(ln["text"]) for ln in grouped[-1])
                too_long = current_text_len > _MAX_PARA_CHARS

                new_paragraph = (
                    gap > gap_threshold
                    or font_changed
                    or indented
                    or too_long
                    or gap < -5  # overlapping lines = different column/area
                )

                if new_paragraph:
                    grouped.append([curr_line])
                else:
                    grouped[-1].append(curr_line)

            # Convert grouped lines into paragraph dicts
            for idx, group in enumerate(grouped):
                content = " ".join(ln["text"] for ln in group).strip()
                font_size = max(
                    (ln["font_size"] for ln in group),
                    key=lambda fs: sum(len(ln["text"]) for ln in group if ln["font_size"] == fs),
                )
                merged_bbox = {
                    "x0": min(ln["bbox"][0] for ln in group),
                    "y0": group[0]["bbox"][1],
                    "x1": max(ln["bbox"][2] for ln in group),
                    "y1": group[-1]["bbox"][3],
                }

                skip = _should_skip_merged(
                    content, font_size, body_font_size,
                    merged_bbox, page_width, page_height,
                )
                if skip is not None:
                    logger.info("POST-SKIP [{}] p{} idx{} ({} words, fs={:.1f}): {!r}",
                                skip, page_num, idx, len(content.split()), font_size, content[:100])
                    continue

                paragraphs.append({
                    "page_number": page_num,
                    "block_index": idx,
                    "bbox": merged_bbox,
                    "content": content,
                })

        # ── Emit one paragraph per detected table ──
        for ti, lines in table_buckets.items():
            all_content = " ".join(ln["text"] for ln in lines)
            avg_font = sum(ln["font_size"] for ln in lines) / len(lines) if lines else body_font_size
            merged_bbox = {
                "x0": min(ln["bbox"][0] for ln in lines),
                "y0": lines[0]["bbox"][1],
                "x1": max(ln["bbox"][2] for ln in lines),
                "y1": lines[-1]["bbox"][3],
            }
            word_count = len(all_content.split())
            skip = _should_skip_merged(
                all_content, avg_font, body_font_size,
                merged_bbox, page_width, page_height,
            )
            if skip is None and word_count >= 10:
                paragraphs.append({
                    "page_number": page_num,
                    "block_index": 900 + ti,
                    "bbox": merged_bbox,
                    "content": all_content,
                })
            logger.info("TABLE p{} #{}: {} lines, {} words{}",
                        page_num, ti, len(lines), word_count,
                        f" (skipped: {skip})" if skip else "")

    doc.close()

    # ── Deduplicate: merge paragraphs on same page with overlapping bboxes ──
    deduped: list[dict] = []
    for p in paragraphs:
        merged_with = None
        for d in deduped:
            if d["page_number"] != p["page_number"]:
                continue
            overlap_y0 = max(d["bbox"]["y0"], p["bbox"]["y0"])
            overlap_y1 = min(d["bbox"]["y1"], p["bbox"]["y1"])
            if overlap_y1 <= overlap_y0:
                continue
            overlap_h = overlap_y1 - overlap_y0
            smaller_h = min(d["bbox"]["y1"] - d["bbox"]["y0"], p["bbox"]["y1"] - p["bbox"]["y0"])
            if smaller_h > 0 and overlap_h / smaller_h > 0.5:
                merged_with = d
                break
        if merged_with is not None:
            if len(p["content"]) > len(merged_with["content"]):
                merged_with["content"] = p["content"]
                merged_with["bbox"] = {
                    "x0": min(merged_with["bbox"]["x0"], p["bbox"]["x0"]),
                    "y0": min(merged_with["bbox"]["y0"], p["bbox"]["y0"]),
                    "x1": max(merged_with["bbox"]["x1"], p["bbox"]["x1"]),
                    "y1": max(merged_with["bbox"]["y1"], p["bbox"]["y1"]),
                }
            logger.info("DEDUP: merged overlapping paragraphs on p{}", p["page_number"])
        else:
            deduped.append(p)

    # ── Merge short fragments ──
    # 1. Page-break fragments: first paragraph on a new page starts mid-sentence
    #    (lowercase) → merge with last paragraph of previous page.
    # 2. Short continuation fragments: very short paragraphs (< 20 words) starting
    #    with lowercase on the SAME page → likely a split artifact, merge with previous.
    import re as _re
    final: list[dict] = []
    for p in deduped:
        if not final:
            final.append(p)
            continue
        prev = final[-1]
        first_alpha = _re.search(r"[a-zA-ZäöüÄÖÜ]", p["content"])
        starts_lower = first_alpha is not None and first_alpha.group().islower()
        word_count = len(p["content"].split())

        # Page-break fragment: different page, lowercase start, short
        is_page_fragment = (
            p["page_number"] != prev["page_number"]
            and starts_lower
            and word_count < 30
        )
        # Same-page short fragment: lowercase start, very short (1-2 sentences)
        is_short_fragment = (
            p["page_number"] == prev["page_number"]
            and starts_lower
            and word_count < 20
        )

        if is_page_fragment or is_short_fragment:
            kind = "PAGE-MERGE" if is_page_fragment else "SHORT-MERGE"
            logger.info("{} p{} → prev p{}: {!r}", kind, p["page_number"], prev["page_number"], p["content"][:80])
            prev["content"] += " " + p["content"]
            # Extend bbox if same page
            if p["page_number"] == prev["page_number"]:
                prev["bbox"] = {
                    "x0": min(prev["bbox"]["x0"], p["bbox"]["x0"]),
                    "y0": min(prev["bbox"]["y0"], p["bbox"]["y0"]),
                    "x1": max(prev["bbox"]["x1"], p["bbox"]["x1"]),
                    "y1": max(prev["bbox"]["y1"], p["bbox"]["y1"]),
                }
        else:
            final.append(p)

    logger.info("Paragraph extraction done: {} paragraphs ({} before dedup, {} before page-merge)",
                len(final), len(paragraphs), len(deduped))
    for i, p in enumerate(final):
        logger.info("PARA[{}] p{}: {!r}", i, p["page_number"], p["content"][:120])
    return final


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
