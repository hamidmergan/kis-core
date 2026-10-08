"""A person's saved templates: list, upload with checks, rename, delete, preview."""

import asyncio
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from src.dependencies import get_current_user
from src.features.bild import optionen
from src.features.praesentation import vorlage, vorlagen, vorlagen_repo
from src.i18n import get_locale, t
from src.limits import PRAESENTATION_MAX_TEMPLATES, PRAESENTATION_TEMPLATE_MAX_MB
from src.utils.upload_stream import stream_upload_to_path

router = APIRouter(tags=["praesentation"])
_VID = re.compile(r"^[0-9a-f]{32}$")


def _analyse_meta(analyse: vorlage.Analyse | None) -> dict:
    """The cacheable slice of an analysis: what a listing needs, nothing more."""
    if not analyse:
        return {"roles": [], "hasImages": False}
    return {"roles": vorlage.waehlbare_rollen(analyse), "hasImages": analyse.hat_bildfelder()}


def _eintrag(zeile: dict, meta: dict | None, system: bool = False) -> dict:
    meta = meta or {}
    return {"id": zeile["id"], "name": zeile["name"], "stiltext": zeile.get("stiltext", ""), "system": system,
            "roles": meta.get("roles", []), "hasImages": bool(meta.get("hasImages"))}


@router.get("/praesentation/bildstile")
def list_bildstile(_user: dict = Depends(get_current_user)):
    """The styles of the image tool, the template's own style stands in for the THL one."""
    return {k: v for k, v in optionen.stiltexte().items() if k != "thl"}


@router.get("/praesentation/vorlagen")
def list_vorlagen(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id", 0)
    _, meta = vorlagen.systemvorlage()
    system = _eintrag({"id": "thl", "name": meta["name"], "stiltext": meta["style_text"]},
                      _analyse_meta(vorlagen.system_analyse()), system=True)
    eigene = []
    for zeile in vorlagen_repo.list_for_user(user_id):
        gecacht = vorlagen.lade_meta(user_id, zeile["id"])
        if gecacht is None:
            roh = vorlagen.lade(user_id, zeile["id"])
            try:
                analyse = vorlage.analysiere(roh) if roh else None
            except Exception:
                analyse = None
            gecacht = _analyse_meta(analyse)
        eigene.append(_eintrag(zeile, gecacht))
    return [system] + eigene


@router.post("/praesentation/vorlagen")
async def upload_vorlage(
    file: UploadFile = File(...),
    name: str = Form(""),
    stiltext: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user.get("user_id", 0)
    if vorlagen_repo.count(user_id) >= PRAESENTATION_MAX_TEMPLATES:
        raise HTTPException(status_code=422, detail=t("praesentation.templateLimit", locale,
                                                      max=PRAESENTATION_MAX_TEMPLATES))
    ext = Path(file.filename or "").suffix.lower()
    with tempfile.TemporaryDirectory(prefix="praesentation_vorlage_") as tmpdir:
        tmp_path = f"{tmpdir}/upload{ext or '.pptx'}"
        try:
            # Streamed to disk first, the size cap must never buffer a whole 500 MB upload in memory.
            await stream_upload_to_path(file, tmp_path, vorlagen.MAX_BYTES, locale)
        except HTTPException as e:
            if e.status_code == 413:
                raise HTTPException(status_code=422, detail=t("praesentation.templateTooBig", locale,
                                                              max=PRAESENTATION_TEMPLATE_MAX_MB)) from e
            raise
        data = await asyncio.to_thread(Path(tmp_path).read_bytes)
    try:
        data, analyse = await asyncio.to_thread(vorlagen.pruefe, data, ext)
    except vorlagen.VorlageUnbrauchbar as e:
        raise HTTPException(status_code=422, detail=t(e.key, locale, max=PRAESENTATION_TEMPLATE_MAX_MB)) from e
    titel = (name.strip() or Path(file.filename or "Vorlage").stem)[:80]
    zeile = vorlagen_repo.create(user_id, titel, stiltext.strip()[:1000])
    try:
        png = await asyncio.to_thread(vorlagen.deckblatt_vorschau, data, analyse, titel)
    except Exception:  # noqa: BLE001 - a missing preview is no reason to refuse the template
        png = None
    meta = _analyse_meta(analyse)
    await asyncio.to_thread(vorlagen.speichere, user_id, zeile["id"], data, png, meta)
    return _eintrag(zeile, meta)


@router.put("/praesentation/vorlagen/{vid}")
def update_vorlage(vid: str, body: dict, current_user: dict = Depends(get_current_user),
                         locale: str = Depends(get_locale)):
    user_id = current_user.get("user_id", 0)
    alt = vorlagen_repo.get(user_id, vid)
    if not alt:
        raise HTTPException(status_code=404, detail=t("praesentation.templateNotFound", locale))
    name = str(body.get("name") or alt["name"]).strip()[:80]
    stil = str(body.get("stiltext") if body.get("stiltext") is not None else alt["stiltext"]).strip()[:1000]
    zeile = vorlagen_repo.update(user_id, vid, name, stil)
    return _eintrag(zeile, None) if zeile else None


@router.delete("/praesentation/vorlagen/{vid}")
def delete_vorlage(vid: str, current_user: dict = Depends(get_current_user),
                         locale: str = Depends(get_locale)):
    user_id = current_user.get("user_id", 0)
    if not vorlagen_repo.delete(user_id, vid):
        raise HTTPException(status_code=404, detail=t("praesentation.templateNotFound", locale))
    vorlagen.loesche(user_id, vid)
    return {"ok": True}


@router.get("/praesentation/vorlagen/{vid}/vorschau")
async def vorlage_vorschau(vid: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id", 0)
    if vid == "thl":
        png = await asyncio.to_thread(vorlagen.system_cover_vorschau)
    elif _VID.match(vid):
        png = vorlagen.lade_vorschau(user_id, vid)
    else:
        png = None
    if not png:
        raise HTTPException(status_code=404)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
