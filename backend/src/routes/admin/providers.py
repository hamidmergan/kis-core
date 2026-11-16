"""Admin routes for the providers themselves and the dropdown metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.features.ai_providers.repository.feature_routes import (
    FALLBACK_FEATURES,
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.features.ai_providers.repository.providers import CONCURRENCY_BUCKETS
from src.i18n import get_locale, t
from src.routes.admin._models import (
    CreateProviderRequest,
    DiscoverVoicesRequest,
    UpdateProviderRequest,
)
from src.routes.admin._provider_shared import (
    _check_concurrency,
    _mask_provider,
    _require,
    _shared_provider,
)
from src.routes.admin.feature_routes import _reihenfolgen_neu
# The old import path of the pieces that moved into their own modules.
from src.routes.admin.feature_routes import list_feature_routes, set_feature_route, test_route  # noqa: F401
from src.routes.admin.provider_transfer import (  # noqa: F401
    build_export,
    build_import_preview,
    perform_clear_all,
    perform_import,
    validate_import_config,
)
from src.services.export_crypto import is_export_key_configured
from src.services.protocols import (
    CAPABILITIES,
    fixed_capabilities,
    known_protocols,
)
from src.services.provider_probe import probe_provider

router = APIRouter(tags=["admin: providers"])


# ─── Meta ──────────────────────────────────────────────────────────────────


@router.get("/providers/meta")
def get_provider_meta(_admin=Depends(_require)):
    """Fixed metadata for the dropdowns of the interface."""
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
        "api_key_encryption_enabled": is_export_key_configured(),
        "concurrency_buckets": list(CONCURRENCY_BUCKETS),
        "fallback_features": list(FALLBACK_FEATURES),
    }


# ─── Providers CRUD ────────────────────────────────────────────────────────


@router.get("/providers")
def list_providers(_admin=Depends(_require)):
    rows = db.list_providers()
    # The access key only goes out truncated, never in full.
    return {"providers": [_mask_provider(p) for p in rows]}


@router.post("/providers")
def create_provider(
    body: CreateProviderRequest,
    _admin=Depends(_require),
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
    concurrency = _check_concurrency(body.concurrency, locale) or {}

    # Where the first capability list comes from: protocol, admin choice or probe.
    fixed = fixed_capabilities(body.protocol) or ()
    if fixed:
        initial_caps: list[str] = list(fixed)
        seed = True  # probe will overwrite with same fixed list anyway
    elif body.initial_capabilities is not None:
        initial_caps = [c for c in body.initial_capabilities if c in CAPABILITIES]
        seed = False  # keep admin selection; probe only updates status
    else:
        initial_caps = []
        seed = True  # probe seeds capabilities automatically

    provider = db.create_provider(
        name=name,
        protocol=body.protocol,
        base_url=base_url,
        api_key=(body.api_key or None),
        capabilities=initial_caps,
        voices=[v.model_dump() for v in body.voices],
        enabled=body.enabled,
        concurrency=concurrency,
    )

    # Auto-probe synchronously so the response already carries probe results.
    probe_provider(provider["id"], seed_capabilities=seed)
    refreshed = _shared_provider(provider["id"])
    return {"provider": _mask_provider(refreshed)}


@router.get("/providers/{provider_id}")
def get_provider(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    row = _shared_provider(provider_id)
    if row is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    return {"provider": _mask_provider(row)}


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: int,
    body: UpdateProviderRequest,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    existing = _shared_provider(provider_id)
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
    if body.concurrency is not None:
        updates["concurrency"] = _check_concurrency(body.concurrency, locale)

    row = db.update_provider(provider_id, **updates)

    # Re-probe if connection-relevant fields changed.
    if any(k in updates for k in ("base_url", "api_key")):
        probe_provider(provider_id)
        row = _shared_provider(provider_id)
    # A provider switched off or without the ability hands its place to the next one in line.
    if any(k in updates for k in ("enabled", "capabilities", "voices")):
        _reihenfolgen_neu(locale)

    return {"provider": _mask_provider(row)}


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    if _shared_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    cleared = db.clear_provider_from_routes(provider_id)
    db.delete_provider(provider_id)
    _reihenfolgen_neu(locale)
    return {"ok": True, "routes_cleared": cleared}


@router.post("/providers/{provider_id}/probe")
def reprobe_provider(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    if _shared_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    result = probe_provider(provider_id)
    if result is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    row = _shared_provider(provider_id)
    return {
        "provider": _mask_provider(row),
        "probe": {
            "status": result.status,
            "error": result.error,
            "capabilities": result.capabilities,
        },
    }


@router.get("/providers/{provider_id}/affected-features")
def get_affected_features(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """Which features would lose their provider if this row went."""
    if _shared_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    affected = db.routes_using_provider(provider_id)
    return {"affected": affected}


# ─── Voice Discovery ───────────────────────────────────────────────────────


@router.post("/providers/discover-voices")
async def discover_voices(
    body: DiscoverVoicesRequest,
    _admin=Depends(_require),
):
    """Queries the provider's voices, the admin fills in the language themselves."""
    import httpx

    url = body.base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]

    voices_path = (body.voices_path or "/v1/audio/voices").lstrip("/")
    voices_url = f"{url}/{voices_path}"

    headers: dict = {"Accept": "application/json"}
    if body.api_key:
        headers["Authorization"] = f"Bearer {body.api_key}"

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(voices_url, headers=headers)
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
