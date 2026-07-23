"""KI-Assistent routes - language_training exercises."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException


from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst

from src.features.ai_assistant.routes._helpers import (
    _resolve_source_ids,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: language-training"])

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercises/cloze")
async def generate_cloze(
    workspace_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a cloze exercise set via Celery."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    entries = db.get_aia_glossary_by_workspace(workspace["id"], user_id)
    if not entries:
        raise HTTPException(status_code=400, detail=t("glossary.notProvided", locale))

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="lueckentext",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], workspace["id"], "lueckentext", "glossary", 10, None, locale=locale)
    return {"set_id": placeholder["id"], "status": "generating"}

@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercises/vocab-test")
async def generate_vocab_test(
    workspace_uuid: str,
    body: schemas.ExerciseGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a vocab test exercise set via Celery."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    entries = db.get_aia_glossary_by_workspace(workspace["id"], user_id)
    if not entries:
        raise HTTPException(status_code=400, detail=t("glossary.notProvided", locale))

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="vokabeltest",
        title="Wird generiert…", mode="glossary", source_uuid=None,
    )
    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(placeholder["id"], workspace["id"], "vokabeltest", "glossary", 10, None, locale=locale)
    return {"set_id": placeholder["id"], "status": "generating"}


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

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # A set can be generated from every selected source, not just the first one.
    # source_uuid stays supported for older clients that only send a single UUID.
    source_uuids = body.source_uuids or ([body.source_uuid] if body.source_uuid else [])
    if body.mode == "source":
        if not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        _resolve_source_ids(workspace, source_uuids, max_count=5, locale=locale)

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode,
        source_uuid=source_uuids[0] if source_uuids else None,
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], workspace["id"], body.tool, body.mode, body.count,
        source_uuids=source_uuids or None,
        locale=locale,
    )

    return {"set": placeholder}

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
    # A set belongs to one user in one workspace (the list route is scoped the same
    # way). Without this check any logged-in user could read another user's set by
    # counting up the serial id. 404 rather than 403 so it does not leak existence.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
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
    # Without this the serial set_id let any user reset another user's run
    # (start_new_run) and write progress against a set they do not own.
    meta = db.get_exercise_set_meta(set_id)
    if not meta or meta["user_id"] != user_id or meta["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if body.new_run:
        db.start_new_run(set_id)
    db.bulk_record_exercise_progress(set_id, user_id, body.results)
    db.update_streak(workspace["id"], user_id)
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

