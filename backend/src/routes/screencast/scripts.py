"""Skript-Endpoints: Auto-Save und Batch-Generierung."""

import asyncio
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.services.screencast import generate_all_scripts
from src.services.screencast import material as zusatzmaterial
from src.services.screencast.pptx import extract_notes_per_slide
from src.services.job_statistik import messe, route_kennung, zeichen_zahlen
from src.storage import get_job_file, job_file_exists, load_result_meta, save_job_file
from src.services.tool_limits import max_screencast_slides

from src.routes.screencast._models import (
    GenerateScriptsRequest,
    SaveScriptsRequest,
)
from src.routes.screencast._shared import get_script_gen_lock, vertonung_verwerfen
from src.routes.screencast._shared import merke_skriptsprache as _merke_skriptsprache

router = APIRouter(tags=["screencast: scripts"])


@router.patch("/screencast/scripts/{translate_job_uuid}")
def save_scripts(
    translate_job_uuid: str,
    body: SaveScriptsRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Autosave or accept scripts for a screencast job (awaiting_user)."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    if job["status"] not in ("awaiting_user", "success"):
        raise HTTPException(status_code=409, detail=t("job.notInputState", locale))
    filename = "accepted_scripts.json" if body.accepted else "user_scripts.json"
    save_job_file(job["user_id"], translate_job_uuid, filename, json.dumps(body.scripts, ensure_ascii=False).encode())
    if body.user_prompt is not None:
        save_job_file(job["user_id"], translate_job_uuid, "prompt.txt", body.user_prompt.encode())
    return {"ok": True}


@router.get("/screencast/{translate_job_uuid}/notizen")
async def screencast_notizen(
    translate_job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The speaker notes of the current deck in the script language, one entry per slide."""
    if not re.match(r"^[a-f0-9]{32}$", translate_job_uuid):
        raise HTTPException(status_code=400, detail=t("job.invalidUuid", locale))
    job = db.get_job(translate_job_uuid)
    if not job or job["user_id"] != current_user.get("user_id", 0):
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    for name in ("corrected.pptx", "translated.pptx"):
        try:
            daten = get_job_file(job["user_id"], translate_job_uuid, name)
        except Exception:
            continue
        notizen = extract_notes_per_slide(daten)
        # The translation step already translated the notes, a skipped one leaves them in the deck's language.
        if job_file_exists(job["user_id"], translate_job_uuid, "original.pptx"):
            return {"notes": notizen}
        sprache = (load_result_meta(job["user_id"], translate_job_uuid) or {}).get("target_lang")
        if not sprache or not any(n.strip() for n in notizen):
            return {"notes": notizen}
        try:
            return {"notes": await asyncio.to_thread(_notizen_uebersetzen, notizen, sprache)}
        except Exception as e:  # noqa: BLE001 - any provider error ends in the same message
            logger.warning("Screencast {}: Notizen nicht übersetzt ({})", translate_job_uuid[:8], e)
            raise HTTPException(status_code=502, detail=t("screencast.notizenNichtUebersetzt", locale))
    raise HTTPException(status_code=404, detail=t("screencast.pptxNotFound", locale))


def _notizen_uebersetzen(notizen: list[str], sprache: str) -> list[str]:
    """Translates the non-empty notes into the script language, the source language is detected."""
    from src.dependencies import get_translate_client_for_provider
    from src.services.translation import TranslationService

    client, glossar = get_translate_client_for_provider(None)
    if client is None:
        raise RuntimeError("No translation provider configured")
    stellen = [i for i, n in enumerate(notizen) if n.strip()]
    uebersetzt = TranslationService(deepl_client=client, glossary=glossar).translate_batch(
        [notizen[i] for i in stellen], "", sprache)
    ergebnis = list(notizen)
    for i, text in zip(stellen, uebersetzt):
        ergebnis[i] = text
    return ergebnis


@router.post("/screencast/generate-scripts")
async def screencast_generate_scripts(
    body: GenerateScriptsRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Generate spoken scripts for each slide via the configured LLM."""
    if not body.slide_texts:
        raise HTTPException(status_code=400, detail=t("screencast.noSlideTexts", locale))

    folien_grenze = max_screencast_slides()
    if len(body.slide_texts) > folien_grenze:
        raise HTTPException(
            status_code=400,
            detail=t(
                "screencast.tooManySlides",
                locale,
                count=len(body.slide_texts),
                max=folien_grenze,
            ),
        )

    logger.info(
        "Screencast/generate-scripts: {} slides, greeting={}, closing={}",
        len(body.slide_texts), body.add_greeting, body.add_closing,
    )

    llm_client = get_llm_client()
    glossary_dict: dict | None = None
    if body.glossary_json:
        try:
            glossary_dict = json.loads(body.glossary_json)
        except (json.JSONDecodeError, TypeError):
            pass

    uuid_key = body.translate_job_uuid if (body.translate_job_uuid and re.match(r"^[a-f0-9]{32}$", body.translate_job_uuid)) else None

    # The caller must own the job, foreign and missing both give 410.
    uuid_user_id: int | None = None
    if uuid_key:
        job_row = db.get_job(uuid_key)
        if not job_row or job_row["user_id"] != current_user.get("user_id", 0):
            raise HTTPException(status_code=410, detail=t("job.dataUnavailable", locale))
        uuid_user_id = job_row["user_id"]

    # Verify job folder still exists before burning LLM tokens
    if uuid_key and uuid_user_id is not None:
        try:
            get_job_file(uuid_user_id, uuid_key, "scripts.txt")
        except Exception:
            raise HTTPException(status_code=410, detail=t("job.dataUnavailable", locale))
        # New scripts arrive, the old audio must not stay behind.
        vertonung_verwerfen(uuid_user_id, uuid_key)

    _merke_skriptsprache(uuid_user_id or 0, uuid_key, body.target_lang)

    async def _do_generate() -> list[str]:
        materials = None
        if uuid_key and uuid_user_id is not None:
            try:
                materials = await asyncio.to_thread(
                    zusatzmaterial.material_je_folie, uuid_user_id, uuid_key, body.slide_texts)
            except Exception as e:  # noqa: BLE001 - without its material the slide still gets a script
                logger.warning("Screencast {}: Material nicht zugeordnet, Skripte ohne ({})", uuid_key[:8], e)
        return await generate_all_scripts(
            body.slide_texts, llm_client,
            glossary=glossary_dict,
            add_greeting=body.add_greeting, add_closing=body.add_closing,
            min_chars=body.min_chars, max_chars=body.max_chars,
            source_lang=body.source_lang, target_lang=body.target_lang,
            materials=materials,
        )

    if not uuid_key:
        return {"scripts": await _do_generate()}

    lock = get_script_gen_lock(uuid_key)

    if lock.locked():
        # Another request is already generating for this job - wait, then return its result
        logger.info("generate-scripts: waiting for concurrent generation of {}", uuid_key)
        async with lock:
            # The other request just finished; read what it saved
            try:
                data = get_job_file(uuid_user_id, uuid_key, "suggested_scripts.json")
                return {"scripts": json.loads(data)}
            except Exception:
                pass
        # File missing after the wait, so generate again, the lock is free.

    async with lock:
        db.set_generating_scripts_flag(uuid_key, True)
        try:
            with messe(uuid_user_id or 0, uuid_key, "skripte") as zahlen:
                zahlen.update(route_kennung("chat"))
                zahlen["ziel"] = body.target_lang
                scripts = await _do_generate()
                zahlen.update(zeichen_zahlen(scripts))
        finally:
            db.set_generating_scripts_flag(uuid_key, False)
        try:
            save_job_file(uuid_user_id, uuid_key, "suggested_scripts.json", json.dumps(scripts, ensure_ascii=False).encode())
        except Exception:
            pass

    return {"scripts": scripts}
