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
from src.services.aia_grammar_types import (
    GRAMMAR_TYPES,
    catalog_for_api,
    get_grammar_type,
    localized,
)

router = APIRouter(tags=["ki-assistent: language-training"])

# A set is generated from at most this many sources (enforced at creation), so the
# numbered legend under the exercises never grows past it either.
_MAX_SET_SOURCES = 5


def _media_source_uuids(source_uuids: list[str]) -> list[str]:
    """Only the audio/video sources of a selection, in the order the learner picked them.

    Hörverstehen is about spoken material, so a PDF that happens to be ticked as well
    drops out instead of ending up in the set. Filtering beats refusing: the learner
    usually has a whole module selected, not one file.
    """
    from src.services.aia_chunker import is_media_file

    out: list[str] = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source and is_media_file(source.get("file_type") or ""):
            out.append(suuid)
    return out


def _numbered_sources(ex_set: dict) -> list[dict]:
    """The set's sources as ``[{number, filename}]``, numbered in selection order.

    That numbering is what the citation chips print in brackets, so it has to be the
    same for every item of the set. Numbering per item (which is what the views did)
    gives the same file different numbers on different cards.

    A source deleted since generation drops out and the remaining ones close the gap:
    a legend entry the learner cannot open is worse than a renumbering.
    """
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

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # A set can be generated from every selected source, not just the first one.
    # source_uuid stays supported for older clients that only send a single UUID.
    source_uuids = body.source_uuids or ([body.source_uuid] if body.source_uuid else [])
    if body.tool == "hoerverstehen":
        # There is nothing to listen to in a PDF, and the learner normally has a whole
        # module ticked. So the recordings are kept and the rest drops out silently,
        # and only a selection without any recording is an error.
        if body.mode != "source":
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        source_uuids = _media_source_uuids(source_uuids)
        if not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.noMediaSelected", locale))
    if body.mode == "source":
        if not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        _resolve_source_ids(workspace, source_uuids, max_count=5, locale=locale)

    grammar_type = None
    if body.tool == "grammatik":
        # The grammar tool rewrites sentences about the source content, so it has
        # nothing to work with in glossary mode.
        if body.mode != "source":
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        known = {e["id"] for e in GRAMMAR_TYPES}
        if not body.grammar_type or body.grammar_type not in known:
            raise HTTPException(status_code=400, detail=t("grammar.typeInvalid", locale))
        grammar_type = body.grammar_type

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode,
        source_uuid=source_uuids[0] if source_uuids else None,
        grammar_type=grammar_type,
        source_uuids=source_uuids,
        requested_count=body.count,
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
    """Run a failed set's generation again, with the settings it was created from.

    The set keeps its id rather than being deleted and re-created, so the learner
    watches the same card go from failed back to generating instead of one card
    vanishing and another appearing.
    """
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    meta = db.get_exercise_set_meta(set_id)
    # Same 404-not-403 rule as the other single-set routes: the serial id must not
    # reveal that another user's set exists.
    if not meta or meta["user_id"] != user_id or meta["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    # A retry costs the same model calls as the first attempt, so it is charged the
    # same way. Checked before the reset, so a rejected retry leaves the card failed
    # rather than stuck in generating with no task behind it.
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


@router.get("/ai-assistant/workspaces/{workspace_uuid}/grammar-types")
async def list_grammar_types(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The grammar exercise types a learner can pick, in the UI language.

    Same catalogue everywhere. It is served per workspace only because access is
    checked here, not because the list differs.
    """
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))
    if workspace["user_id"] != user_id and not db.is_student_enrolled(workspace["id"], user_id):
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))
    return {"types": catalog_for_api(locale)}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/items/{item_id}/check")
async def check_grammar_answer(
    workspace_uuid: str,
    set_id: int,
    item_id: int,
    body: schemas.GrammarCheckBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Mark one free-text grammar answer against its expected solution.

    An exact match is answered without touching the model at all; only a deviating
    answer costs a call. That matters because the provider rate limit is shared
    across the whole university.
    """
    from src.services import aia_grammar_check as gc
    # Imported here, not at module level: the tasks package pulls in the whole
    # generation chain and closes an import cycle back through the attribution.
    from src.features.ai_assistant.tasks._helpers import _language_label

    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    ex_set = db.get_exercise_set_with_items(set_id)
    # Same ownership gate as the other single-set routes: 404, not 403, so the
    # serial id cannot be used to probe for other users' sets.
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

    gtype = get_grammar_type(ex_set.get("grammar_type"))
    rule = gtype["rule"] if gtype else ""

    # Only pay the burst budget when the answer actually needs the model.
    if not gc.is_exact_match(answer, item["back"]):
        enforce_aia_burst(user_id, locale)

    client, model = gc.get_check_client()
    if client is None:
        result = {
            "verdict": gc.heuristic_verdict(answer, item["back"]),
            "feedback": None,
            "used_llm": False,
        }
    else:
        result = gc.check_answer(
            client, model,
            given=answer, expected=item["back"],
            prompt_sentence=item["front"], rule=rule,
            language=_language_label(locale),
        )

    return {
        "verdict": result["verdict"],
        "feedback": result["feedback"],
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
        # Grammar sets carry a catalogue id. The list resolves it to the localised
        # name here, so the card can say which exercise type it is without the
        # frontend fetching the catalogue just to render a label.
        entry = get_grammar_type(s.get("grammar_type"))
        if entry:
            s["grammar_type_label"] = localized(entry, "label", locale)
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
    # A set belongs to one user in one workspace (the list route is scoped the same
    # way). Without this check any logged-in user could read another user's set by
    # counting up the serial id. 404 rather than 403 so it does not leak existence.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
    entry = get_grammar_type(ex_set.get("grammar_type"))
    if entry:
        ex_set["grammar_type_label"] = localized(entry, "label", locale)
    # The numbered legend under the exercises, and the numbers the chips print.
    ex_set["sources"] = _numbered_sources(ex_set)
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
    # Without this the serial set_id let any user write progress against a set
    # they do not own.
    meta = db.get_exercise_set_meta(set_id)
    if not meta or meta["user_id"] != user_id or meta["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    db.bulk_record_exercise_progress(set_id, user_id, body.results)
    db.update_streak(workspace["id"], user_id)

    # Feed the learner profile: a wrong item is a weakness on that term, a correct
    # one graduates it. The term is the answer side for a gap sentence (the gap IS
    # the term) and the prompt side otherwise. Decided by content, not by tool, since
    # gap sentences now live inside the quiz.
    _detail = db.get_exercise_set_with_items(set_id)
    if _detail:
        _term_by_id = {
            it["id"]: (
                (it.get("back") if "___" in (it.get("front") or "") else it.get("front")) or ""
            ).strip()
            for it in _detail.get("items", [])
        }
        for _r in body.results:
            _term = _term_by_id.get(_r["item_id"])
            if not _term:
                continue
            if _r["correct"]:
                db.graduate_learner_term(user_id, workspace["id"], _term)
            else:
                db.record_weakness(user_id, workspace["id"], "term", "quiz_wrong", _term)

    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

