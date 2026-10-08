"""Measuring material while it is being picked, so an oversized choice shows before the start.

Podcast, presentation and summary share this. Nothing is stored, the file is read once and
forgotten. The start reads it again and remains the one that decides.
"""

import asyncio
from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.dependencies import get_current_user
from src.i18n import get_locale
from src.services import sources
from src.services import workspace_sources


def measure_router(dienst: str, schluessel: str | None = None) -> APIRouter:
    """The two measuring routes of one service, the service name is its message key unless given."""
    schluessel = schluessel or dienst
    router = APIRouter(tags=[dienst])

    @router.post(f"/{dienst}/measure")
    async def measure_file(file: UploadFile = File(...),
                           _user: dict = Depends(get_current_user),
                           locale: str = Depends(get_locale)):
        zeichen = await sources.measure_upload(file, locale=locale, schluessel=schluessel)
        return {"chars": zeichen, "maxChars": sources.MAX_TOTAL_CHARS}

    @router.post(f"/{dienst}/measure/workspace")
    async def measure_workspace_source(workspace_uuid: str = Form(...),
                                       source_uuid: str = Form(...),
                                       current_user: dict = Depends(get_current_user),
                                       locale: str = Depends(get_locale)):
        zeichen = await asyncio.to_thread(workspace_sources.measure_one,
            workspace_uuid, source_uuid, user_id=current_user.get("user_id", 0),
            locale=locale, schluessel=schluessel)
        return {"chars": zeichen, "maxChars": sources.MAX_TOTAL_CHARS}

    return router
