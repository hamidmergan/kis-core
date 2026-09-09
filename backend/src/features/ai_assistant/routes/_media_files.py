"""Uploaded sources: office conversion, faststart remux, page count, transcript segments."""

import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src.i18n import DEFAULT_LOCALE, t
from src.services.aia_transcript_offsets import TranscriptIndex
from src.storage import aia_transcript_key, get_file

from ._text import _TRANSCRIPT_LINE, _format_timestamp, _parse_ts


_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}


_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm", ".youtube"}


_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (audio/video can be large)


def _convert_office_to_pdf(data: bytes, ext: str, locale: str = DEFAULT_LOCALE) -> bytes:
    """Convert .docx or .pptx to PDF using LibreOffice. Raises HTTPException on failure."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / f"input{ext}"
        src.write_bytes(data)
        result = subprocess.run(
            ["libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", str(tmp), str(src)],
            capture_output=True, text=True, timeout=180,
        )
        pdf_path = tmp / "input.pdf"
        if not pdf_path.exists():
            logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
            raise HTTPException(status_code=500, detail=t("ai.source.pdfConversionFailed", locale))
        return pdf_path.read_bytes()


def _mp4_faststart(data: bytes) -> bytes:
    """Remuxes MP4 so the browser can play right away instead of downloading first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / "input.mp4"
        dst = tmp / "output.mp4"
        src.write_bytes(data)
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                 "-c", "copy", "-movflags", "+faststart", str(dst)],
                capture_output=True, text=True, timeout=600,
            )
        except Exception as e:
            logger.warning("KI Tutor: faststart remux exception: {}", e)
            return data
        if result.returncode != 0 or not dst.exists():
            logger.warning("KI Tutor: faststart remux failed (rc={}): {}", result.returncode, result.stderr[:200])
            return data
        return dst.read_bytes()


def _count_pages(ext: str, data: bytes) -> int | None:
    """Return page/slide count for PDF/PPTX, None for formats without a meaningful page count."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(data)
            count = len(doc)
            doc.close()
            return count
        if ext == ".pptx":
            import io
            from pptx import Presentation
            return len(Presentation(io.BytesIO(data)).slides)
    except Exception as e:
        logger.warning("KI Tutor: page count failed for {}: {}", ext, e)
    return None


def _convert_office_to_pdf_path(src_path: str, ext: str, out_dir: str, locale: str = DEFAULT_LOCALE) -> str:
    """Converts a docx, pptx or html file to PDF via LibreOffice."""
    result = subprocess.run(
        ["libreoffice", "--headless", "--norestore", "--convert-to", "pdf",
         "--outdir", out_dir, src_path],
        capture_output=True, text=True, timeout=180,
    )
    pdf_path = Path(out_dir) / (Path(src_path).stem + ".pdf")
    if not pdf_path.exists():
        logger.error("LibreOffice conversion failed (rc={}): {}", result.returncode, result.stderr[:300])
        raise HTTPException(status_code=500, detail=t("ai.source.pdfConversionFailed", locale))
    return str(pdf_path)


def _mp4_faststart_path(src_path: str, out_dir: str) -> str:
    """Remuxes an MP4 file on disk for immediate playback."""
    dst = Path(out_dir) / "faststart.mp4"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path,
             "-c", "copy", "-movflags", "+faststart", str(dst)],
            capture_output=True, text=True, timeout=600,
        )
    except Exception as e:
        logger.warning("KI Tutor: faststart remux exception: {}", e)
        return src_path
    if result.returncode != 0 or not dst.exists():
        logger.warning("KI Tutor: faststart remux failed (rc={}): {}", result.returncode, result.stderr[:200])
        return src_path
    return str(dst)


def _count_pages_path(ext: str, path: str) -> int | None:
    """Page/slide count for a PDF/PPTX on disk, None for other formats."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path)
            count = len(doc)
            doc.close()
            return count
        if ext == ".pptx":
            from pptx import Presentation
            return len(Presentation(path).slides)
    except Exception as e:
        logger.warning("KI Tutor: page count failed for {}: {}", ext, e)
    return None


def _load_transcript_segments(source: dict) -> list[dict]:
    """Loads the Whisper segments from the transcript file next to a media source."""
    file_path = source.get("file_path") or ""
    if not file_path:
        return []
    transcript_key = aia_transcript_key(file_path)
    try:
        text = get_file(transcript_key).decode("utf-8")
    except Exception as e:
        logger.debug("transcript artifact unavailable for source {}: {}", source.get("id"), e)
        return []
    segments: list[dict] = []
    for line in text.splitlines():
        m = _TRANSCRIPT_LINE.match(line.strip())
        if m:
            segments.append({
                "start": _parse_ts(m.group(1)),
                "end": _parse_ts(m.group(2)),
                "text": m.group(3).strip(),
            })
    return segments


def _chunk_segments(chunk: dict, segments: list[dict]) -> list[dict]:
    """The Whisper segments of a media chunk, matched up by their order."""
    if chunk.get("start_time") is None or not segments:
        return []
    return TranscriptIndex(segments).segments_of(chunk)


def _enrich_media_content(chunk: dict, segments: list[dict]) -> str:
    """Puts timestamps on the segment boundaries inside a media chunk."""
    content = chunk.get("content") or ""
    relevant = _chunk_segments(chunk, segments)
    if len(relevant) < 2:
        return content
    return " ".join(f"({_format_timestamp(s['start'])}) {s['text']}" for s in relevant)
