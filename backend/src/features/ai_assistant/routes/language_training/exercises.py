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
from src.features.ai_assistant.repository.grammar_topics import catalog_entry

router = APIRouter(tags=["ki-assistent: language-training"])

# A set is generated from at most this many sources (enforced at creation), so the
# numbered legend under the exercises never grows past it either.
_MAX_SET_SOURCES = 5


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

    # Ist der Trainer im Workspace aus, gibt es hier nichts mehr zu bauen. Ein
    # offen gebliebenes Fenster kennt die Kacheln noch und wuerde sonst
    # weiterhin Modell-Aufrufe ausloesen.
    if not db.is_language_training_active(workspace["id"]):
        raise HTTPException(status_code=403, detail=t("ai.workspace.languageTrainingOff", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # A set can be generated from every selected source, not just the first one.
    # source_uuid stays supported for older clients that only send a single UUID.
    source_uuids = body.source_uuids or ([body.source_uuid] if body.source_uuid else [])
    if body.tool == "hoerverstehen" and body.mode != "source":
        # Hör- und Leseverstehen fragt zu den gewählten Quellen, im Glossar stehen nur
        # Einzelbegriffe. Auf Medien gefiltert wird nicht: wer eine PDF anhakt, übt Lesen.
        raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
    if body.mode == "source":
        if not source_uuids:
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        _resolve_source_ids(workspace, source_uuids, max_count=5, locale=locale)

    grammar_topic_id = None
    if body.tool == "grammatik":
        # Geübt wird an den Vorlesungsfolien: die Quellen liefern den Wortschatz, das
        # Thema kommt vom Dozenten. Ohne Quellen gibt es also nichts umzuformen.
        if body.mode != "source":
            raise HTTPException(status_code=400, detail=t("ai.source.notSelected", locale))
        topic = db.get_grammar_topic(body.grammar_topic_id)
        if not topic or topic["workspace_id"] != workspace["id"]:
            raise HTTPException(status_code=400, detail=t("grammar.typeInvalid", locale))
        grammar_topic_id = topic["id"]

    placeholder = db.create_exercise_set_placeholder(
        workspace_id=workspace["id"], user_id=user_id, tool=body.tool,
        title="Wird generiert…", mode=body.mode,
        source_uuid=source_uuids[0] if source_uuids else None,
        grammar_topic_id=grammar_topic_id,
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

    # Vor dem Nachschlagen des Satzes: ein abgeschalteter Trainer erzeugt nichts
    # mehr, auch keinen zweiten Anlauf.
    if not db.is_language_training_active(workspace["id"]):
        raise HTTPException(status_code=403, detail=t("ai.workspace.languageTrainingOff", locale))

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

    # Die Regel steuert die Rueckmeldung. Sie haengt am Thema und an der Sprache,
    # deshalb wird sie hier ueber beides geholt und nicht ueber einen Code-Eintrag.
    topic = db.get_grammar_topic(ex_set.get("grammar_topic_id"))
    spec = db.get_topic_spec(topic["id"], locale) if topic else None
    rule = (spec or {}).get("rule") or ""

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
        # Grammatik-Sets tragen ein Thema. Die Liste löst es hier zum Namen auf,
        # damit die Karte sagen kann worum es geht, ohne dass die Oberfläche dafür
        # eine zweite Anfrage stellt.
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
    # A set belongs to one user in one workspace (the list route is scoped the same
    # way). Without this check any logged-in user could read another user's set by
    # counting up the serial id. 404 rather than 403 so it does not leak existence.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))
    if ex_set.get("created_at") and hasattr(ex_set["created_at"], "isoformat"):
        ex_set["created_at"] = ex_set["created_at"].isoformat() + "Z"
    topic = db.get_grammar_topic(ex_set.get("grammar_topic_id"))
    if topic:
        ex_set["grammar_topic_name"] = topic["name"]
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
    return {"ok": True}


# ─── Streak ──────────────────────────────────────────────────────────────────

