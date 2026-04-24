"""Download-Endpunkte: /download (Result-File), /pptx (Translated PPTX), /bundle (ZIP)."""

import base64
import io
import json as json_lib
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.limits import BUNDLE_INCLUDE_AUDIO
from src.storage import (
    _job_folder_name,
    get_file,
    get_job_file,
    job_file_exists,
    load_result_meta,
)

from src.routes.jobs._shared import _CONTENT_TYPES


router = APIRouter()


@router.get("/{job_uuid}/download")
async def download_job_result(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the binary result file (MP4 or MP3) for a completed job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job["status"] != "success":
        raise HTTPException(status_code=404, detail="Job noch nicht abgeschlossen")
    if not job["result_path"]:
        raise HTTPException(status_code=404, detail="Kein Download für diesen Job")

    result_path_str = job["result_path"]
    try:
        data = get_file(result_path_str)
    except Exception:
        raise HTTPException(status_code=404, detail="Datei nicht mehr vorhanden (abgelaufen)")

    ext = Path(result_path_str).suffix.lower()

    # Multi-image JSON → ZIP (or single PNG direct)
    if ext == ".json" and job["tool"] == "image_generate":
        try:
            images_data = json_lib.loads(data)["images"]
        except Exception:
            raise HTTPException(status_code=500, detail="Bilddaten konnten nicht gelesen werden")

        if len(images_data) == 1:
            img_bytes = base64.b64decode(images_data[0]["b64_json"])
            png_filename = images_data[0].get("filename", "image.png")
            return StreamingResponse(
                iter([img_bytes]),
                media_type="image/png",
                headers={
                    "Content-Length": str(len(img_bytes)),
                    "Content-Disposition": f'attachment; filename="{png_filename}"',
                },
            )
        else:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for img in images_data:
                    img_bytes = base64.b64decode(img["b64_json"])
                    zf.writestr(img.get("filename", "image.png"), img_bytes)
            zip_bytes = buf.getvalue()
            base_name = (job["result_filename"] or "images").removesuffix(".json")
            zip_filename = f"{base_name}.zip"
            return StreamingResponse(
                iter([zip_bytes]),
                media_type="application/zip",
                headers={
                    "Content-Length": str(len(zip_bytes)),
                    "Content-Disposition": f'attachment; filename="{zip_filename}"',
                },
            )

    content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
    filename = job["result_filename"] or Path(result_path_str).name

    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{job_uuid}/pptx")
async def download_job_pptx(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download the translated PPTX for a screencast render job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    # Use get_job_file so the folder name (YYYY-MM-DD_HH-MM-SS_{uuid}) is resolved
    # correctly from the DB — works for both screencast_translate (has result_path)
    # and screencast_demo_render (result_path is NULL, but translated.pptx is in folder).
    try:
        data = get_job_file(job_uuid, "translated.pptx")
    except Exception as e:
        logger.error("PPTX download failed for job {}: {}", job_uuid, e)
        raise HTTPException(status_code=404, detail="PPTX nicht mehr vorhanden (abgelaufen)")

    original = job["original_filename"] or "screencast.pptx"
    pptx_filename = f"{Path(original).stem}.pptx"

    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{pptx_filename}"',
        },
    )


class _ZipStreamWriter:
    """File-like object that collects written bytes into chunks for streaming."""

    def __init__(self):
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        return self._buf.write(data)

    def flush(self):
        pass

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf.seek(offset, whence)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def close(self):
        pass


def _streaming_zip_bundle(job_uuid: str, folder_name: str, audio_count: int):
    """Generator that yields ZIP data file-by-file without buffering everything first."""
    stream = _ZipStreamWriter()
    zf = zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED)

    def _add_and_yield(arcname: str, data: bytes):
        pos_before = stream.tell()
        zf.writestr(arcname, data)
        pos_after = stream.tell()
        stream.seek(pos_before)
        chunk = stream.read(pos_after - pos_before)
        return chunk

    # MP4
    try:
        mp4_data = get_job_file(job_uuid, "output.mp4")
        yield _add_and_yield(f"{folder_name}.mp4", mp4_data)
        del mp4_data
    except Exception:
        pass

    # Slide audios
    if BUNDLE_INCLUDE_AUDIO:
        for i in range(audio_count):
            try:
                audio_data = get_job_file(job_uuid, f"audio/slide_{i:03d}.mp3")
                yield _add_and_yield(f"Audios/slide_{i + 1:03d}.mp3", audio_data)
            except Exception:
                pass

    # PPTX
    pptx_name = "corrected.pptx" if job_file_exists(job_uuid, "corrected.pptx") else "translated.pptx"
    try:
        pptx_data = get_job_file(job_uuid, pptx_name)
        yield _add_and_yield(f"{folder_name}.pptx", pptx_data)
    except Exception:
        pass

    # Script
    for script_file in ("accepted_scripts.json", "user_scripts.json", "scripts.txt"):
        try:
            script_data = get_job_file(job_uuid, script_file)
            yield _add_and_yield(script_file, script_data)
            break
        except Exception:
            continue

    # Finalize ZIP (central directory)
    pos_before = stream.tell()
    zf.close()
    pos_after = stream.tell()
    stream.seek(pos_before)
    yield stream.read(pos_after - pos_before)


@router.get("/{job_uuid}/bundle")
async def download_job_bundle(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a ZIP bundle containing MP4, slide audios, PPTX and script for a screencast job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    if job.get("user_id") != current_user.get("user_id"):
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    folder_name = _job_folder_name(job_uuid)
    meta = load_result_meta(job_uuid) or {}
    audio_count = int(meta.get("audio_count", 0))
    zip_filename = f"{folder_name}.zip"

    return StreamingResponse(
        _streaming_zip_bundle(job_uuid, folder_name, audio_count),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
