"""Admin routes for the context window of each provider and model."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies_rbac import require_permission
from src.i18n import get_locale, t
from src.limits import MAP_UNMEASURED_WINDOW_TOKENS
from src.permissions_registry import PERM_SET_PROVIDERS
from src.routes.admin._models import SetModelWindowRequest
from src.services import model_limits

router = APIRouter(tags=["admin: providers"])

_require = require_permission(PERM_SET_PROVIDERS)

# A window outside these bounds is a typo, no model we can reach lies there.
_WINDOW_MIN = 1_000
_WINDOW_MAX = 10_000_000


def _routed_models() -> list[tuple[int, str]]:
    """One model per provider, the one the chat route currently uses there."""
    route = next((r for r in db.list_routes() if r.get("feature") == "chat"), None) or {}
    modelle = {int(pid): m for pid, m in (route.get("provider_models") or {}).items() if m}
    if route.get("provider_id") and route.get("model_name"):
        modelle.setdefault(route["provider_id"], route["model_name"])
    return sorted(modelle.items())


def _row(provider_id: int, model: str, profil: model_limits.ModelProfile | None) -> dict:
    return {
        "provider_id": provider_id,
        "model_name": model,
        "window_tokens": profil.window_tokens if profil and profil.measured else None,
        "source": profil.source if profil else model_limits.QUELLE_UNBEKANNT,
    }


@router.get("/model-windows")
def list_model_windows(_admin=Depends(_require)):
    """The window of every routed model, and what the services assume without one."""
    return {
        "models": [_row(pid, m, model_limits.stored_profile(pid, m)) for pid, m in _routed_models()],
        "unmeasured_window_tokens": MAP_UNMEASURED_WINDOW_TOKENS,
    }


@router.put("/model-windows")
def set_model_window(
    body: SetModelWindowRequest,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """Sets the window by hand, an empty value deletes it and measures again."""
    provider = db.get_provider(body.provider_id)
    if provider is None:
        raise HTTPException(400, t("admin.providers.notFound", locale))
    model = body.model_name.strip()
    if not model:
        raise HTTPException(400, t("admin.providers.windowNoModel", locale))
    if body.window_tokens is not None and not _WINDOW_MIN <= body.window_tokens <= _WINDOW_MAX:
        sep = "." if locale == "de" else ","
        raise HTTPException(400, t("admin.providers.windowOutOfRange", locale,
                                   min=f"{_WINDOW_MIN:,}".replace(",", sep),
                                   max=f"{_WINDOW_MAX:,}".replace(",", sep)))
    profil = model_limits.set_window_by_hand(provider, model, body.window_tokens)
    return _row(body.provider_id, model, profil)
