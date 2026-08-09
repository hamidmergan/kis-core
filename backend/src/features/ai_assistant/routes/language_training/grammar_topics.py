"""Themen der Grammatik-Übung: auflisten, anlegen, Beispiele pflegen.

Anlegen ist Verwaltungsarbeit und hängt deshalb an Eigentum oder Tutor-Rolle,
nicht am Systemrang. Wählen darf jeder mit Zugang, sonst wäre die Liste für
Studierende nutzlos.

Der Ablauf ist bewusst zweistufig. ``preview`` leitet Regel und Musterpaar ab und
speichert **nichts**. Erst der zweite Aufruf legt an. So sieht der Dozent das
Musterpaar, bevor irgendetwas in der Datenbank steht, und das ist hier die
einzige Prüfstelle: die Grammatik kommt nicht aus den Quellen, also kann sie auch
nicht an ihnen geprüft werden.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t

from src.features.ai_assistant import schemas
from src.features.ai_assistant.repository.grammar_topics import MAX_EXAMPLES
from src.features.ai_assistant.routes._helpers import (
    _require_workspace_access,
    _require_workspace_manage,
)
from src.features.ai_assistant.tasks._helpers import _get_llm_client
from src.services.aia_grammar_topic import derive_topic

router = APIRouter(tags=["ki-assistent: language-training"])

_BASE = "/ai-assistant/workspaces/{workspace_uuid}/grammar-topics"


def _topic_in_workspace(topic_id: int, workspace: dict, locale: str) -> dict:
    """Das Thema, oder 404. Ein Thema eines fremden Kurses gilt als nicht vorhanden."""
    topic = db.get_grammar_topic(topic_id)
    if not topic or topic["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("grammar.topicNotFound", locale))
    return topic


@router.get(_BASE)
async def list_topics(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Die Themen des Kurses. Für alle mit Zugang, denn daraus wählt der Lernende."""
    workspace = _require_workspace_access(workspace_uuid, current_user["user_id"], locale)
    return {"topics": db.list_grammar_topics(workspace["id"])}


@router.post(_BASE + "/preview")
async def preview_topic(
    workspace_uuid: str,
    body: schemas.GrammarTopicPreviewBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Regel und Musterpaar zu einem getippten Namen, ohne zu speichern."""
    _require_workspace_manage(workspace_uuid, current_user["user_id"], locale)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("grammar.topicNameEmpty", locale))

    client, model, _ = _get_llm_client()
    # Regel und Musterbeispiel entstehen in der Unterrichtssprache des Kursraums, nicht
    # in der Sprache, auf die der Dozent seine Oberflaeche gestellt hat.
    from src.features.ai_assistant.tasks._helpers import tool_output_language
    workspace = db.get_aia_workspace(workspace_uuid) or {}
    _, sprache = tool_output_language(workspace.get("id"))
    try:
        derived = derive_topic(client, model, name, sprache)
    except Exception as e:
        # Der Dienst ist weg, nicht das Thema falsch. Wer hier "kein Grammatikthema"
        # liest, schreibt seinen völlig richtigen Namen um und wundert sich.
        logger.warning("Grammatik-Thema {!r}: Anbieter nicht erreichbar: {}", name, e)
        raise HTTPException(status_code=503, detail=t("grammar.topicServiceDown", locale))
    if not derived:
        # Kein Grammatikthema, oder das Modell hat kein brauchbares Muster geliefert.
        # Eine Absage ist hier besser als ein erfundener Eintrag, den später ein
        # ganzer Kurs übt.
        raise HTTPException(status_code=422,
                            detail=t("grammar.topicNotRecognized", locale))
    # Die Regel geht mit zurück, damit der zweite Aufruf sie nicht neu ableiten muss.
    # Angezeigt wird sie nicht, der Dozent beurteilt das Musterpaar.
    return {"name": name, "rule": derived["rule"], "examples": derived["examples"],
            "task_lines": derived.get("task_lines") or {},
            # Der Name der Form, die das Modell wirklich ausgearbeitet hat. Leer heisst,
            # das Formular zeigt keine Zeile. Gespeichert wird er nie, er ist danach
            # entweder der Name oder vergessen.
            "suggested_name": derived.get("label") or ""}


@router.post(_BASE)
async def create_topic(
    workspace_uuid: str,
    body: schemas.GrammarTopicCreateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Thema anlegen, mit der Ausarbeitung aus der Vorschau."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_manage(workspace_uuid, user_id, locale)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail=t("grammar.topicNameEmpty", locale))
    existing = {t_["name"].casefold() for t_ in db.list_grammar_topics(workspace["id"])}
    if name.casefold() in existing:
        raise HTTPException(status_code=409, detail=t("grammar.topicExists", locale))

    topic = db.create_grammar_topic(workspace["id"], name, user_id)
    pairs = [p.model_dump() for p in body.examples][:MAX_EXAMPLES]
    # Die Anweisungszeilen kommen aus der Vorschau mit. Fehlen sie, arbeitet der erste
    # Uebungslauf das Thema ohnehin nach und traegt sie dann ein.
    db.save_topic_spec(topic["id"], locale, body.rule, pairs,
                       getattr(body, "task_lines", None))
    return {"topic": topic}


@router.patch(_BASE + "/{topic_id}")
async def update_topic_examples(
    workspace_uuid: str,
    topic_id: int,
    body: schemas.GrammarTopicUpdateBody,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Beispiele überschreiben. Die Regel bleibt, sie ist Modellsache.

    Das ist der Weg, auf dem das Sprachenzentrum sein eigenes Material einbringt:
    es korrigiert Beispiele, statt Anweisungen zu formulieren. In diesem Projekt
    ist mehrfach gemessen worden, dass Prosa-Regeln wirkungslos bleiben und
    Beispiele wirken.
    """
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    spec = db.get_topic_spec(topic["id"], locale) or {"rule": ""}
    pairs = [p.model_dump() for p in body.examples][:MAX_EXAMPLES]
    # Der Dozent korrigiert Beispiele, nicht Anweisungen. Die bleiben, wie sie sind,
    # sonst waeren sie nach jeder Beispiel-Korrektur weg.
    saved = db.save_topic_spec(topic["id"], locale, spec.get("rule") or "", pairs,
                               spec.get("task_lines"))
    return {"topic": topic, "examples": saved["examples"]}


@router.get(_BASE + "/{topic_id}")
async def get_topic(
    workspace_uuid: str,
    topic_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Ein Thema samt Beispielen in der Kurssprache, zum Anzeigen und Bearbeiten."""
    workspace = _require_workspace_access(workspace_uuid, current_user["user_id"], locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    spec = db.get_topic_spec(topic["id"], locale) or {}
    return {"topic": topic, "examples": spec.get("examples") or []}


@router.delete(_BASE + "/{topic_id}")
async def delete_topic(
    workspace_uuid: str,
    topic_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    workspace = _require_workspace_manage(workspace_uuid, current_user["user_id"], locale)
    topic = _topic_in_workspace(topic_id, workspace, locale)
    db.delete_grammar_topic(topic["id"])
    return {"ok": True}
