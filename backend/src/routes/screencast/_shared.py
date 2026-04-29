"""Shared helpers for all screencast routes: upload validation, translation-service factory,
prerender task, script-generation locks, job-tool list."""

import asyncio
import json
import tempfile
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src.dependencies import get_deepl_client
from src.services.glossary import GlossaryService
from src.features.jobs.repository import get_job
from src.services.screencast import IMAGE_TMP_DIR, pptx_to_images
from src.services.translation import TranslationService
from src.storage import get_job_file
from src.utils.file_validation import SCREENCAST_EXTENSIONS

# Job tools that count toward the screencast in the queue/limit calculation
SCREENCAST_TOOLS = ["screencast_translate", "screencast_render", "screencast_demo_render"]

# Per-UUID lock: prevents parallel script generation for the same job
_script_gen_locks: dict[str, asyncio.Lock] = {}


def get_script_gen_lock(uuid_key: str) -> asyncio.Lock:
    """Return the lock for a job (creates it on demand)."""
    if uuid_key not in _script_gen_locks:
        _script_gen_locks[uuid_key] = asyncio.Lock()
    return _script_gen_locks[uuid_key]


def validate_upload(filename: str | None) -> str:
    """Validate filename/extension of a PPTX upload and return the extension."""
    if not filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")
    ext = Path(filename).suffix.lower()
    if ext not in SCREENCAST_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur .pptx erlaubt")
    return ext


def build_translation_service(glossary_json: str = "") -> TranslationService:
    """Build a TranslationService with DeepL client and optional glossary."""
    client = get_deepl_client()
    if client is None:
        raise HTTPException(status_code=500, detail="DeepL API Key fehlt")
    glossary = GlossaryService()
    if glossary_json:
        try:
            entries = json.loads(glossary_json)
            if isinstance(entries, dict):
                glossary.set_entries(entries)
        except (json.JSONDecodeError, TypeError):
            pass
    return TranslationService(deepl_client=client, glossary=glossary)


async def prerender_images_task(translate_job_uuid: str) -> None:
    """Background task: render slide images at 100 DPI and cache them in IMAGE_TMP_DIR."""
    out_dir = IMAGE_TMP_DIR / translate_job_uuid
    out_dir.mkdir(parents=True, exist_ok=True)

    job = get_job(translate_job_uuid)
    if job is None:
        logger.warning("Pre-render: job not found for job={}", translate_job_uuid)
        return
    user_id = job["user_id"]

    # Read PPTX from job folder (corrected if available, else translated)
    pptx_data: bytes | None = None
    for filename in ("corrected.pptx", "translated.pptx"):
        try:
            pptx_data = get_job_file(user_id, translate_job_uuid, filename)
            break
        except Exception:
            pass

    if pptx_data is None:
        logger.warning("Pre-render: PPTX not found in job folder for job={}", translate_job_uuid)
        return

    tmp_f = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    tmp_f.write(pptx_data)
    tmp_f.close()
    pptx_src = Path(tmp_f.name)

    try:
        await asyncio.to_thread(pptx_to_images, pptx_src, out_dir, 100)
        logger.info("Pre-rendering complete for job={}", translate_job_uuid)
    except Exception as e:
        logger.warning("Pre-rendering failed for job={}: {}", translate_job_uuid, e)
    finally:
        pptx_src.unlink(missing_ok=True)
