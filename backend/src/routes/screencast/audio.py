"""Audio-Download-Endpoints: Einzel-Slide-MP3 und ZIP-Bundle aller Folien."""

import zipfile
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from src.dependencies import get_current_user
from src.features.jobs.repository import get_job
from src.i18n import get_locale, t
from src.storage import get_all_audio_slides, get_audio_slide, get_audio_slide_count, get_job_file

router = APIRouter(tags=["screencast: audio"])


def _resolve_user_id(audio_id: str, current_user: dict, locale: str = "de") -> int:
    """Resolve the owning user_id for an audio_id (which is a job_uuid) and confirm
    the caller owns that job. Without the ownership check any authenticated user
    could download another user's slide audio by its job_uuid (IDOR)."""
    job = get_job(audio_id)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("audio.notFound", locale))
    return job["user_id"]


@router.get("/screencast/audio/{audio_id}/zip")
def download_all_slide_audio_zip(
    audio_id: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download all per-slide MP3s as a single ZIP archive."""
    user_id = _resolve_user_id(audio_id, current_user, locale)
    slides = get_all_audio_slides(user_id, audio_id)
    if not slides:
        raise HTTPException(status_code=404, detail=t("audio.notFound", locale))

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
def download_slide_audio(
    audio_id: str,
    slide_index: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download a single per-slide MP3 from the render audio cache (file-based)."""
    user_id = _resolve_user_id(audio_id, current_user, locale)
    count = get_audio_slide_count(user_id, audio_id)
    if count == 0:
        raise HTTPException(status_code=404, detail=t("audio.notFound", locale))
    if slide_index < 0 or slide_index >= count:
        raise HTTPException(status_code=404, detail=t("screencast.slideNotFound", locale, slide=slide_index + 1))

    audio_bytes = get_audio_slide(user_id, audio_id, slide_index)
    if audio_bytes is None:
        raise HTTPException(status_code=404, detail=t("screencast.slideNotFound", locale, slide=slide_index + 1))

    filename = f"slide_{slide_index + 1:02d}.mp3"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/screencast/{job_uuid}/vorschau/{folie}")
def vorschau_folie(
    job_uuid: str,
    folie: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Der Ton einer einzelnen Folie, schon waehrend der Rest noch vertont wird."""
    user_id = _resolve_user_id(job_uuid, current_user, locale)
    if folie < 0 or folie > 999:
        raise HTTPException(status_code=404, detail=t("screencast.slideNotFound", locale, slide=folie + 1))
    # Waehrend des Laufs liegt der Ton im Vorrat, nach dem Erfolg im audio-Ordner.
    for name in (f"render_cache/slide_{folie:03d}.mp3", f"audio/slide_{folie:03d}.mp3"):
        try:
            data = get_job_file(user_id, job_uuid, name)
        except Exception:
            continue
        return Response(content=data, media_type="audio/mpeg",
                        headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404, detail=t("screencast.slideNotFound", locale, slide=folie + 1))
