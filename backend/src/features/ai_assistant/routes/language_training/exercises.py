"""KI-Assistent routes - language_training exercises."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException


from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst

from src.features.ai_assistant.routes._workspace_access import _resolve_source_ids
from src.features.ai_assistant import schemas
from src.features.ai_assistant.repository.stats import LANGUAGE_TRAINING_TOOLS
from src.services.aia_grammar_formats import clean_kinds
from src.services import aia_flashcard_speech as speech

router = APIRouter(tags=["ki-assistent: language-training"])

# Maximum number of sources per set, the legend follows the same number.
_MAX_SET_SOURCES = 5


def _numbered_sources(ex_set: dict) -> list[dict]:
    """The sources of a set, numbered in the order they were picked."""
    uuids = ex_set.get("source_uuids") or []
    if not uuids and ex_set.get("source_uuid"):
        uuids = [ex_set["source_uuid"]]
    out: list[dict] = []
    for suuid in uuids[:_MAX_SET_SOURCES]:
        source = db.get_aia_source(suuid)
        if not source:
            continue
        out.append({"number": len(out) + 1, "filename": source["filename"]})
    return out

# ─── Exercise Sets CRUD ──────────────────────────────────────────────────────

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets")
async def create_exercise_set(
    workspace_uuid: str,
    body: schemas.CreateSetBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a new exercise set - returns immediately, generates via Celery."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    # Without switch and level for this person, a window left open builds nothing any more.
    if body.tool in LANGUAGE_TRAINING_TOOLS and not db.is_language_training_ready(user_id):
        raise HTTPException(status_code=403, detail=t("ai.languageTraining.off", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # A set is built from all chosen sources, source_uuid stays for old browsers.
    source_uuids = body.source_uuids or ([body.source_uuid] if body.source_uuid else [])
    if body.mode == "source":
        if not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        _resolve_source_ids(workspace, source_uuids, max_count=5, locale=locale)

    grammar_topic_id = None
    grammar_kinds = None
    if body.tool == "grammatik":
        # Without sources there is nothing to reshape, the vocabulary comes from the slides.
        if body.mode != "source":
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        topic = db.get_grammar_topic(body.grammar_topic_id)
        if not topic or topic["workspace_id"] != workspace["id"]:
            raise HTTPException(status_code=400, detail=t("grammar.typeInvalid", locale))
        grammar_topic_id = topic["id"]
        # Unknown codes are dropped, a mixed exercise beats an error.
        grammar_kinds = clean_kinds(body.grammar_kinds)

    flashcard_set_id = None
    if body.tool == "wortschatz":
        # Imported locally, a module level import would close a cycle here.
        from src.features.ai_assistant.tasks.language_training._source_cloze import (
            usable_flashcard_set,
        )
        # The text always comes from the sources, on the card path too.
        if body.mode not in ("source", "cards") or not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        _resolve_source_ids(workspace, source_uuids, max_count=5, locale=locale)
        if body.mode == "cards":
            karten = (db.get_exercise_set_with_items(body.flashcard_set_id)
                      if body.flashcard_set_id else None)
            # Whether there really are cards only shows in the exercises already loaded.
            if not usable_flashcard_set(karten, workspace["id"], user_id) or not karten.get("items"):
                raise HTTPException(status_code=400,
                                    detail=t("ai.flashcardSet.invalid", locale))
            flashcard_set_id = karten["id"]

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode,
        source_uuid=source_uuids[0] if source_uuids else None,
        grammar_topic_id=grammar_topic_id,
        source_uuids=source_uuids,
        requested_count=body.count,
        flashcard_set_id=flashcard_set_id,
        grammar_kinds=grammar_kinds,
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], workspace["id"], body.tool, body.mode, body.count,
        source_uuids=source_uuids or None,
        locale=locale,
    )

    return {"set": placeholder}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/retry")
async def retry_exercise_set(
    workspace_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Restarts a failed set with its original settings."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    meta = db.get_exercise_set_meta(set_id)
    # 404 instead of 403, the running number must not reveal other people's sets.
    if not meta or meta["user_id"] != user_id or meta["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    # A trainer that is not ready produces no second attempt either.
    if meta["tool"] in LANGUAGE_TRAINING_TOOLS and not db.is_language_training_ready(user_id):
        raise HTTPException(status_code=403, detail=t("ai.languageTraining.off", locale))

    # A second attempt costs the same and is therefore billed the same.
    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    ex_set = db.reset_exercise_set_for_retry(set_id, user_id)
    if not ex_set:
        # Not failed (any more): already generating, already ready, or a second click.
        raise HTTPException(status_code=409, detail=t("set.retryNotFailed", locale))

    source_uuids = ex_set.get("source_uuids") or (
        [ex_set["source_uuid"]] if ex_set.get("source_uuid") else []
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        set_id, workspace["id"], ex_set["tool"], ex_set["mode"],
        # Sets created before the count was stored fall back to the create default.
        ex_set.get("requested_count") or schemas.CreateSetBody.model_fields["count"].default,
        source_uuids=source_uuids or None,
        locale=locale,
    )

    return {"ok": True, "status": "generating"}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/items/{item_id}/check")
async def check_grammar_answer(
    workspace_uuid: str,
    set_id: int,
    item_id: int,
    body: schemas.GrammarCheckBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Checks a free-text answer purely by computation, without a model call."""
    from src.services import aia_grammar_check as gc

    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    ex_set = db.get_exercise_set_with_items(set_id)
    # 404 instead of 403, the running number must not reveal other people's sets.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("tool") != "grammatik":
        raise HTTPException(status_code=400, detail=t("grammar.typeInvalid", locale))

    item = next((i for i in ex_set.get("items", []) if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    answer = (body.answer or "").strip()
    if not answer:
        raise HTTPException(status_code=400, detail=t("grammar.answerEmpty", locale))

    # The other valid versions of the same reshaping, delivered at generation time.
    accepts = (item.get("extras") or {}).get("accepts") or []

    return {
        "verdict": gc.mark_answer(answer, item["back"], accepts),
        "solution": item["back"],
        "explanation": item.get("explanation"),
    }

@router.get("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets")
async def list_exercise_sets(
    workspace_uuid: str,
    tool: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    sets = db.get_exercise_sets(workspace["id"], user_id, tool)
    for s in sets:
        if s.get("created_at") and hasattr(s["created_at"], "isoformat"):
            s["created_at"] = s["created_at"].isoformat() + "Z"
        # Grammar sets carry a topic, resolved to its name right here.
        topic = db.get_grammar_topic(s.get("grammar_topic_id"))
        if topic:
            s["grammar_topic_name"] = topic["name"]
        s["sources"] = _numbered_sources(s)
    return {"sets": sets}

@router.get("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}")
async def get_exercise_set(
    workspace_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    ex_set = db.get_exercise_set_with_items(set_id)
    # A set belongs to one person in one course room, otherwise 404.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
    topic = db.get_grammar_topic(ex_set.get("grammar_topic_id"))
    if topic:
        ex_set["grammar_topic_name"] = topic["name"]
    # The numbered legend under the exercises, and the numbers the chips print.
    ex_set["sources"] = _numbered_sources(ex_set)
    # Whether the card may show a speaker is set in the admin area.
    ex_set["speech_enabled"] = speech.speech_enabled()
    return {"set": ex_set}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}")
async def delete_exercise_set_endpoint(
    workspace_uuid: str,
    set_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    # Scoped to the owner: deleting another user's set by its serial id returns 404.
    if not db.delete_exercise_set(set_id, current_user["user_id"]):
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    return {"ok": True}

@router.patch("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/title")
async def rename_exercise_set(
    workspace_uuid: str,
    set_id: int,
    body: schemas.ArtifactTitleBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Changes the name of a set, hand-typed names apply without duplicate protection."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    titel = db.clean_title(body.title)
    if not titel:
        raise HTTPException(status_code=400, detail=t("title.empty", locale))

    # Someone else's row: 404 instead of 403, as on the other single-item routes.
    if not db.update_artifact_title("exercise_set", set_id, user_id, workspace["id"], titel):
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    return {"ok": True, "title": titel}

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/progress")
async def record_set_progress(
    workspace_uuid: str,
    set_id: int,
    body: schemas.ExerciseProgressBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    # Without this check anyone could write progress onto other people's sets.
    meta = db.get_exercise_set_meta(set_id)
    if not meta or meta["user_id"] != user_id or meta["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    db.bulk_record_exercise_progress(set_id, user_id, body.results, body.new_run)
    db.update_streak(workspace["id"], user_id)
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

