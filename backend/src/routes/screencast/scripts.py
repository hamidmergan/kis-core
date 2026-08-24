"""Skript-Endpoints: Auto-Save, Batch-Generierung, Einzel-Folien-Refinement."""

import asyncio
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.services.screencast import generate_all_scripts
from src.services.screencast.statistik import messe, route_kennung, zeichen_zahlen
from src.storage import get_job_file, load_result_meta, save_job_file, save_result_meta
from src.services.tool_limits import max_screencast_slides

from src.routes.screencast._models import (
    GenerateScriptsRequest,
    RegenerateSlideScriptRequest,
    SaveScriptsRequest,
)
from src.routes.screencast._shared import get_script_gen_lock


def _merke_skriptsprache(user_id: int, job_uuid: str | None, target_lang: str) -> None:
    """In dieser Sprache stehen die Skripte, also muss die Vertonung sie sprechen."""
    if not job_uuid or not target_lang:
        return
    save_result_meta(user_id, job_uuid, {**(load_result_meta(user_id, job_uuid) or {}),
                                         "target_lang": target_lang})

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

    # The endpoint is authenticated (global verify_auth) but must also confirm the
    # caller OWNS the referenced job. Without it a user could generate into and
    # overwrite another user's job folder (suggested_scripts.json) via its uuid.
    # A foreign / missing job both return 410 so ownership is not an oracle.
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

    _merke_skriptsprache(uuid_user_id or 0, uuid_key, body.target_lang)

    async def _do_generate() -> list[str]:
        return await generate_all_scripts(
            body.slide_texts, llm_client,
            glossary=glossary_dict,
            add_greeting=body.add_greeting, add_closing=body.add_closing,
            min_chars=body.min_chars, max_chars=body.max_chars,
            source_lang=body.source_lang, target_lang=body.target_lang,
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
        # File missing after wait (other request failed) - fall through to regenerate.
        # The lock is now FREE (we released it above), so the acquire below is safe.

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


@router.post("/screencast/regenerate-slide-script")
async def screencast_regenerate_slide_script(
    body: RegenerateSlideScriptRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Regenerate the narration script for a single slide via the configured LLM.

    Called from Step 5 when the user clicks the AI icon next to a slide.
    Uses a single LLM call (no batching) so user_prompt is fully reliable.
    """
    user_prompt = body.user_prompt or (body.messages[-1].content if body.messages else "")
    has_content = (
        body.slide_text.strip()
        or (body.current_script or "").strip()
        or user_prompt.strip()
    )
    if not has_content:
        return {"script": ""}

    llm_client = get_llm_client()

    try:
        script = await asyncio.to_thread(
            llm_client.refine_script,
            user_prompt,
            body.current_script or "",
            body.slide_text,
            body.target_lang,
            body.selected_text or None,
            [{"role": m.role, "content": m.content} for m in body.messages],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=t("screencast.scriptGenerationFailed", locale, error=str(e)))

    return {"script": script}
