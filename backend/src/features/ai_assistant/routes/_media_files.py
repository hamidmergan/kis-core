"""Uploaded sources: office conversion, faststart remux, page count, transcript segments."""

import subprocess
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src.i18n import DEFAULT_LOCALE, t
from src.services.aia_transcript_offsets import TranscriptIndex
from src.storage import aia_transcript_key, get_file

from ._text import _TRANSCRIPT_LINE, _format_timestamp, _parse_ts


_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}


_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm", ".youtube"}


# What the browser is told a stored source is, by its extension.
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".webm": "video/webm",
}


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
