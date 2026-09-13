"""KI-Assistent routes - flashcards."""


from fastapi import APIRouter, Depends, HTTPException

from langfuse.decorators import observe

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst

from src.features.ai_assistant.routes._workspace_access import _resolve_source_ids
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])

@router.post("/ai-assistant/workspaces/{workspace_uuid}/flashcards/generate")
@observe(name="aia-flashcards")
async def generate_flashcards(
    workspace_uuid: str,
    body: schemas.FlashcardsGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a flashcards exercise set via Celery."""
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

    source_ids = _resolve_source_ids(workspace, body.active_source_ids, locale=locale)
    first_uuid = body.active_source_ids[0] if body.active_source_ids else None

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="flashcards",
        title="Wird generiert…", mode="source", source_uuid=first_uuid,
        source_uuids=body.active_source_ids,
        requested_count=body.count,
    )

    from src.tasks.aia_tasks import run_generate_exercise_set
    run_generate_exercise_set.delay(
        placeholder["id"], workspace["id"], "flashcards", "source", body.count,
        source_uuids=body.active_source_ids,
        locale=locale,
    )
    return {"set_id": placeholder["id"], "status": "generating"}


# ─── DataTable generieren ─────────────────────────────────────────────────

