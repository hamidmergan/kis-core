"""Admin endpoints for the provider-centric AI configuration.

Two resources:

- ``/admin/providers``  - CRUD over the providers table + manual re-probe
- ``/admin/feature-routes`` - per-feature provider + model assignment
- ``/admin/providers/meta`` - static metadata for the UI dropdowns (known
  protocols, known capabilities, known feature ids).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_admin_user
from src.features.ai_providers.repository.feature_routes import (
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.i18n import get_locale, t
from src.routes.admin._models import (
    CreateProviderRequest,
    DiscoverVoicesRequest,
    SetFeatureRouteRequest,
    UpdateProviderRequest,
)
from src.services.protocols import (
    CAPABILITIES,
    fixed_capabilities,
    known_protocols,
)
from src.services.feature_route_test import test_feature_route
from src.services.provider_probe import probe_provider

router = APIRouter(tags=["admin: providers"])


# ─── Meta ──────────────────────────────────────────────────────────────────


@router.get("/providers/meta")
async def get_provider_meta(_admin=Depends(get_admin_user)):
    """Static metadata for the admin UI: protocol dropdown, capability list,
    feature list. Frontend reads this once on page load."""
    protocols = []
    for proto in known_protocols():
        protocols.append({
            "id": proto,
            "fixed_capabilities": list(fixed_capabilities(proto) or []),
        })
    return {
        "protocols": protocols,
        "capabilities": list(CAPABILITIES),
        "features": list(FEATURES),
        "user_choice_features": sorted(USER_CHOICE_FEATURES),
    }


# ─── Providers CRUD ────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers(_admin=Depends(get_admin_user)):
    rows = db.list_providers()
    # Mask api_key in responses - only the last 6 chars are returned for
    # UI display ("sk-...abc123"). The full key never leaves the backend.
    return {"providers": [_mask_provider(p) for p in rows]}


@router.post("/providers")
async def create_provider(
    body: CreateProviderRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    name = body.name.strip()
    base_url = body.base_url.strip()
    if not name or not base_url:
        raise HTTPException(400, t("admin.providers.requiredFields", locale))
    if body.protocol not in known_protocols():
        raise HTTPException(400, t("admin.providers.unknownProtocol", locale, protocol=body.protocol))
    if db.get_provider_by_name(name) is not None:
        raise HTTPException(409, t("admin.providers.nameTaken", locale, name=name))

    # Seed capabilities from the protocol's fixed list (if any) so the row is
    # immediately usable in feature-route dropdowns even before the probe runs.
    fixed = fixed_capabilities(body.protocol) or ()
    provider = db.create_provider(
        name=name,
        protocol=body.protocol,
        base_url=base_url,
        api_key=(body.api_key or None),
        capabilities=list(fixed),
        voices=[v.model_dump() for v in body.voices],
        enabled=body.enabled,
    )

    # Auto-probe synchronously so the response already carries probe results.
    # ``seed_capabilities=True`` is the only path that overwrites the row's
    # capability list — re-probe later does not, so manual edits stick.
    probe_provider(provider["id"], seed_capabilities=True)
    refreshed = db.get_provider(provider["id"])
    return {"provider": _mask_provider(refreshed)}


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: int,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    row = db.get_provider(provider_id)
    if row is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    return {"provider": _mask_provider(row)}


@router.patch("/providers/{provider_id}")
async def update_provider(
    provider_id: int,
    body: UpdateProviderRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    existing = db.get_provider(provider_id)
    if existing is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))

    updates: dict = {}
    if body.name is not None:
        new_name = body.name.strip()
        if not new_name:
            raise HTTPException(400, t("admin.providers.requiredFields", locale))
        collision = db.get_provider_by_name(new_name)
        if collision and collision["id"] != provider_id:
            raise HTTPException(409, t("admin.providers.nameTaken", locale, name=new_name))
        updates["name"] = new_name
    if body.base_url is not None:
        base_url = body.base_url.strip()
        if not base_url:
            raise HTTPException(400, t("admin.providers.requiredFields", locale))
        updates["base_url"] = base_url
    if body.api_key is not None:
        # Empty string clears the key.
        updates["api_key"] = body.api_key or None
    if body.capabilities is not None:
        bad = [c for c in body.capabilities if c not in CAPABILITIES]
        if bad:
            raise HTTPException(400, t("admin.providers.unknownCapability", locale, items=bad))
        updates["capabilities"] = sorted(set(body.capabilities))
    if body.voices is not None:
        updates["voices"] = [v.model_dump() for v in body.voices]
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    row = db.update_provider(provider_id, **updates)

    # Re-probe if connection-relevant fields changed.
    if any(k in updates for k in ("base_url", "api_key")):
        probe_provider(provider_id)
        row = db.get_provider(provider_id)

    return {"provider": _mask_provider(row)}


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    if db.get_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    cleared = db.clear_provider_from_routes(provider_id)
    db.delete_provider(provider_id)
    return {"ok": True, "routes_cleared": cleared}


@router.post("/providers/{provider_id}/probe")
async def reprobe_provider(
    provider_id: int,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    result = probe_provider(provider_id)
    if result is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    row = db.get_provider(provider_id)
    return {
        "provider": _mask_provider(row),
        "probe": {
            "status": result.status,
            "error": result.error,
            "capabilities": result.capabilities,
        },
    }


@router.get("/providers/{provider_id}/affected-features")
async def get_affected_features(
    provider_id: int,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Used by the delete-confirmation dialog: which features would lose their
    provider if this row was removed."""
    if db.get_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    affected = db.routes_using_provider(provider_id)
    return {"affected": affected}


