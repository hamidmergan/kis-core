"""The read-only side of a page: its pictures, the view behind a shared link and a person's overview.

These routes need only the link or a login, so a student without the pages tool still reads
what a teacher shared.
"""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.dependencies import get_current_user
from src.features.pages import repository as repo
from src.features.pages import schema
from src.i18n import get_locale, t
from src.storage import get_job_file
from src.tasks import pages_tasks as pt
from src.tasks.pages_tasks import load_page

shared_router = APIRouter(tags=["pages"])

_CODE = re.compile(r"^[A-Za-z0-9]{6,32}$")
IMAGE_TYPES = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}


def _dt(v) -> str | None:
    return (v.isoformat() + "Z") if hasattr(v, "isoformat") else v


def _image(user_id: int, job_uuid: str, name: str, locale: str) -> Response:
    if not schema.IMAGE_NAME.match(name):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    try:
        data = get_job_file(user_id, job_uuid, name)
    except Exception:  # noqa: BLE001 - a missing picture is a 404, nothing more
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale)) from None
    art = IMAGE_TYPES[name[name.rfind("."):]]
    return Response(content=data, media_type=art, headers={"Cache-Control": "private, max-age=86400"})


# A shared link is for the people it is given to, search engines leave it out.
_NOINDEX = {"X-Robots-Tag": "noindex, nofollow, noarchive"}


def _logged_in(user: dict) -> bool:
    """A session that counts as an askFrancis account, an expired test access does not."""
    if not user.get("user_id"):
        return False
    ablauf = user.get("access_expires_at")
    try:
        return not ablauf or datetime.fromisoformat(ablauf) > datetime.now()
    except (TypeError, ValueError):
        return False


def _shared(code: str, user: dict, locale: str) -> tuple[dict, dict]:
    """The page behind a link, 401 when only an askFrancis account may read it and the reader has none."""
    row = repo.shared_page(code) if _CODE.match(code) else None
    page = load_page(row["user_id"], row["job_uuid"])[0] if row and row["status"] == "success" else None
    if not row or page is None:
        raise HTTPException(status_code=404, detail=t("pages.notShared", locale), headers=_NOINDEX)
    if not row["public"] and not _logged_in(user):
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale), headers=_NOINDEX)
    return row, page


@shared_router.get("/pages/shared/{code}")
def shared_page(code: str, response: Response, sprache: str = Query(""),
                current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """A shared page for whoever its link is meant for, in the asked language, hidden sections left out."""
    response.headers.update(_NOINDEX)
    row, page = _shared(code, current_user, locale)
    gezeigt = pt.in_language(row["user_id"], row["job_uuid"], page, sprache)
    return {"page": schema.for_viewers(gezeigt), "owner": {"name": row["owner_name"], "code": row["collection_code"]},
            "limits": schema.limits(), "languages": pt.readable(row["user_id"], row["job_uuid"], page),
            "language": pt.key_of(gezeigt)}


@shared_router.get("/pages/shared/{code}/images/{name}")
def shared_image(code: str, name: str, current_user: dict = Depends(get_current_user),
                 locale: str = Depends(get_locale)):
    row, page = _shared(code, current_user, locale)
    if name not in pt.viewer_images(row["user_id"], row["job_uuid"], page):
        raise HTTPException(status_code=404, detail=t("pages.notFound", locale))
    bild = _image(row["user_id"], row["job_uuid"], name, locale)
    bild.headers.update(_NOINDEX)
    return bild


@shared_router.get("/pages/collection/{code}")
def shared_collection(code: str, response: Response, current_user: dict = Depends(get_current_user),
                      locale: str = Depends(get_locale)):
    """Every page one person shares, newest first, as cards; without an account only the open ones."""
    response.headers.update(_NOINDEX)
    angemeldet = _logged_in(current_user)
    daten = repo.collection(code, only_public=not angemeldet) if _CODE.match(code) else None
    own = bool(daten) and daten["user_id"] == current_user.get("user_id", 0)
    # An overview its owner has not shared is theirs alone, the login may show it is theirs.
    if daten and not daten["enabled"] and not own and not angemeldet:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale), headers=_NOINDEX)
    if not daten or not (daten["enabled"] or own):
        raise HTTPException(status_code=404, detail=t("pages.collectionNotFound", locale), headers=_NOINDEX)
    # Nothing open to show, the login may reveal the pages meant for askFrancis accounts.
    if not angemeldet and not daten["pages"]:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale), headers=_NOINDEX)
    karten = []
    for row in daten["pages"]:
        page = load_page(daten["user_id"], row["job_uuid"])[0]
        if not page:
            continue
        sichtbar = schema.for_viewers(page)
        karten.append({"code": row["code"], "title": schema.title_of(sichtbar),
                       "image": schema.first_image(sichtbar),
                       "updated_at": page.get("saved_at") or _dt(row["completed_at"] or row["updated_at"])})
    # The owner gets the way back to their own pages, a reader has the logo.
    return {"owner": {"name": daten["owner_name"]}, "pages": karten, "own": own,
            "shared": daten["enabled"]}
