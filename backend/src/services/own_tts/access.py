"""Who may use which own interface, the one place that decides it."""
from __future__ import annotations

from fastapi import HTTPException

from src import database as db
from src.i18n import t
from src.permissions_registry import PERM_GENERAL_INTERFACES

# Raise it when the disclaimer changes in substance, everybody then has to accept anew.
CONSENT_VERSION = 1


def has_permission(user: dict) -> bool:
    from src.dependencies_rbac import permissions_of

    return permissions_of(user).has(PERM_GENERAL_INTERFACES)


def has_consent(user_id: int) -> bool:
    version = db.get_interfaces_consent(user_id).get("interfaces_consent_version") or 0
    return version >= CONSENT_VERSION


def may_use(user: dict) -> bool:
    """The permission and the accepted disclaimer, both are needed."""
    return has_permission(user) and has_consent(user.get("user_id") or 0)


def own_voice_providers(user: dict) -> list[dict]:
    """The person's own voice services that are switched on, empty without permission or agreement."""
    if not may_use(user):
        return []
    return [p for p in db.list_own_providers(user["user_id"]) if p.get("enabled")]


def check_voice_provider(provider_id: int, user: dict, locale: str) -> None:
    """Refuses a person's own interface to everybody else, and to the owner without permission or agreement."""
    provider = db.get_provider(provider_id) if provider_id else None
    owner = (provider or {}).get("owner_user_id")
    if owner is None:
        return
    if owner != user.get("user_id") or not may_use(user):
        raise HTTPException(status_code=404, detail=t("tts.providerNotFound", locale))
