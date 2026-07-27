"""Shared helpers for all screencast routes: upload validation, translation-service factory,
prerender task, script-generation locks, job-tool list."""

import asyncio
import json
import tempfile
from collections import OrderedDict
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src.dependencies import get_deepl_client
from src.i18n import t
from src.services.glossary import GlossaryService
from src.features.jobs.repository import get_job
from src.services.screencast import IMAGE_TMP_DIR, pptx_to_images
from src.services.translation import TranslationService
from src.storage import get_job_file
from src.utils.file_validation import SCREENCAST_EXTENSIONS

# Job tools that count toward the screencast in the queue/limit calculation
SCREENCAST_TOOLS = ["screencast_translate", "screencast_render"]

# Per-UUID lock: prevents parallel script generation for the same job.
# Begrenzt, weil die Einträge sonst für jeden je gesehenen Job liegen bleiben.
_script_gen_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
_MAX_SCRIPT_GEN_LOCKS = 256


def get_script_gen_lock(uuid_key: str) -> asyncio.Lock:
    """Return the lock for a job (creates it on demand)."""
    lock = _script_gen_locks.get(uuid_key)
    if lock is None:
        lock = asyncio.Lock()
        _script_gen_locks[uuid_key] = lock
        # Älteste freie Sperren verwerfen. Eine gehaltene Sperre bleibt.
        while len(_script_gen_locks) > _MAX_SCRIPT_GEN_LOCKS:
            oldest_key, oldest_lock = next(iter(_script_gen_locks.items()))
            if oldest_lock.locked():
                _script_gen_locks.move_to_end(oldest_key)
                break
            _script_gen_locks.pop(oldest_key)
    _script_gen_locks.move_to_end(uuid_key)
    return lock


def prerender_dir(translate_job_uuid: str, dpi: int) -> Path:
    """Ablage der vorgerenderten Bilder. Die Auflösung gehört in den Pfad."""
    return IMAGE_TMP_DIR / translate_job_uuid / f"dpi{dpi}"


def validate_upload(filename: str | None, locale: str = "de") -> str:
    """Validate filename/extension of a PPTX upload and return the extension."""
    if not filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    ext = Path(filename).suffix.lower()
    if ext not in SCREENCAST_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("screencast.onlyPptx", locale))
    return ext


def build_translation_service(glossary_json: str = "", locale: str = "de") -> TranslationService:
    """Build a TranslationService with DeepL client and optional glossary."""
    client = get_deepl_client()
    if client is None:
        raise HTTPException(status_code=500, detail=t("translate.deeplKeyMissing", locale))
    glossary = GlossaryService()
    if glossary_json:
        try:
            entries = json.loads(glossary_json)
            if isinstance(entries, dict):
                glossary.set_entries(entries)
        except (json.JSONDecodeError, TypeError):
            pass
    return TranslationService(deepl_client=client, glossary=glossary)


async def prerender_images_task(translate_job_uuid: str, dpi: int = 100) -> None:
    """Background task: render slide images and cache them in IMAGE_TMP_DIR.

    Die Auflösung steht im Ordnernamen. Vorher wurde immer mit 100 DPI
    vorgerendert, während die Oberfläche 144 DPI voreinstellt. Damit passte das
    Ergebnis nie und jeder Job hat die LibreOffice-Konvertierung umsonst
    gemacht und danach noch einmal richtig.
    """
    out_dir = prerender_dir(translate_job_uuid, dpi)
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
        await asyncio.to_thread(pptx_to_images, pptx_src, out_dir, dpi)
        logger.info("Pre-rendering complete for job={} at {} DPI", translate_job_uuid, dpi)
    except Exception as e:
        logger.warning("Pre-rendering failed for job={}: {}", translate_job_uuid, e)
    finally:
        pptx_src.unlink(missing_ok=True)
