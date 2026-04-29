"""Audio-Download-Endpoints: Einzel-Slide-MP3 und ZIP-Bundle aller Folien."""

import zipfile
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.features.jobs.repository import get_job
from src.storage import get_all_audio_slides, get_audio_slide, get_audio_slide_count

router = APIRouter(tags=["screencast: audio"])


def _resolve_user_id(audio_id: str) -> int:
    """Resolve the owning user_id for an audio_id (which is a job_uuid)."""
    job = get_job(audio_id)
    if not job:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    return job["user_id"]


@router.get("/screencast/audio/{audio_id}/zip")
async def download_all_slide_audio_zip(audio_id: str):
    """Download all per-slide MP3s as a single ZIP archive."""
    user_id = _resolve_user_id(audio_id)
    slides = get_all_audio_slides(user_id, audio_id)
    if not slides:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")

    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for filename, data in slides:
            zf.writestr(filename, data)
    buf.seek(0)
    zip_bytes = buf.read()

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Length": str(len(zip_bytes)),
            "Content-Disposition": 'attachment; filename="folien_audio.zip"',
        },
    )


@router.get("/screencast/audio/{audio_id}/{slide_index}")
async def download_slide_audio(audio_id: str, slide_index: int):
    """Download a single per-slide MP3 from the render audio cache (file-based)."""
    user_id = _resolve_user_id(audio_id)
    count = get_audio_slide_count(user_id, audio_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    if slide_index < 0 or slide_index >= count:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    audio_bytes = get_audio_slide(user_id, audio_id, slide_index)
    if audio_bytes is None:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    filename = f"slide_{slide_index + 1:02d}.mp3"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
