"""Reads out the example sentence of a flashcard, the text comes from the card id."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.security.rate_limit import enforce_tool_burst
from src.services import aia_flashcard_speech as speech

router = APIRouter(tags=["ki-assistent: language-training"])


@router.post(
    "/ai-assistant/workspaces/{workspace_uuid}/exercise-sets/{set_id}/items/{item_id}/speak"
)
def speak_example_sentence(
    workspace_uuid: str,
    set_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Returns the example sentence of a flashcard as MP3."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    ex_set = db.get_exercise_set_with_items(set_id)
    # 404 instead of 403 so other people's sets cannot be found by counting up.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    # Only flashcards carry an example sentence, that is hard security in the data.
    if ex_set.get("tool") != "flashcards":
        raise HTTPException(status_code=403, detail=t("flashcards.speechOnly", locale))

    item = next((i for i in ex_set.get("items", []) if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    sentence = ((item.get("extras") or {}).get("example_sentence") or "").strip()
    if not sentence:
        raise HTTPException(status_code=404, detail=t("flashcards.noExampleSentence", locale))

    enforce_tool_burst(user_id, "tts", locale)

    audio = speech.synthesize_sentence(sentence, locale)
    return Response(content=audio, media_type="audio/mpeg")
