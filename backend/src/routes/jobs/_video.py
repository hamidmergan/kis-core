"""Playback route for the finished video: inline, with chapter marks."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.storage import USE_S3, stream_s3_object

router = APIRouter()


@router.get("/{job_uuid}/video")
def stream_job_video(
    job_uuid: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The result for viewing instead of downloading."""
    job = db.get_job(job_uuid)
    # The same answer for foreign and missing, otherwise jobs could be probed.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["status"] != "success" or not job["result_path"]:
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))

    pfad = job["result_path"]
    if Path(pfad).suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))

    if USE_S3:
        bereich = request.headers.get("range")
        strom, laenge, ausschnitt = stream_s3_object(pfad, bereich)
        kopf = {
            "Content-Disposition": 'inline; filename="screencast.mp4"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(laenge),
            "Cache-Control": "private, max-age=3600",
        }
        if ausschnitt:
            kopf["Content-Range"] = ausschnitt
        return StreamingResponse(strom, status_code=206 if bereich and ausschnitt else 200,
                                 media_type="video/mp4", headers=kopf)

    # FileResponse answers Range itself, that saves the local special case.
    return FileResponse(path=pfad, media_type="video/mp4", filename="screencast.mp4",
                        content_disposition_type="inline",
                        headers={"Cache-Control": "private, max-age=3600"})
