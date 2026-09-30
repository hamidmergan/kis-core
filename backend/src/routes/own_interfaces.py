"""A person's own interfaces: accept the disclaimer once, then connect, refresh or remove a voice service."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies_rbac import require_permission
from src.i18n import get_locale, t
from src.permissions_registry import PERM_GENERAL_INTERFACES
from src.services import export_crypto, own_tts
from src.services.own_tts._base import OwnInterfaceError
from src.services.own_tts.access import CONSENT_VERSION, has_consent

router = APIRouter(prefix="/me/interfaces", tags=["own interfaces"])

_gate = require_permission(PERM_GENERAL_INTERFACES)


class ConnectRequest(BaseModel):
    vendor: str
    api_key: str = Field(min_length=8, max_length=500)


def _require_consent(user: dict, locale: str) -> None:
    if not has_consent(user["user_id"]):
        raise HTTPException(status_code=403, detail=t("interfaces.consentRequired", locale))


def _own_row(provider_id: int, user: dict, locale: str) -> dict:
    row = db.get_provider(provider_id)
    if not row or row.get("owner_user_id") != user["user_id"]:
        raise HTTPException(status_code=404, detail=t("interfaces.notFound", locale))
    return row


def _refusal(e: OwnInterfaceError, locale: str) -> HTTPException:
    logger.info("Eigene Schnittstelle {} abgewiesen: {} {}", e.vendor_label, e.code, e.detail[:200])
    status = 400 if e.permanent or e.code == "rejected" else 502
    return HTTPException(status_code=status, detail=e.message(locale))


def _public(row: dict) -> dict:
    """What the page shows, the key only as its last characters."""
    key = row.get("api_key") or ""
    vendor = own_tts.vendor_of(row)
    return {
        "id": row["id"],
        "vendor": vendor.key,
        "label": vendor.label,
        "key_last_chars": key[-4:] if len(key) > 4 else "",
        "voices": [{"voice_id": v.get("voice_id"), "name": v.get("name")} for v in row.get("voices") or []],
        "created_at": row.get("created_at"),
    }


@router.get("")
def overview(user: dict = Depends(_gate)):
    consent = db.get_interfaces_consent(user["user_id"])
    at = consent.get("interfaces_consent_at")
    rows = db.list_own_providers(user["user_id"]) if has_consent(user["user_id"]) else []
    return {
        "consent": {
            "accepted": has_consent(user["user_id"]),
            "accepted_at": at.isoformat() if at else None,
            "version": CONSENT_VERSION,
        },
        "vendors": [{"key": v.key, "label": v.label} for v in own_tts.VENDORS.values()],
        "interfaces": [_public(r) for r in rows if r.get("protocol") in own_tts.VENDORS],
    }


@router.post("/consent")
def accept_consent(user: dict = Depends(_gate)):
    db.set_interfaces_consent(user["user_id"], CONSENT_VERSION)
    logger.info("Person {} hat den Hinweis zu eigenen Schnittstellen bestätigt (Fassung {})",
                user["user_id"], CONSENT_VERSION)
    return {"ok": True}


@router.post("")
async def connect(body: ConnectRequest, user: dict = Depends(_gate), locale: str = Depends(get_locale)):
    """Checks the key by reading the voices, then stores it, a second key for the same service replaces the first."""
    _require_consent(user, locale)
    # The disclaimer promises an encrypted key, without the server's secret it would lie in plain text.
    if not export_crypto.is_export_key_configured():
        raise HTTPException(status_code=503, detail=t("interfaces.encryptionMissing", locale))
    vendor = own_tts.VENDORS.get(body.vendor)
    if vendor is None:
        raise HTTPException(status_code=400, detail=t("interfaces.unknownVendor", locale))
    key = body.api_key.strip()
    try:
        voices = await asyncio.to_thread(vendor.module.list_voices, key)
    except OwnInterfaceError as e:
        raise _refusal(e, locale) from e
    if not voices:
        raise HTTPException(status_code=400, detail=t("interfaces.noVoices", locale, vendor=vendor.label))

    existing = next((p for p in db.list_own_providers(user["user_id"]) if p.get("protocol") == vendor.key), None)
    if existing:
        row = db.update_provider(existing["id"], api_key=key, voices=voices, enabled=True)
    else:
        row = db.create_provider(
            name=own_tts.internal_name(vendor, user["user_id"]),
            protocol=vendor.key,
            base_url=vendor.base_url,
            api_key=key,
            capabilities=["tts"],
            voices=voices,
            enabled=True,
            concurrency={"tts": vendor.concurrency},
            owner_user_id=user["user_id"],
        )
    logger.info("Person {} hat {} verbunden, {} Stimmen", user["user_id"], vendor.label, len(voices))
    return {"interface": _public(row)}


@router.post("/{provider_id}/refresh")
async def refresh_voices(provider_id: int, user: dict = Depends(_gate), locale: str = Depends(get_locale)):
    """Reads the voices again, for example after cloning a new one at the service."""
    _require_consent(user, locale)
    row = _own_row(provider_id, user, locale)
    vendor = own_tts.vendor_of(row)
    try:
        voices = await asyncio.to_thread(vendor.module.list_voices, row.get("api_key") or "")
    except OwnInterfaceError as e:
        raise _refusal(e, locale) from e
    row = db.update_provider(provider_id, voices=voices)
    return {"interface": _public(row)}


@router.get("/{provider_id}/credit")
async def credit(provider_id: int, user: dict = Depends(_gate), locale: str = Depends(get_locale)):
    """The balance left at the service, null when the service does not tell."""
    _require_consent(user, locale)
    row = _own_row(provider_id, user, locale)
    vendor = own_tts.vendor_of(row)
    try:
        return {"credit": await asyncio.to_thread(vendor.module.credit, row.get("api_key") or "")}
    except OwnInterfaceError as e:
        raise _refusal(e, locale) from e


@router.delete("/{provider_id}")
def disconnect(provider_id: int, user: dict = Depends(_gate), locale: str = Depends(get_locale)):
    """Removes the interface together with the stored key."""
    _own_row(provider_id, user, locale)
    db.delete_provider(provider_id)
    logger.info("Person {} hat eigene Schnittstelle {} entfernt", user["user_id"], provider_id)
    return {"ok": True}
