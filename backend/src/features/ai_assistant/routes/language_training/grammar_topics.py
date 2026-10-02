"""List, create and maintain grammar topics, creating happens in two steps."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota

from src.features.ai_assistant import schemas
from src.features.ai_assistant.repository.grammar_topics import MAX_EXAMPLES
from src.features.ai_assistant.routes._workspace_access import _require_workspace_access
from src.features.ai_assistant.tasks._helpers import _get_llm_client
from src.services.aia_grammar_topic import derive_topic

router = APIRouter(tags=["ki-assistent: language-training"])

_BASE = "/ai-assistant/workspaces/{workspace_uuid}/grammar-topics"


def _topic_in_workspace(topic_id: int, workspace: dict, locale: str) -> dict:
    """The topic, or 404. A topic of another course counts as non-existent."""
    topic = db.get_grammar_topic(topic_id)
    if not topic or topic["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("grammar.topicNotFound", locale))
    return topic


def _is_topic_manager(workspace: dict, creator_id: int | None,
                      tutor_cache: dict[int, bool] | None = None) -> bool:
    """Whether a topic by this creator counts as official, visible to everyone."""
    if creator_id is None:
        return False
    if creator_id == workspace["user_id"]:
        return True
    if tutor_cache is None:
        return db.is_workspace_tutor(workspace["id"], creator_id)
    if creator_id not in tutor_cache:
        tutor_cache[creator_id] = db.is_workspace_tutor(workspace["id"], creator_id)
    return tutor_cache[creator_id]


def _require_topic_edit_access(workspace: dict, topic: dict, user_id: int, locale: str) -> None:
    """The creator may touch their own topic, owner and tutor reach every topic."""
    if topic.get("created_by") == user_id:
        return
    if _is_topic_manager(workspace, user_id):
        return
    raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))


@router.get(_BASE)
def list_topics(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Official topics plus your own, everyone else's private topics stay hidden."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    tutor_cache: dict[int, bool] = {}
    topics = [
        t_ for t_ in db.list_grammar_topics(workspace["id"])
        if t_.get("created_by") == user_id or _is_topic_manager(workspace, t_.get("created_by"), tutor_cache)
    ]
    return {"topics": topics}


@router.post(_BASE + "/preview")
def preview_topic(
    workspace_uuid: str,
    body: schemas.GrammarTopicPreviewBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Rule and pattern pair for a typed name, without saving."""
    user_id = current_user["user_id"]
    _require_workspace_access(workspace_uuid, user_id, locale)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("grammar.topicNameEmpty", locale))
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    client, model, _ = _get_llm_client()
    # Rule and pattern are produced in the teaching language, not the interface language.
    from src.features.ai_assistant.tasks._helpers import tool_output_language
    workspace = db.get_aia_workspace(workspace_uuid) or {}
    _, sprache = tool_output_language(workspace.get("id"))
    try:
        derived = derive_topic(client, model, name, sprache)
    except Exception as e:
        # The service is gone, the topic is not wrong.
        logger.warning("Grammatik-Thema {!r}: Anbieter nicht erreichbar: {}", name, e)
        raise HTTPException(status_code=503, detail=t("grammar.topicServiceDown", locale))
    if not derived:
        # A refusal beats an invented entry that a whole course practises.
        raise HTTPException(status_code=422,
                            detail=t("grammar.topicNotRecognized", locale))
    # The rule goes back along so the second call need not derive it again.
    return {"name": name, "rule": derived["rule"], "examples": derived["examples"],
            # The name of the elaborated form, empty means no row in the form.
            "suggested_name": derived.get("label") or ""}


@router.post(_BASE)
def create_topic(
    workspace_uuid: str,
    body: schemas.GrammarTopicCreateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Create a topic, with the elaboration from the preview."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("grammar.topicNameEmpty", locale))
    existing = {t_["name"].casefold() for t_ in db.list_grammar_topics(workspace["id"])}
    if name.casefold() in existing:
        raise HTTPException(status_code=409, detail=t("grammar.topicExists", locale))

    topic = db.create_grammar_topic(workspace["id"], name, user_id)
    pairs = [p.model_dump() for p in body.examples][:MAX_EXAMPLES]
    db.save_topic_spec(topic["id"], locale, body.rule, pairs)
    return {"topic": topic}


@router.patch(_BASE + "/{topic_id}")
def update_topic_examples(
    workspace_uuid: str,
    topic_id: int,
    body: schemas.GrammarTopicUpdateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Overwrites the examples, the rule stays the model's business."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    _require_topic_edit_access(workspace, topic, user_id, locale)
    spec = db.get_topic_spec(topic["id"], locale) or {"rule": ""}
    # A stored rule wins, the sent one only fills a topic that never had one.
    rule = spec.get("rule") or (body.rule or "").strip()
    pairs = [p.model_dump() for p in body.examples][:MAX_EXAMPLES]
    if not rule or not pairs:
        raise HTTPException(status_code=400, detail=t("grammar.topicNeedsExample", locale))
    saved = db.update_topic_examples(topic["id"], locale, rule, pairs)
    return {"topic": topic, "examples": saved["examples"]}


@router.get(_BASE + "/{topic_id}")
def get_topic(
    workspace_uuid: str,
    topic_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """A topic with its examples in the course language, for display and editing."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    if topic.get("created_by") != user_id and not _is_topic_manager(workspace, topic.get("created_by")):
        # Someone else's private topic, a locked-away id counts as non-existent.
        raise HTTPException(status_code=404, detail=t("grammar.topicNotFound", locale))
    spec = db.get_topic_spec(topic["id"], locale) or {}
    return {"topic": topic, "examples": spec.get("examples") or []}


@router.delete(_BASE + "/{topic_id}")
def delete_topic(
    workspace_uuid: str,
    topic_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(workspace_uuid, user_id, locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    _require_topic_edit_access(workspace, topic, user_id, locale)
    db.delete_grammar_topic(topic["id"])
    return {"ok": True}
