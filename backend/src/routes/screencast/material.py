"""Extra documents for the scripts of one screencast, uploaded or picked from a workspace."""

import asyncio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.dependencies import get_current_user
from src.i18n import get_locale, t
from src.limits import SCREENCAST_MAX_SOURCES
from src.routes.screencast.einstellungen import _auftrag
from src.services import sources as quellen
from src.services import workspace_sources as arbeitsraum
from src.services.screencast import material

router = APIRouter(tags=["screencast: material"])


def _antwort(gelesen: list) -> dict:
    return {"files": [q.dateiname for q in gelesen], "chars": sum(len(q.text) for q in gelesen)}


@router.get("/screencast/{job_uuid}/material")
def material_lesen(job_uuid: str, current_user: dict = Depends(get_current_user),
                   locale: str = Depends(get_locale)):
    user_id = _auftrag(job_uuid, current_user, locale)
    return _antwort(quellen.load_sources(user_id, job_uuid))


@router.post("/screencast/{job_uuid}/material")
async def material_setzen(
    job_uuid: str,
    mode: str = Form("files"),
    workspace_uuid: str = Form(""),
    source_uuids: str = Form("[]"),
    files: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Reads the material once, it replaces whatever the job carried before."""
    user_id = _auftrag(job_uuid, current_user, locale)
    if mode == "module":
        gelesen = await asyncio.to_thread(arbeitsraum.read_workspace,
            workspace_uuid, arbeitsraum.parse_uuids(source_uuids), user_id=user_id,
            locale=locale, hoechstens=SCREENCAST_MAX_SOURCES, schluessel="screencast")
    elif mode == "files":
        gelesen = await quellen.read_uploads(files, locale=locale, hoechstens=SCREENCAST_MAX_SOURCES,
                                             schluessel="screencast")
    else:
        raise HTTPException(status_code=422, detail=t("screencast.noContent", locale))
    await asyncio.to_thread(quellen.save_sources, user_id, job_uuid, gelesen)
    await asyncio.to_thread(material.verwerfen, user_id, job_uuid)
    return _antwort(gelesen)


@router.delete("/screencast/{job_uuid}/material")
def material_entfernen(job_uuid: str, current_user: dict = Depends(get_current_user),
                       locale: str = Depends(get_locale)):
    user_id = _auftrag(job_uuid, current_user, locale)
    quellen.save_sources(user_id, job_uuid, [])
    material.verwerfen(user_id, job_uuid)
    return {"files": [], "chars": 0}
