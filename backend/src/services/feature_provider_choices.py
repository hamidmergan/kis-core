"""Which providers a user may pick for a tool, by capability."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from loguru import logger

from src import database as db
from src.limits import PROVIDER_PROBE_MAX_AGE_SECONDS
from src.services import feature_router
from src.services.feature_router import FeatureBinding, FeatureNotConfigured
from src.services.protocols import make_adapter

# Exactly one capability per selectable feature.
_FEATURE_CAPABILITY: dict[str, str] = {
    "stt": "stt",
    "vision": "vision",
    "image_gen": "image_gen",
    "image_edit": "image_edit",
    "chat": "chat",
    "embedding": "embedding",
}

# Cap for a single reachability probe.
_PROBE_TIMEOUT = 6.0

# Last probe per provider as (time, reachable), and the probes renewing them right now.
_probed: dict[tuple, tuple[float, bool]] = {}
_probing: dict[tuple, asyncio.Task] = {}


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
    # People see the providers in the admin's order, the standard one first.
    stelle = {pid: i for i, pid in enumerate(db.ordered_ids(route, [p["id"] for p in rows]))}
    rows.sort(key=lambda p: stelle[p["id"]])
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


def binding_for(feature: str, provider_id: int | None) -> FeatureBinding:
    """The chosen provider, the admin route when nothing was chosen or the choice is gone."""
    if provider_id:
        try:
            return resolve_binding(feature, provider_id)
        except FeatureNotConfigured as e:
            logger.warning("Gewaehlter Anbieter nicht mehr nutzbar, Standard springt ein ({})", e)
    return feature_router.resolve(feature)


def fallback_candidates(feature: str) -> list[FeatureBinding]:
    """The admin's fallback for this feature as a binding, empty without one.

    For 'embedding' only a fallback serving the identical model name counts, so a
    query never crosses into a different vector space.
    """
    from src.services import provider_transport

    rows, route = _candidates(feature)
    if not route:
        return []
    primary_id = route.get("provider_id")
    primary_model = _model_for(route, primary_id) if primary_id is not None else ""
    ziel = provider_transport.fallback_target(feature, primary_id, primary_model)
    if ziel is None:
        return []
    provider = next((p for p in rows if p["id"] == ziel.provider_id), None)
    if provider is None:
        return []
    return [FeatureBinding(feature=feature, provider=provider, model=ziel.model)]


async def _probe_reachable(provider: dict) -> bool:
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
        ok = await asyncio.wait_for(asyncio.to_thread(_probe), _PROBE_TIMEOUT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        ok = False
    _probed[_probe_key(provider)] = (time.time(), ok)
    return ok


def _probe_key(provider: dict) -> tuple:
    """A changed address in the admin counts as a new provider."""
    return provider["id"], provider["protocol"], provider["base_url"]


async def _is_reachable(provider: dict) -> bool:
    """The last probe result, an old one is renewed in the background and only a missing one is awaited."""
    key = _probe_key(provider)
    known = _probed.get(key)
    if known is None:
        return await _probe_reachable(provider)
    checked_at, ok = known
    if time.time() - checked_at > PROVIDER_PROBE_MAX_AGE_SECONDS and key not in _probing:
        task = asyncio.create_task(_probe_reachable(provider))
        _probing[key] = task
        task.add_done_callback(lambda _t: _probing.pop(key, None))
    return ok


async def only_reachable(providers: list[dict], feature: str | None = None) -> list[dict]:
    """The providers that answer right now and did not fail their last real call, order kept."""
    from src.services import provider_check

    # A provider can answer the probe and still turn down every real request.
    ids = {p["id"] for p in providers}
    refused = await asyncio.to_thread(provider_check.refused_ids, feature, ids) if feature else set()
    providers = [p for p in providers if p["id"] not in refused]
    flags = await asyncio.gather(*(_is_reachable(p) for p in providers))
    return [p for p, ok in zip(providers, flags) if ok]


async def list_reachable_choices(feature: str) -> dict:
    """The selectable providers with a default, empty when nothing is reachable."""
    candidates, route = _candidates(feature)
    if not candidates:
        return {"providers": [], "default_id": None}

    reachable = await only_reachable(candidates, feature)

    # The candidates come in the admin's order, so the first that answers is the default.
    default_id = reachable[0]["id"] if reachable else None

    return {
        "providers": [{"id": p["id"], "name": p["name"], "model": _model_for(route, p["id"])}
                      for p in reachable],
        "default_id": default_id,
    }
