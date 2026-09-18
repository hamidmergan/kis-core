"""Download-Endpunkte: /download (Result-File), /pptx (Translated PPTX), /docx (Word), /bundle (ZIP)."""

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.limits import BUNDLE_INCLUDE_AUDIO
from src.storage import (
    get_file,
    get_job_file,
    job_file_exists,
    load_result_meta,
)

from src.services.screencast.infodatei import baue_info, sprach_wort

from src.routes.jobs._shared import _CONTENT_TYPES


router = APIRouter()


@router.get("/{job_uuid}/download")
def download_job_result(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download the binary result file (MP4 or MP3) for a completed job."""
    job = db.get_job(job_uuid)
    # Owner-only: a foreign job_uuid must not download another user's result file.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["status"] != "success":
        raise HTTPException(status_code=404, detail=t("job.notCompleted", locale))
    if not job["result_path"]:
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))

    result_path_str = job["result_path"]
    try:
        data = get_file(result_path_str)
    except Exception:
        raise HTTPException(status_code=404, detail=t("job.fileExpired", locale))

    ext = Path(result_path_str).suffix.lower()
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


@router.get("/{job_uuid}/subtitles")
def download_job_subtitles(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The subtitle track as VTT so the browser player can offer CC."""
    job = db.get_job(job_uuid)
    # Owner only, otherwise other people's UUIDs could be read along.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))

    try:
        data = get_job_file(job["user_id"], job_uuid, "untertitel.vtt")
    except Exception:
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))

    return StreamingResponse(
        iter([data]),
        media_type="text/vtt; charset=utf-8",
        headers={"Content-Length": str(len(data))},
    )


@router.get("/{job_uuid}/pptx")
def download_job_pptx(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download the translated PPTX for a screencast render job."""
    job = db.get_job(job_uuid)
    # Owner-only: a foreign job_uuid must not download another user's PPTX.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))

    # Works for screencast_translate (has result_path); translated.pptx is in the job folder.
    try:
        data = get_job_file(job["user_id"], job_uuid, "translated.pptx")
    except Exception as e:
        logger.error("PPTX download failed for job {}: {}", job_uuid, e)
        raise HTTPException(status_code=404, detail=t("screencast.pptxExpired", locale))

    pptx_filename = _resolve_artifact_filename(job, ext="pptx")

    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{pptx_filename}"',
        },
    )


@router.get("/{job_uuid}/docx")
def download_job_docx(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download the Word version of a completed summary job, alongside its Markdown result."""
    job = db.get_job(job_uuid)
    # Owner-only: a foreign job_uuid must not download another user's Word file.
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))

    try:
        data = get_job_file(job["user_id"], job_uuid, "output.docx")
    except Exception as e:
        logger.error("DOCX download failed for job {}: {}", job_uuid, e)
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))

    docx_filename = Path(job["result_filename"] or "summary.md").stem + ".docx"

    return StreamingResponse(
        iter([data]),
        media_type=_CONTENT_TYPES[".docx"],
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{docx_filename}"',
        },
    )


def _resolve_artifact_filename(job: dict, ext: str) -> str:
    """The visible file name of a result."""
    meta = load_result_meta(job["user_id"], job["job_uuid"]) or {}
    stem = (
        meta.get("result_stem")
        or meta.get("translated_stem")
        or Path(job.get("original_filename") or "screencast").stem
        or "screencast"
    )
    return f"{stem}.{ext.lstrip('.')}"


class _ZipStreamWriter:
    """A buffer for zipfile that is drained in pieces and keeps memory small."""

    def __init__(self):
        self._buf = io.BytesIO()
        self._base = 0  # absolute offset of the buffer start within the archive

    def write(self, data: bytes) -> int:
        return self._buf.write(data)

    def flush(self):
        pass

    def tell(self) -> int:
        return self._base + self._buf.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        # zipfile only seeks back within the current entry.
        if whence == 0:
            offset -= self._base
        self._buf.seek(offset, whence)
        return self._base + self._buf.tell()

    def drain(self) -> bytes:
        """Return everything buffered since the last drain and reset the buffer."""
        chunk = self._buf.getvalue()
        self._base += len(chunk)
        self._buf = io.BytesIO()
        return chunk

    def close(self):
        pass


def _streaming_zip_bundle(
    user_id: int, job_uuid: str, stem: str, audio_count: int,
    ziel_wort: str = "uebersetzt", info_text: str = "",
):
    """Generator that yields ZIP data entry-by-entry without buffering the whole archive."""
    stream = _ZipStreamWriter()
    zf = zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_STORED)

    def _add_and_yield(arcname: str, data: bytes):
        zf.writestr(arcname, data)
        return stream.drain()

    # MP4
    try:
        mp4_data = get_job_file(user_id, job_uuid, "output.mp4")
        yield _add_and_yield(f"{stem}_video.mp4", mp4_data)
        del mp4_data
    except Exception:
        pass

    # Slide audios
    if BUNDLE_INCLUDE_AUDIO:
        for i in range(audio_count):
            try:
                audio_data = get_job_file(user_id, job_uuid, f"audio/slide_{i:03d}.mp3")
                yield _add_and_yield(f"Audios/folie_{i + 1:03d}.mp3", audio_data)
            except Exception:
                pass

    # If there was a translation, the file carries the target language in its name.
    hat_original = job_file_exists(user_id, job_uuid, "original.pptx")
    pptx_name = "corrected.pptx" if job_file_exists(user_id, job_uuid, "corrected.pptx") else "translated.pptx"
    try:
        pptx_data = get_job_file(user_id, job_uuid, pptx_name)
        endung = ziel_wort if hat_original else "original"
        yield _add_and_yield(f"{stem}_{endung}.pptx", pptx_data)
    except Exception:
        pass

    # The uploaded file before the translation.
    try:
        original_data = get_job_file(user_id, job_uuid, "original.pptx")
        yield _add_and_yield(f"{stem}_original.pptx", original_data)
    except Exception:
        pass

    # Untertitel
    try:
        vtt_data = get_job_file(user_id, job_uuid, "untertitel.vtt")
        yield _add_and_yield(f"{stem}_untertitel.vtt", vtt_data)
    except Exception:
        pass

    # Sprechtexte
    for script_file in ("accepted_scripts.json", "user_scripts.json", "scripts.txt"):
        try:
            script_data = get_job_file(user_id, job_uuid, script_file)
            yield _add_and_yield(f"{stem}_sprechtexte.json", script_data)
            break
        except Exception:
            continue

    # What is inside and what it was made with.
    if info_text:
        yield _add_and_yield(f"{stem}_info.txt", info_text.encode("utf-8"))

    # Finalize ZIP (central directory + end record)
    zf.close()
    yield stream.drain()


@router.get("/{job_uuid}/bundle")
def download_job_bundle(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Download a ZIP bundle containing MP4, slide audios, PPTX and script for a screencast job."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job.get("user_id") != current_user.get("user_id"):
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    user_id = job["user_id"]
    meta = load_result_meta(user_id, job_uuid) or {}
    audio_count = int(meta.get("audio_count", 0))
    stem = (
        meta.get("result_stem")
        or meta.get("translated_stem")
        or Path(job.get("original_filename") or "screencast").stem
        or "screencast"
    )
    zip_filename = f"{stem}.zip"
    # Providers, models and durations appear only in an admin's archive.
    info_text = baue_info(job, meta, mit_technik=is_admin_user(current_user))

    return StreamingResponse(
        _streaming_zip_bundle(
            user_id, job_uuid, stem, audio_count,
            sprach_wort(meta.get("target_lang", "")), info_text,
        ),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
