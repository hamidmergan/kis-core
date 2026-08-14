"""Admin endpoints for the provider-centric AI configuration.

Two resources:

- ``/admin/providers``  - CRUD over the providers table + manual re-probe
- ``/admin/feature-routes`` - per-feature provider + model assignment
- ``/admin/providers/meta`` - static metadata for the UI dropdowns (known
  protocols, known capabilities, known feature ids).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger

from src import database as db
from src.features.ai_providers.repository.feature_routes import (
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.i18n import get_locale, t
from src.routes.admin._models import (
    CreateProviderRequest,
    DiscoverVoicesRequest,
    ImportConfigRequest,
    SetFeatureRouteRequest,
    UpdateProviderRequest,
)
from src.services.export_crypto import (
    is_envelope,
    is_export_key_configured,
    try_unwrap_api_key,
    wrap_api_key,
)
from src.services.protocols import (
    CAPABILITIES,
    fixed_capabilities,
    known_protocols,
)
from src.services.feature_route_check import run_feature_route_test
from src.services.provider_probe import probe_provider

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_PROVIDERS

router = APIRouter(tags=["admin: providers"])

# Anbieter, Modelle und die Zuordnung zu den Funktionen, beide Reiter.
_require = require_permission(PERM_SET_PROVIDERS)


# ─── Meta ──────────────────────────────────────────────────────────────────


@router.get("/providers/meta")
async def get_provider_meta(_admin=Depends(_require)):
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
        "api_key_encryption_enabled": is_export_key_configured(),
    }


# ─── Providers CRUD ────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers(_admin=Depends(_require)):
    rows = db.list_providers()
    # Mask api_key in responses - only the last 6 chars are returned for
    # UI display ("sk-...abc123"). The full key never leaves the backend.
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

    # Determine initial capability list:
    # - Protocol with fixed caps (deepl, docling) → use those.
    # - Admin provided explicit selection via initial_capabilities → use that,
    #   and probe only for status (not seeding), so the selection sticks.
    # - Otherwise → seed from probe result (default auto-detect behaviour).
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
    )

    # Auto-probe synchronously so the response already carries probe results.
    probe_provider(provider["id"], seed_capabilities=seed)
    refreshed = db.get_provider(provider["id"])
    return {"provider": _mask_provider(refreshed)}


@router.get("/providers/export")
async def export_config(
    _admin=Depends(_require),
):
    """Download the full AI config as JSON. Never includes api_keys."""
    payload = build_export(exported_from=None)
    filename = f"kis-ai-config-{date.today().isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    row = db.get_provider(provider_id)
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


@router.delete("/providers/all")
async def clear_all(_admin=Depends(_require)):
    return perform_clear_all()


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: int,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    if db.get_provider(provider_id) is None:
        raise HTTPException(404, t("admin.providers.notFound", locale))
    cleared = db.clear_provider_from_routes(provider_id)
    db.delete_provider(provider_id)
    return {"ok": True, "routes_cleared": cleared}


@router.post("/providers/{provider_id}/probe")
def reprobe_provider(
    provider_id: int,
    _admin=Depends(_require),
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
    _admin=Depends(_require),
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
    _admin=Depends(_require),
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


# ─── Feature routes ────────────────────────────────────────────────────────


@router.get("/feature-routes")
async def list_feature_routes(_admin=Depends(get_admin_user)):
    return {"routes": db.list_routes()}


@router.post("/feature-routes/{feature}/test")
def test_route(
    feature: str,
    provider_id: int | None = Query(None),
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Run a feature-specific live test against the route's assigned provider.

    Distinct from the provider probe (which only verifies reachability): this
    issues a minimal real request to the feature-specific endpoint with the
    configured model so the admin can confirm the feature/provider/model combo
    actually works, not just "the provider responds at /v1/models".

    Pass provider_id to test a specific provider using its per-provider model
    (provider_models[provider_id]) rather than the global model_name.
    """
    if feature not in FEATURES:
        raise HTTPException(400, t("admin.providers.unknownFeature", locale, feature=feature))
    routes = db.list_routes()
    row = next((r for r in routes if r["feature"] == feature), None)
    if row is None:
        raise HTTPException(400, t("admin.providers.testNoProvider", locale))
    provider_models = row.get("provider_models") or {}
    if provider_id is not None:
        provider = db.get_provider(provider_id)
        if provider is None:
            raise HTTPException(400, t("admin.providers.notFound", locale))
        model_name = provider_models.get(str(provider_id)) or row.get("model_name")
    else:
        if row.get("provider_id") is None:
            raise HTTPException(400, t("admin.providers.testNoProvider", locale))
        provider = db.get_provider(row["provider_id"])
        if provider is None:
            raise HTTPException(400, t("admin.providers.notFound", locale))
        model_name = provider_models.get(str(row["provider_id"])) or row.get("model_name")
    result = run_feature_route_test(
        feature=feature,
        protocol=provider["protocol"],
        base_url=provider["base_url"],
        api_key=provider.get("api_key"),
        model_name=model_name,
        voices=provider.get("voices") or [],
    )
    return {"status": result.status, "error": result.error, "warning": result.warning}


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
        provider_models=body.provider_models,
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


