"""The podcast demo, a finished run from files, without compute and without a job."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.features.podcast import store
from src.i18n import get_locale, t

router = APIRouter(
    tags=["podcast-demo"],
    dependencies=[Depends(require_tool_access("podcast"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "podcast"
ERGEBNIS = "podcast.mp3"
# The start of the same script voiced by other services, to hear what better voices could do, per language.
VERGLEICH_DIR = DEMO_DIR / "vergleich"
_LINE_ID = re.compile(r"^b[0-9]{1,4}$")
_VERGLEICH_ID = re.compile(r"^[a-z0-9]+(-[a-z]{2})?$")


def _laden(locale: str) -> dict:
    pfad = DEMO_DIR / "ansicht.json"
    if not pfad.exists():
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return json.loads(pfad.read_text(encoding="utf-8"))


def _vergleich() -> list[dict]:
    """The comparison excerpts with a language in the order the list names them, one without a file stays as a placeholder."""
    pfad = VERGLEICH_DIR / "vergleich.json"
    if not pfad.exists():
        return []
    eintraege = json.loads(pfad.read_text(encoding="utf-8"))
    return [{**e, "ton": (VERGLEICH_DIR / f"{e['id']}.mp3").exists()} for e in eintraege
            if _VERGLEICH_ID.match(e.get("id", "")) and e.get("sprache")]


@router.get("/podcast-demo/available")
def demo_available(_: dict = Depends(get_current_user)):
    """Whether a prepared run is there, the tool page only offers the demo then."""
    return {"available": (DEMO_DIR / "ansicht.json").exists() and (DEMO_DIR / ERGEBNIS).exists()}


@router.get("/podcast-demo/ansicht")
def demo_ansicht(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The finished run as the real view reports it, plus the material it was made from."""
    daten = _laden(locale)
    zeilen = daten.get("lines", [])
    return {
        "job_uuid": "demo",
        "status": "success",
        "progress": None,
        "error": None,
        "params": daten.get("params"),
        "lines": zeilen,
        "voiced": [z["id"] for z in zeilen if (DEMO_DIR / store.audio_name(z["id"])).exists()],
        "has_result": (DEMO_DIR / ERGEBNIS).exists(),
        "seconds": daten.get("seconds"),
        "workspace": daten.get("workspace", ""),
        "files": daten.get("dateien", []),
        "vergleich": _vergleich(),
        "angaben": daten.get("angaben") or {},
        "erstellt": daten.get("erstellt"),
    }


@router.get("/podcast-demo/line/{line_id}")
def demo_line(line_id: str, _: dict = Depends(get_current_user)):
    datei = DEMO_DIR / store.audio_name(line_id)
    if not _LINE_ID.match(line_id) or not datei.exists():
        raise HTTPException(status_code=404)
    return FileResponse(datei, media_type="audio/mpeg")


@router.get("/podcast-demo/vergleich/{vergleich_id}")
def demo_vergleich(vergleich_id: str, _: dict = Depends(get_current_user)):
    if vergleich_id not in {e["id"] for e in _vergleich() if e["ton"]}:
        raise HTTPException(status_code=404)
    return FileResponse(VERGLEICH_DIR / f"{vergleich_id}.mp3", media_type="audio/mpeg")


@router.get("/podcast-demo/download")
def demo_download(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The finished file, served so the player can seek and the button can save it."""
    datei = DEMO_DIR / ERGEBNIS
    if not datei.exists():
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return FileResponse(datei, media_type="audio/mpeg", filename=ERGEBNIS)


@router.get("/podcast-demo/transcript")
def demo_transcript(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The whole conversation as text, names in front of every contribution, like the real one."""
    daten = _laden(locale)
    personen = (daten.get("params") or {}).get("persons") or [{"name": ""}]
    namen = [personen[z["speaker"]]["name"] if z["speaker"] < len(personen) else personen[0]["name"]
             for z in daten.get("lines", [])]
    text = "\n\n".join(f"{n}: {z['text']}" for n, z in zip(namen, daten.get("lines", []))) + "\n"
    return Response(content=text, media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="podcast.txt"'})
