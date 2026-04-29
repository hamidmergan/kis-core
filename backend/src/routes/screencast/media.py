"""Media-Endpoints: Slide-Bilder nachrendern, PPTX-Download."""

import base64
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.services.screencast import convert_slides_to_images_async
from src.storage import get_job_file, load_result_json

router = APIRouter(tags=["screencast: media"])


@router.get("/screencast/{job_uuid}/images")
async def get_job_slide_images(job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Return slide images (base64) for a translate/demo job — rendered from saved PPTX."""
    if not re.match(r"^[a-f0-9]{32}$", job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige Job-UUID")
    job = db.get_job(job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    # Try to load from result JSON first (fast path for jobs that stored images)
    if job.get("result_path"):
        try:
            result_data = load_result_json(job["result_path"])
            imgs = result_data.get("slide_images", [])
            if imgs:
                return {"slide_images": imgs}
        except Exception:
            pass

    # Fallback: re-render from saved translated.pptx
    pptx_bytes: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            pptx_bytes = get_job_file(job["user_id"], job_uuid, filename)
            break
        except Exception:
            pass
    if not pptx_bytes:
        raise HTTPException(status_code=404, detail="PPTX nicht mehr verfügbar")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pptx_path = tmp / "presentation.pptx"
        pptx_path.write_bytes(pptx_bytes)
        img_dir = tmp / "images"
        img_dir.mkdir()
        try:
            slide_image_paths = await convert_slides_to_images_async(pptx_path, img_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

    return {"slide_images": slide_images_b64}


@router.get("/screencast/pptx/{translate_job_uuid}")
async def download_pptx_file(translate_job_uuid: str, current_user: dict = Depends(get_current_user)):
    """Download translated/corrected PPTX from job folder."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail="Ungültige job UUID")
    job = db.get_job(translate_job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diesen Job")
    data: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            data = get_job_file(job["user_id"], translate_job_uuid, filename)
            break
        except Exception:
            pass
    if data is None:
        raise HTTPException(status_code=404, detail="PPTX nicht gefunden")
    logger.info("Serving PPTX for job={} ({} bytes)", translate_job_uuid, len(data))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": 'attachment; filename="translated.pptx"',
        },
    )
