"""The pages demo, one prepared page from files, without compute and without jobs."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.dependencies import get_current_user
from src.dependencies_rbac import require_tool_access
from src.features.pages import schema
from src.i18n import get_locale, t

router = APIRouter(
    tags=["pages-demo"],
    dependencies=[Depends(require_tool_access("pages"))],
)

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo" / "pages"
_IMAGE_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


def _setup() -> dict:
    pfad = DEMO_DIR / "demo.json"
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}


def _page(locale: str = "") -> dict | None:
    """The prepared page in the reader's language where it has one, else in its own."""
    for name in ([f"page_{locale}.json"] if locale else []) + ["page.json"]:
        pfad = DEMO_DIR / name
        if pfad.exists():
            return schema.for_viewers(schema.clean_page(json.loads(pfad.read_text(encoding="utf-8"))))
    return None


@router.get("/pages-demo/setup")
def demo_setup(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The material of the prepared run and the one card of the demo list, no card without a page."""
    daten = _setup()
    seite = _page(locale)
    return {
        "workspace": daten.get("workspace", ""),
        "files": daten.get("dateien", []),
        "instructions": daten.get("anweisung", ""),
        "card": {
            "title": schema.title_of(seite),
            "image": schema.first_image(seite),
            "sources": ", ".join(daten.get("dateien", [])),
            "created_at": daten.get("erstellt"),
            "updated_at": daten.get("erstellt"),
            # What a real run shows behind the info icon, so the demo card reads the same.
            "info": daten.get("angaben") or {},
        } if seite else None,
    }


@router.get("/pages-demo/page")
def demo_page(_: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """The prepared page as a reader sees it, with the limits every page carries."""
    seite = _page(locale)
    if seite is None:
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return {"page": seite, "limits": schema.limits()}


@router.get("/pages-demo/images/{name}")
def demo_image(name: str, _: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """A picture of the prepared page, only one the page shows."""
    seite = _page()
    datei = DEMO_DIR / name
    if seite is None or not schema.IMAGE_NAME.match(name) or name not in schema.images_of(seite) or not datei.is_file():
        raise HTTPException(status_code=404, detail=t("demo.resultMissing", locale))
    return FileResponse(datei, media_type=_IMAGE_TYPES[datei.suffix],
                        headers={"Cache-Control": "private, max-age=86400"})
