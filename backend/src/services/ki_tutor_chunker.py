"""Document chunker for KI Tutor – extracts text chunks from PDF, DOCX, PPTX, TXT, and MD files."""

_CHUNK_SIZE = 1000
_OVERLAP = 100


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
    ft = file_type.lower().lstrip(".")
    if ft == "pdf":
        return _extract_pdf(file_path)
    if ft == "docx":
        return _extract_docx(file_path)
    if ft == "pptx":
        return _extract_pptx(file_path)
    if ft in ("txt", "md"):
        return _extract_text(file_path)
    raise ValueError(f"Unsupported file_type: {file_type!r}")


def get_page_count(file_path: str, file_type: str) -> int:
    """Return the number of logical pages / chunks in a document."""
    return len(extract_chunks(file_path, file_type))


# ── Format-specific extractors ────────────────────────────────────────────────

def _extract_pdf(file_path: str) -> list[dict]:
    import fitz  # PyMuPDF
    chunks: list[dict] = []
    doc = fitz.open(file_path)
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text().strip()
        if text:
            chunks.append({"page_number": page_num, "content": text})
    doc.close()
    if not chunks:
        raise ValueError(
            "Das PDF enthält keinen lesbaren Text. "
            "Gescannte PDFs werden aktuell nicht unterstützt. "
            "Bitte konvertiere das PDF zuerst mit einem OCR-Tool (z.B. Adobe Acrobat oder online unter smallpdf.com)."
        )
    return chunks


def _extract_docx(file_path: str) -> list[dict]:
    from docx import Document
    doc = Document(file_path)
    chunks: list[dict] = []
    current = ""
    page_number = 1

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if len(current) + len(text) + 1 > _CHUNK_SIZE:
            chunks.append({"page_number": page_number, "content": current or "[Leere Seite]"})
            page_number += 1
            current = text
        else:
            current = (current + " " + text).strip() if current else text

    # flush last chunk
    if current or not chunks:
        chunks.append({"page_number": page_number, "content": current or "[Leere Seite]"})

    return chunks


def _extract_pptx(file_path: str) -> list[dict]:
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
        content = " ".join(parts).strip() or "[Leere Seite]"
        chunks.append({"page_number": slide_num, "content": content})
    return chunks


def _extract_text(file_path: str) -> list[dict]:
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    if not text.strip():
        return [{"page_number": 1, "content": "[Leere Seite]"}]

    chunks: list[dict] = []
    start = 0
    page_number = 1
    while start < len(text):
        end = start + _CHUNK_SIZE
        chunk = text[start:end].strip() or "[Leere Seite]"
        chunks.append({"page_number": page_number, "content": chunk})
        page_number += 1
        start = end - _OVERLAP  # overlap with previous chunk
        if start >= len(text):
            break

    return chunks
