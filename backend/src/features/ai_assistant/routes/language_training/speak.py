"""Der Beispielsatz einer Lernkarte, vorgelesen.

Die Ansicht schickt nur die NUMMER der Karte, nie den Text. Ein Endpunkt, der
beliebigen Text entgegennimmt und ihn durch unsere Vertonung schickt, wäre ein
offenes Scheunentor; der Satz kommt deshalb aus derselben Zeile, aus der ihn auch
die Karte anzeigt.

Kein Job und keine Warteschlange wie beim Werkzeug "Text in Sprache". Ein Satz
dauert vier bis fünf Sekunden, das wartet die Ansicht mit einem Kringel ab, und
gespeichert wird nichts: der Browser behält den Ton, solange die Lernansicht
offen ist.

Eigene Datei statt eines weiteren Wegs in exercises.py, damit die Datei nicht
weiter wächst.
"""

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
    """Den Beispielsatz einer Lernkarte als MP3 zurückgeben.

    Kein ``async``: Der Sprech-Aufruf ist blockierend (httpx.Client mit Netzwerk-I/O,
    typisch 4–5 Sekunden, im Fehlerfall bis 600 Sekunden), würde aber als ``async def``
    die Ereignisschleife für die gesamte Dauer sperren und alle anderen Anfragen auf
    demselben Arbeiter verzögern. Ein gewöhnliches ``def`` wird von FastAPI automatisch
    in den Threadpool geschickt, die Ereignisschleife bleibt frei.

    Kein ``enforce_quota``: ein Satz ist kein Vertonungsauftrag und soll niemandem
    das Kontingent für das Werkzeug wegnehmen. Gegen Dauerklicken reicht die
    Burst-Bremse.

    Auch bewusst KEIN ``require_tool_access("tts")``: wer Lernkarten benutzen
    darf, darf seinen Beispielsatz hören, auch wenn das Vertonungswerkzeug für
    seine Rolle nicht freigeschaltet ist.
    """
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    ex_set = db.get_exercise_set_with_items(set_id)
    # Gleicher Riegel wie bei den anderen Einzel-Set-Wegen: 404 statt 403, damit
    # sich fremde Sätze nicht durch Hochzählen der Nummer finden lassen.
    if not ex_set or ex_set["user_id"] != user_id or ex_set["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("set.notFound", locale))

    # Der Lautsprecher funktioniert nur bei Lernkarten-Übungen. Nur Lernkarten
    # schreiben `example_sentence` in `extras`. Dieses Verbot ist in den Daten
    # harte Sicherheit, keine zufällige Implementierungsfolge.
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