# ─── Voice Discovery ───────────────────────────────────────────────────────


@router.post("/providers/discover-voices")
async def discover_voices(
    body: DiscoverVoicesRequest,
    _admin=Depends(get_admin_user),
):
    """Try GET {base_url}/v1/audio/voices and return whatever the provider exposes.

    On success: ``{ voices: [{ voice_id, name }], discoverable: true }``
    On failure (404, timeout, unreachable): ``{ voices: [], discoverable: false }``

    The ``language`` field is intentionally NOT filled in — the admin must set
    it manually since providers don't expose language metadata.
    """
    import httpx

    url = body.base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]

    headers: dict = {"Accept": "application/json"}
    if body.api_key:
        headers["Authorization"] = f"Bearer {body.api_key}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{url}/v1/audio/voices", headers=headers)
        if resp.status_code != 200:
            return {"voices": [], "discoverable": False}

        data = resp.json()
        raw = data.get("voices") or data.get("data", [])
        voices = []
        for v in raw:
            if isinstance(v, str):
                voices.append({"voice_id": v, "name": v, "language": ""})
            elif isinstance(v, dict):
                vid = v.get("id") or v.get("voice_id") or v.get("name", "")
                vname = v.get("name") or vid
                voices.append({"voice_id": vid, "name": vname, "language": ""})
        return {"voices": voices, "discoverable": True}

    except Exception as exc:
        logger.debug("discover-voices failed for {}: {}", body.base_url, exc)
        return {"voices": [], "discoverable": False}


# ─── Feature routes ────────────────────────────────────────────────────────


@router.get("/feature-routes")
async def list_feature_routes(_admin=Depends(get_admin_user)):
    return {"routes": db.list_routes()}


@router.post("/feature-routes/{feature}/test")
async def test_route(
    feature: str,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Run a feature-specific live test against the route's assigned provider.

    Distinct from the provider probe (which only verifies reachability): this
    issues a minimal real request to the feature-specific endpoint with the
    configured model so the admin can confirm "TTS @ KISSKI" actually works,
    not just "the provider responds at /v1/models".
    """
    if feature not in FEATURES:
        raise HTTPException(400, t("admin.providers.unknownFeature", locale, feature=feature))
    routes = db.list_routes()
    row = next((r for r in routes if r["feature"] == feature), None)
    if row is None or row.get("provider_id") is None:
        raise HTTPException(400, t("admin.providers.testNoProvider", locale))
    provider = db.get_provider(row["provider_id"])
    if provider is None:
        raise HTTPException(400, t("admin.providers.notFound", locale))
    result = test_feature_route(
        feature=feature,
        protocol=provider["protocol"],
        base_url=provider["base_url"],
        api_key=provider.get("api_key"),
        model_name=row.get("model_name"),
    )
    return {"status": result.status, "error": result.error}


@router.patch("/feature-routes/{feature}")
async def set_feature_route(
    feature: str,
    body: SetFeatureRouteRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    if feature not in FEATURES:
        raise HTTPException(400, t("admin.providers.unknownFeature", locale, feature=feature))

    # Validate referenced provider ids exist.
    if body.provider_id is not None and db.get_provider(body.provider_id) is None:
        raise HTTPException(400, t("admin.providers.notFound", locale))
    if body.user_choices:
        if feature not in USER_CHOICE_FEATURES:
            raise HTTPException(
                400,
                t("admin.providers.userChoiceNotSupported", locale, feature=feature),
            )
        for pid in body.user_choices:
            if db.get_provider(pid) is None:
                raise HTTPException(
                    400,
                    t("admin.providers.userChoiceUnknownProvider", locale, provider_id=pid),
                )

    row = db.set_route(
        feature,
        provider_id=body.provider_id,
        model_name=(body.model_name or None),
        user_choices=body.user_choices,
    )

    # Changing the embedding route makes any persisted fingerprint stale —
    # the next call to ``get_cached_fingerprint`` must recompute against the
    # new provider+model so the workspace reindex check uses the right value.
    if feature == "embedding":
        from src.routes.admin._embedding import invalidate_fingerprint_cache
        invalidate_fingerprint_cache()

    return {"route": row}


# ─── Helpers ───────────────────────────────────────────────────────────────


def _mask_provider(row: dict | None) -> dict | None:
    """Mask the raw api_key. The UI only ever sees the last 6 chars + a flag."""
    if row is None:
        return None
    masked = dict(row)
    raw = row.get("api_key")
    if raw:
        masked["api_key_set"] = True
        masked["api_key_last_chars"] = raw[-6:] if len(raw) > 6 else raw
    else:
        masked["api_key_set"] = False
        masked["api_key_last_chars"] = None
    masked.pop("api_key", None)
    return masked