# ─── Export / Import ───────────────────────────────────────────────────────


SCHEMA_VERSION = 1


def build_export(*, exported_from: str | None) -> dict:
    """Build the export payload from current DB state.

    Translates feature_routes' provider_id (+ user_choices / provider_models
    keys) into provider names for portability. When ``KIS_EXPORT_KEY`` is
    configured, each provider's api_key is wrapped with AES-GCM and embedded
    in the export so the same deployment can restore it on import.
    """
    providers = db.list_providers()
    routes = db.list_routes()

    id_to_name = {p["id"]: p["name"] for p in providers}
    encrypt_keys = is_export_key_configured()

    exported_providers: list[dict] = []
    for p in providers:
        entry = {
            "name": p["name"],
            "protocol": p["protocol"],
            "base_url": p["base_url"],
            "capabilities": list(p.get("capabilities") or []),
            "voices": list(p.get("voices") or []),
            "enabled": bool(p.get("enabled", True)),
        }
        raw_key = p.get("api_key")
        if encrypt_keys and raw_key:
            entry["api_key"] = wrap_api_key(raw_key, provider_name=p["name"])
        exported_providers.append(entry)

    exported_routes: list[dict] = []
    for r in routes:
        user_choice_names = [
            id_to_name[pid] for pid in (r.get("user_choices") or [])
            if pid in id_to_name
        ]
        provider_models_named: dict[str, str] = {}
        for key, model in (r.get("provider_models") or {}).items():
            try:
                pid = int(key)
            except (TypeError, ValueError):
                continue
            if pid in id_to_name:
                provider_models_named[id_to_name[pid]] = model
        exported_routes.append({
            "feature": r["feature"],
            "provider_name": id_to_name.get(r.get("provider_id")),
            "model_name": r.get("model_name"),
            "user_choices": user_choice_names,
            "provider_models": provider_models_named,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_from": exported_from,
        "api_keys_encrypted": encrypt_keys,
        "providers": exported_providers,
        "feature_routes": exported_routes,
    }


def _needs_api_key(protocol: str, base_url: str) -> bool:
    """Heuristic: does this provider need an api_key?

    deepl always does. openai_compat usually does unless it's a local
    endpoint (Kokoro, local Ollama, etc.).
    """
    if protocol == "deepl":
        return True
    if protocol == "openai_compat":
        lowered = base_url.lower()
        if any(token in lowered for token in ("localhost", "127.0.0.1", "0.0.0.0")):
            return False
        return True
    return False  # docling and friends: no key needed


def validate_import_config(cfg: dict) -> None:
    """Validate an import payload before preview or commit. Raises 400."""
    if cfg.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(
            400,
            f"Unsupported schema_version {cfg.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION})",
        )

    bad_protocols = sorted({
        p["protocol"] for p in cfg.get("providers", [])
        if p.get("protocol") not in known_protocols()
    })
    if bad_protocols:
        raise HTTPException(400, f"Unknown protocols: {bad_protocols}")

    bad_caps: set[str] = set()
    for p in cfg.get("providers", []):
        for cap in p.get("capabilities", []):
            if cap not in CAPABILITIES:
                bad_caps.add(cap)
    if bad_caps:
        raise HTTPException(400, f"Unknown capabilities: {sorted(bad_caps)}")

    bad_features = sorted({
        r["feature"] for r in cfg.get("feature_routes", [])
        if r.get("feature") not in FEATURES
    })
    if bad_features:
        raise HTTPException(400, f"Unknown features: {bad_features}")

    names = [p["name"] for p in cfg.get("providers", [])]
    if len(names) != len(set(names)):
        dups = sorted({n for n in names if names.count(n) > 1})
        raise HTTPException(400, f"Duplicate provider names in import: {dups}")


def build_import_preview(cfg: dict) -> dict:
    """Compute the diff between current DB state and the import payload.

    Does NOT modify the DB.
    """
    validate_import_config(cfg)

    existing_by_name = {p["name"]: p for p in db.list_providers()}

    # Provider diffs.
    provider_diffs: list[dict] = []
    imported_names: set[str] = set()
    for p in cfg.get("providers", []):
        imported_names.add(p["name"])
        existing = existing_by_name.get(p["name"])
        action = "update" if existing else "create"
        protocol_change = None
        existing_has_key = False
        if existing:
            existing_has_key = bool(existing.get("api_key"))
            if existing["protocol"] != p["protocol"]:
                protocol_change = {
                    "from": existing["protocol"], "to": p["protocol"],
                }
        envelope = p.get("api_key")
        encrypted_key_present = is_envelope(envelope)
        encrypted_key_recoverable = (
            encrypted_key_present
            and try_unwrap_api_key(envelope, provider_name=p["name"]) is not None
        )
        provider_diffs.append({
            "name": p["name"],
            "action": action,
            "needs_api_key": _needs_api_key(p["protocol"], p["base_url"]),
            "existing_has_key": existing_has_key,
            "protocol_change": protocol_change,
            "encrypted_key_present": encrypted_key_present,
            "encrypted_key_recoverable": encrypted_key_recoverable,
        })

    # Route diffs. A route's resolved_provider must exist either in the
    # import payload OR on the target system after merge.
    available_names = set(existing_by_name.keys()) | imported_names

    route_diffs: list[dict] = []
    for r in cfg.get("feature_routes", []):
        pname = r.get("provider_name")
        if pname is None:
            route_diffs.append({
                "feature": r["feature"], "action": "skip_unresolved",
                "reason": "Keine Provider-Zuordnung im Export",
            })
            continue
        if pname not in available_names:
            route_diffs.append({
                "feature": r["feature"], "action": "skip_unresolved",
                "reason": f"Provider '{pname}' nicht im Import enthalten",
            })
            continue
        # action is "update" if a route for that feature already exists,
        # else "create". We need list_routes to determine that.
        action = "update" if _route_exists(r["feature"]) else "create"
        route_diffs.append({
            "feature": r["feature"], "action": action,
            "resolved_provider": pname,
        })

    return {"providers": provider_diffs, "routes": route_diffs}


def _route_exists(feature: str) -> bool:
    """Helper: is there already a row in feature_routes for this feature?"""
    return db.get_route(feature) is not None


@router.post("/providers/import/preview")
async def import_preview(
    body: ImportConfigRequest,
    _admin=Depends(_require),
):
    return build_import_preview(body.config.model_dump())


def perform_import(cfg: dict) -> dict:
    """Apply an import payload to the DB. Merge mode: never wipes
    existing rows, never touches existing api_keys."""
    validate_import_config(cfg)

    # ── Provider merge ──
    existing_by_name = {p["name"]: p for p in db.list_providers()}
    providers_created = 0
    providers_updated = 0
    providers_needing_key: list[str] = []

    for p in cfg.get("providers", []):
        existing = existing_by_name.get(p["name"])
        capabilities = [c for c in p.get("capabilities", []) if c in CAPABILITIES]
        voices = list(p.get("voices") or [])
        envelope = p.get("api_key")
        recovered_key = (
            try_unwrap_api_key(envelope, provider_name=p["name"])
            if is_envelope(envelope)
            else None
        )
        if existing is None:
            row = db.create_provider(
                name=p["name"], protocol=p["protocol"],
                base_url=p["base_url"], api_key=recovered_key,
                capabilities=capabilities, voices=voices,
                enabled=bool(p.get("enabled", True)),
            )
            providers_created += 1
        else:
            # Only restore the key if the existing row has none — never
            # clobber an admin-set key with a possibly stale envelope.
            update_kwargs: dict = {
                "protocol": p["protocol"], "base_url": p["base_url"],
                "capabilities": capabilities, "voices": voices,
                "enabled": bool(p.get("enabled", True)),
            }
            if recovered_key and not existing.get("api_key"):
                update_kwargs["api_key"] = recovered_key
            row = db.update_provider(existing["id"], **update_kwargs)
            providers_updated += 1
        # Re-probe so probe_status reflects current reachability.
        probe_provider(row["id"])
        # row already carries api_key via the RETURNING clause; we only set
        # it on create or when restoring into an empty existing row.
        if _needs_api_key(p["protocol"], p["base_url"]) and not row.get("api_key"):
            providers_needing_key.append(p["name"])

    # ── Route merge ──
    # Refresh provider name → id map after the create/update pass.
    name_to_id = {p["name"]: p["id"] for p in db.list_providers()}
    existing_routes = {r["feature"]: r for r in db.list_routes()}
    routes_created = 0
    routes_updated = 0
    routes_skipped = 0
    embedding_changed = False

    for r in cfg.get("feature_routes", []):
        pname = r.get("provider_name")
        if pname is None or pname not in name_to_id:
            routes_skipped += 1
            continue
        pid = name_to_id[pname]
        user_choice_ids = [
            name_to_id[n] for n in (r.get("user_choices") or [])
            if n in name_to_id
        ]
        provider_models: dict[str, str] = {}
        for n, model in (r.get("provider_models") or {}).items():
            if n in name_to_id:
                provider_models[str(name_to_id[n])] = model

        db.set_route(
            r["feature"],
            provider_id=pid,
            model_name=r.get("model_name"),
            user_choices=user_choice_ids,
            provider_models=provider_models,
        )
        if r["feature"] in existing_routes:
            routes_updated += 1
        else:
            routes_created += 1
        if r["feature"] == "embedding":
            embedding_changed = True

    if embedding_changed:
        from src.routes.admin._embedding import invalidate_fingerprint_cache
        invalidate_fingerprint_cache()

    return {
        "providers_created": providers_created,
        "providers_updated": providers_updated,
        "routes_created": routes_created,
        "routes_updated": routes_updated,
        "routes_skipped": routes_skipped,
        "providers_needing_key": providers_needing_key,
    }


@router.post("/providers/import")
def import_config(
    body: ImportConfigRequest,
    _admin=Depends(_require),
):
    return perform_import(body.config.model_dump())


def perform_clear_all() -> dict:
    """Wipe all providers + feature_routes. Destructive."""
    routes_deleted = db.delete_all_routes()
    providers_deleted = db.delete_all_providers()

    from src.routes.admin._embedding import invalidate_fingerprint_cache
    invalidate_fingerprint_cache()

    return {
        "providers_deleted": providers_deleted,
        "routes_deleted": routes_deleted,
    }

