"""KI-Assistent routes - flashcards."""


from fastapi import APIRouter, Depends

from langfuse.decorators import observe

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst

from src.features.ai_assistant.routes._workspace_access import _require_workspace_member, _resolve_source_ids
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: studio"])

@router.post("/ai-assistant/workspaces/{workspace_uuid}/flashcards/generate")
@observe(name="aia-flashcards")
def generate_flashcards(
    workspace_uuid: str,
    body: schemas.FlashcardsGenerateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a flashcards exercise set via Celery."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    _resolve_source_ids(workspace, body.active_source_ids, locale=locale)
    first_uuid = body.active_source_ids[0] if body.active_source_ids else None

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool="flashcards",
        title="Wird generiert…", mode="source", source_uuid=first_uuid,
        source_uuids=body.active_source_ids,
        requested_count=body.count,
    )

    from src.features.ai_assistant.scheduling.service import enqueue_task
    enqueue_task("aia.generate_exercise_set", user_id,
                 args=[placeholder["id"], workspace["id"], "flashcards", "source", body.count],
                 kwargs={"source_uuids": body.active_source_ids, "locale": locale})
    return {"set_id": placeholder["id"], "status": "generating"}
