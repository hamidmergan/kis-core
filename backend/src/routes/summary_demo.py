"""The summary demo, prepared results from files, without compute and without jobs."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.features.summary.templates import TEMPLATES, get_template
from src.i18n import get_locale, t
from src.utils.download_header import attachment

router = APIRouter(
    tags=["summary-demo"],
    dependencies=[Depends(require_tool_access("summary"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "zusammenfassung"
_ARTEN = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ABSCHNITT = re.compile(r"^#{2,3} ", re.MULTILINE)


def _ergebnis(slug: str, endung: str) -> Path | None:
    """The prepared file of one template, None when it is missing."""
    ordner = DEMO_DIR / slug
    if endung not in _ARTEN or get_template(slug) is None or not ordner.is_dir():
        return None
    return next(iter(sorted(ordner.glob(f"*.{endung}"))), None)


@router.get("/summary-demo/setup")
def demo_setup(_: dict = Depends(get_current_user)):
    """The material and instruction of the prepared runs, and the templates that have one."""
    pfad = DEMO_DIR / "demo.json"
    daten = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}
    ergebnisse = {v.slug: md for v in TEMPLATES if (md := _ergebnis(v.slug, "md"))}
    return {
        "workspace": daten.get("workspace", ""),
        "files": daten.get("dateien", []),
        "instructions": daten.get("anweisung", ""),
        # What a real run shows in its info, so the demo result reads the same.
        "provider": daten.get("anbieter", ""),
        "created": daten.get("erstellt"),
        "templates": list(ergebnisse),
        # The simulated run counts the sections the prepared text really has.
        "sections": {slug: max(1, len(_ABSCHNITT.findall(md.read_text(encoding="utf-8"))))
                     for slug, md in ergebnisse.items()},
    }


@router.get("/summary-demo/{slug}/{endung}")
def demo_download(
    slug: str,
    endung: str,
    _: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The prepared result of one template as Markdown or Word."""
    datei = _ergebnis(slug, endung)
    if datei is None:
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return FileResponse(datei, media_type=_ARTEN[endung], headers={"Content-Disposition": attachment(datei.name)})
