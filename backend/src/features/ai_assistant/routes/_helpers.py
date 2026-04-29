"""Shared helpers for KI-Assistent routes."""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from loguru import logger
from langfuse.decorators import langfuse_context

from src import database as db
from src.storage import USE_S3

def _trace_kisski(kisski, name: str) -> None:
    """Update current Langfuse observation with provider metadata."""
    langfuse_context.update_current_observation(
        metadata={"provider": kisski._provider, "base_url": kisski._base_url, "model": kisski._model},
        name=name,
    )

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"}
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (audio/video can be large)

def _convert_office_to_pdf(data: bytes, ext: str) -> bytes:
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
            raise HTTPException(status_code=500, detail="Konvertierung nach PDF fehlgeschlagen")
        return pdf_path.read_bytes()

def _mp4_faststart(data: bytes) -> bytes:
    """Remux MP4 so the moov atom sits at the file start (progressive playback).

    Without this, browsers must download to near end-of-file before playback
    starts — painful for multi-hour recordings. ffmpeg -c copy avoids re-encoding.
    Falls back to the original bytes on any failure.
    """
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

def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for citation references."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


_TRANSCRIPT_LINE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)"
)


def _parse_ts(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


def _load_transcript_segments(source: dict) -> list[dict]:
    """Load Whisper segments from the _transcript.txt artifact next to a media source.

    Returns list of {"start": float, "end": float, "text": str} or [] on any error.
    """
    file_path = source.get("file_path") or ""
    if not file_path:
        return []
    base_key = file_path.rsplit(".", 1)[0]
    transcript_key = base_key + "_transcript.txt"
    try:
        from src.storage import get_file
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


def _enrich_media_content(chunk: dict, segments: list[dict]) -> str:
    """Inject inline `(MM:SS)` markers at segment boundaries within a media chunk's content.

    Gives the LLM finer-grained timestamps to cite than just the chunk's start_time,
    so answers about content mid-chunk can reference the correct moment.
    Falls back to the original content if segments can't be aligned.
    """
    content = chunk.get("content") or ""
    if chunk.get("start_time") is None or chunk.get("end_time") is None or not segments:
        return content
    tol = 0.5
    relevant = [
        s for s in segments
        if chunk["start_time"] - tol <= s["start"] <= chunk["end_time"] + tol
    ]
    if len(relevant) < 2:
        return content
    return " ".join(f"({_format_timestamp(s['start'])}) {s['text']}" for s in relevant)

def _require_own_module(module_uuid: str, user_id: int) -> dict:
    module = db.get_aia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if module["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    return module

def _save_source_file(user_id: int, module_uuid: str, source_uuid: str, ext: str, data: bytes) -> str:
    from src.storage import aia_source_key
    key = aia_source_key(user_id, module_uuid, source_uuid, ext)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)

def _delete_source_files_for_module(module: dict) -> None:
    sources = db.get_aia_sources_by_module(module["id"])
    for source in sources:
        try:
            delete_file(source["file_path"])
        except Exception as e:
            logger.warning("KI Tutor: could not delete file {}: {}", source["file_path"], e)

def _resolve_source_ids(module: dict, source_uuids: list[str], max_count: int = 3) -> list[int]:
    """Resolve source UUIDs to DB IDs, enforce max count."""
    if len(source_uuids) > max_count:
        raise HTTPException(status_code=400, detail=f"Maximal {max_count} Sources erlaubt")
    ids = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source and source["module_id"] == module["id"] and source["status"] == "ready":
            ids.append(source["id"])
    if not ids:
        raise HTTPException(status_code=400, detail="Keine gültigen Sources ausgewählt")
    return ids

def _term_appears_in_text(term: str, text_lower: str) -> bool:
    """Check if term appears literally or as a lemma/stem prefix in the text.
    Allows LLM to return Grundform (e.g. "erhöhen") when text has inflected
    form ("erhöht", "zu erhöhen"). Rejects terms that share only a weak prefix.
    """
    t = term.lower().strip()
    if not t:
        return False
    if t in text_lower:
        return True
    stem_len = max(5, len(t) * 3 // 4)
    stem = t[:stem_len]
    return bool(re.search(r"\b" + re.escape(stem), text_lower))

