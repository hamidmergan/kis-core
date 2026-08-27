"""Which providers a user may pick for a tool, by capability."""

from __future__ import annotations

import asyncio
from typing import Optional

from src import database as db
from src.services.feature_router import FeatureBinding, FeatureNotConfigured
from src.services.protocols import make_adapter

# Exactly one capability per selectable feature.
_FEATURE_CAPABILITY: dict[str, str] = {
    "stt": "stt",
    "vision": "vision",
    "image_gen": "image_gen",
    "image_edit": "image_edit",
    "chat": "chat",
}

# Cap for a single reachability probe.
_PROBE_TIMEOUT = 6.0


def _model_for(route: Optional[dict], provider_id: int) -> str:
    """The model registered for this provider, or an empty string."""
    if not route:
        return ""
    models = route.get("provider_models") or {}
    explicit = models.get(str(provider_id))
    if explicit:
        return explicit
    if route.get("provider_id") == provider_id:
        return route.get("model_name") or ""
    return ""


def _candidates(feature: str) -> tuple[list[dict], Optional[dict]]:
    """Enabled, capability-having providers that have a model for ``feature``."""
    cap = _FEATURE_CAPABILITY.get(feature)
    if cap is None:
        return [], None
    route = db.get_route(feature)
    rows = [p for p in db.list_providers_with_capability(cap) if _model_for(route, p["id"])]
    return rows, route


def is_eligible(feature: str, provider_id: int) -> bool:
    """Whether this provider is selectable for this feature."""
    rows, _route = _candidates(feature)
    return any(p["id"] == provider_id for p in rows)


def resolve_binding(feature: str, provider_id: int) -> FeatureBinding:
    """Builds the binding for a chosen provider, by capability."""
    cap = _FEATURE_CAPABILITY.get(feature)
    if cap is None:
        raise FeatureNotConfigured(f"feature {feature!r} is not user-pickable")
    provider = db.get_provider(provider_id)
    if provider is None or not provider.get("enabled"):
        raise FeatureNotConfigured(f"provider {provider_id} for {feature!r} is unavailable")
    if cap not in (provider.get("capabilities") or []):
        raise FeatureNotConfigured(f"provider {provider_id} lacks the {cap!r} capability")
    model = _model_for(db.get_route(feature), provider_id)
    if not model:
        raise FeatureNotConfigured(f"provider {provider_id} has no model for {feature!r}")
    return FeatureBinding(feature=feature, provider=provider, model=model)


async def _is_reachable(provider: dict) -> bool:
    """Probes reachability outside the event loop, False on any error."""
    def _probe() -> bool:
        try:
            adapter = make_adapter(
                protocol=provider["protocol"],
                base_url=provider["base_url"],
                api_key=provider.get("api_key"),
            )
            return adapter.probe().status == "ok"
        except Exception:  # noqa: BLE001 - any probe failure means "not reachable"
            return False

    try:
        return await asyncio.wait_for(asyncio.to_thread(_probe), _PROBE_TIMEOUT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        return False


async def list_reachable_choices(feature: str) -> dict:
    """The selectable providers with a default, empty when nothing is reachable."""
    candidates, route = _candidates(feature)
    if not candidates:
        return {"providers": [], "default_id": None}

    flags = await asyncio.gather(*(_is_reachable(p) for p in candidates))
    reachable = [p for p, ok in zip(candidates, flags) if ok]

    default_id = route.get("provider_id") if route else None
    reachable_ids = {p["id"] for p in reachable}
    if default_id not in reachable_ids:
        default_id = reachable[0]["id"] if reachable else None

    return {
        "providers": [{"id": p["id"], "name": p["name"]} for p in reachable],
        "default_id": default_id,
    }
