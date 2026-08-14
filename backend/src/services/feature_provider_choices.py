"""Runtime provider choice for user-pickable tool features.

Some tools let the end-user pick which provider serves their request (STT, the
image tools). This mirrors the established TTS picker: the candidate set is
*capability-based*, not the route's ``user_choices`` array. A provider is
offered when it

  * is enabled,
  * has the feature's capability, and
  * has a model configured for this feature (an explicit per-provider model in
    ``provider_models``, or — for the route's primary provider — ``model_name``).

The last point is what "the admin added this provider for the feature" means in
the admin's split routing card: giving a provider a model there opts it in.

``list_reachable_choices`` additionally probes each candidate and returns only
the reachable ones, so the tool dropdown never offers a dead endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from src import database as db
from src.services.feature_router import FeatureBinding, FeatureNotConfigured
from src.services.protocols import make_adapter

# Each user-pickable tool feature is satisfied by exactly one capability.
# ``chat`` is offered only as a per-tool pick (e.g. the summary tool); the
# admin chat route and the AI-assistant chat stay on the default binding.
_FEATURE_CAPABILITY: dict[str, str] = {
    "stt": "stt",
    "vision": "vision",
    "image_gen": "image_gen",
    "image_edit": "image_edit",
    "chat": "chat",
}

# Cap a single reachability probe so one hanging endpoint cannot stall the list
# (the adapter's own client times out at 10s; we give up earlier and treat the
# slow provider as unreachable).
_PROBE_TIMEOUT = 6.0


def _model_for(route: Optional[dict], provider_id: int) -> str:
    """Model configured for ``provider_id`` on this feature, or empty string.

    Explicit per-provider model wins; otherwise the route's ``model_name`` is
    only inherited by the route's primary provider. This keeps a capability-
    eligible provider that the admin never configured out of the candidate set.
    """
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
    """Whether ``provider_id`` may be picked for ``feature`` (used to validate
    a user-supplied choice before queueing a job)."""
    rows, _route = _candidates(feature)
    return any(p["id"] == provider_id for p in rows)


def resolve_binding(feature: str, provider_id: int) -> FeatureBinding:
    """Build a binding for a user-picked provider, by capability (not the
    ``user_choices`` array). Raises ``FeatureNotConfigured`` if the provider is
    gone/disabled, lacks the capability, or has no model for this feature."""
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
    """Run the adapter reachability probe off the event loop. False on any
    error or timeout."""
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
    """``{"providers": [{id, name}], "default_id": int | None}`` for ``feature``.

    Empty list when nothing is configured/reachable — the tool then hides the
    dropdown and falls back to the admin default route.
    """
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
