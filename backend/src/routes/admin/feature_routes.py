"""Admin routes for the feature routes: which provider and model serve which function."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from src import database as db
from src.features.ai_providers.repository.feature_routes import (
    FALLBACK_CAPABILITY,
    FALLBACK_FEATURES,
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.i18n import get_locale, t
from src.routes.admin._models import SetFeatureRouteRequest
from src.routes.admin._provider_shared import _require, _shared_provider
from src.services.feature_route_check import run_feature_route_test

router = APIRouter(tags=["admin: providers"])


@router.get("/feature-routes")
def list_feature_routes(_admin=Depends(_require)):
    """All routes, each with what was measured about its model."""
    from src.services import model_limits

    routen = db.list_routes()
    for route in routen:
        modelle = route.get("provider_models") or {}
        modell = modelle.get(str(route.get("provider_id"))) or route.get("model_name")
        route["limits"] = model_limits.as_dict(
            model_limits.stored_profile(route.get("provider_id"), modell)
        )
    return {"routes": routen}


@router.post("/feature-routes/{feature}/test")
def test_route(
    feature: str,
    provider_id: int | None = Query(None),
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """A real test call against the route's provider, not just a reachability probe."""
    if feature not in FEATURES:
        raise HTTPException(400, t("admin.providers.unknownFeature", locale, feature=feature))
    routes = db.list_routes()
    row = next((r for r in routes if r["feature"] == feature), None)
    if row is None:
        raise HTTPException(400, t("admin.providers.testNoProvider", locale))
    # Without a named provider the test runs against the first choice of the route.
    pid = provider_id if provider_id is not None else row.get("provider_id")
    if pid is None:
        raise HTTPException(400, t("admin.providers.testNoProvider", locale))
    provider = _shared_provider(pid)
    if provider is None:
        raise HTTPException(400, t("admin.providers.notFound", locale))
    model_name = (row.get("provider_models") or {}).get(str(pid)) or row.get("model_name")
    result = run_feature_route_test(
        feature=feature,
        protocol=provider["protocol"],
        base_url=provider["base_url"],
        api_key=provider.get("api_key"),
        model_name=model_name,
        voices=provider.get("voices") or [],
    )
    return {
        "status": result.status,
        "error": result.error,
        "warning": result.warning,
        "limits": _measure_route_model(provider, model_name, feature) if result.status == "ok" else None,
    }


def _measure_route_model(provider: dict, model_name: str | None, feature: str) -> dict | None:
    """Measures the route's model, a failed measurement is not an error."""
    from src.services import model_limits

    if feature not in model_limits.CHAT_LIKE_FEATURES or not model_name:
        return None
    try:
        return model_limits.as_dict(model_limits.remeasure(provider, model_name))
    except Exception as e:  # noqa: BLE001
        logger.debug("Nebenmessung fehlgeschlagen: {}", e)
        return None


# Bounds of the sampling values, the providers refuse anything outside anyway.
_SAMPLING_GRENZEN = {"temperature": (0.0, 2.0), "top_p": (0.0, 1.0)}


def _pruefe_sampling(feature: str, roh: dict | None, locale: str) -> dict | None:
    """Keeps only known keys within their bounds, empty entries are dropped."""
    from src.services import model_limits

    if roh is None:
        return None
    if roh and feature not in model_limits.CHAT_LIKE_FEATURES:
        raise HTTPException(400, t("admin.providers.samplingNotSupported", locale,
                                   feature=feature))
    sauber: dict[str, dict[str, float]] = {}
    for pid, werte in roh.items():
        if not isinstance(werte, dict):
            continue
        eintrag: dict[str, float] = {}
        for schluessel, (unten, oben) in _SAMPLING_GRENZEN.items():
            wert = werte.get(schluessel)
            if wert is None:
                continue
            if not unten <= float(wert) <= oben:
                raise HTTPException(400, t("admin.providers.samplingOutOfRange", locale,
                                           feld=schluessel, min=unten, max=oben))
            eintrag[schluessel] = float(wert)
        if eintrag:
            sauber[str(pid)] = eintrag
    return sauber


def _check_fallback(feature: str, body: SetFeatureRouteRequest, locale: str) -> int | None:
    """Validates the fallback provider of a route, a route without a first choice has none."""
    fallback_id = body.fallback_provider_id
    # People pick their voice themselves, so a voice fallback stands on its own and may be the route's provider.
    voice = feature == "tts"
    if fallback_id is None or (body.provider_id is None and not voice):
        return None
    if feature not in FALLBACK_FEATURES:
        raise HTTPException(422, t("admin.providers.fallbackNotSupported", locale,
                                   feature=feature))
    if fallback_id == body.provider_id and not voice:
        raise HTTPException(422, t("admin.providers.fallbackSameAsPrimary", locale))
    provider = _shared_provider(fallback_id)
    if provider is None:
        raise HTTPException(422, t("admin.providers.fallbackUnknownProvider", locale,
                                   provider_id=fallback_id))
    if not provider.get("enabled"):
        raise HTTPException(422, t("admin.providers.fallbackDisabled", locale))
    if provider.get("protocol") != "openai_compat":
        raise HTTPException(422, t("admin.providers.fallbackProtocol", locale))
    capability = FALLBACK_CAPABILITY[feature]
    if capability not in (provider.get("capabilities") or []):
        raise HTTPException(422, t("admin.providers.fallbackCapability", locale,
                                   capability=capability))
    # A voice job that switches over needs at least one voice to speak with.
    if feature == "tts" and not any(v.get("voice_id") for v in provider.get("voices") or []):
        raise HTTPException(422, t("admin.providers.fallbackNoVoices", locale))
    models = body.provider_models or {}
    model = (models.get(str(fallback_id)) or "").strip()
    if not model:
        raise HTTPException(422, t("admin.providers.fallbackNoModel", locale))
    if feature == "embedding":
        primary = (models.get(str(body.provider_id)) or body.model_name or "").strip()
        if model != primary:
            raise HTTPException(422, t("admin.providers.fallbackEmbeddingModel", locale,
                                       model=primary))
    return fallback_id


def _aus_reihenfolge(feature: str, body: SetFeatureRouteRequest, locale: str) -> None:
    """First choice and fallback out of the order: the first provider that can serve, then the next."""
    models = body.provider_models or {}
    ids = [pid for pid in dict.fromkeys(body.provider_order or []) if _shared_provider(pid) is not None]
    body.provider_order = ids

    # Translating also runs on a translation service of its own, such as DeepL.
    faehig = {FALLBACK_CAPABILITY[feature]} | ({"translation"} if feature.endswith("_translate") else set())

    def bereit(pid: int) -> bool:
        provider = _shared_provider(pid)
        # Only an OpenAI compatible interface needs a model, the others bring their own.
        return bool(provider and provider.get("enabled")
                    and faehig & set(provider.get("capabilities") or [])
                    and (provider.get("protocol") != "openai_compat" or (models.get(str(pid)) or "").strip()))

    erste = next((pid for pid in ids if bereit(pid)), None)
    body.provider_id = erste
    body.model_name = (models.get(str(erste)) or "").strip() or None
    body.fallback_provider_id = None
    for pid in ids[ids.index(erste) + 1:] if erste is not None else []:
        body.fallback_provider_id = pid
        try:
            _check_fallback(feature, body, locale)
            return
        except HTTPException:
            body.fallback_provider_id = None


def _reihenfolgen_neu(locale: str) -> None:
    """Every ordered route takes its first choice and fallback anew, after a provider changed or went."""
    for route in db.list_routes():
        if not route.get("provider_order"):
            continue
        body = SetFeatureRouteRequest(
            provider_models=route.get("provider_models") or {},
            provider_order=route.get("provider_order"),
        )
        _aus_reihenfolge(route["feature"], body, locale)
        db.set_route(
            route["feature"],
            provider_id=body.provider_id,
            model_name=body.model_name,
            user_choices=route.get("user_choices") or [],
            provider_models=route.get("provider_models") or {},
            provider_sampling=route.get("provider_sampling") or {},
            fallback_provider_id=body.fallback_provider_id,
            provider_order=body.provider_order,
        )


@router.patch("/feature-routes/{feature}")
def set_feature_route(
    feature: str,
    body: SetFeatureRouteRequest,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    if feature not in FEATURES:
        raise HTTPException(400, t("admin.providers.unknownFeature", locale, feature=feature))

    # Validate referenced provider ids exist.
    if body.provider_id is not None and _shared_provider(body.provider_id) is None:
        raise HTTPException(400, t("admin.providers.notFound", locale))
    if body.user_choices:
        if feature not in USER_CHOICE_FEATURES:
            raise HTTPException(
                400,
                t("admin.providers.userChoiceNotSupported", locale, feature=feature),
            )
        for pid in body.user_choices:
            if _shared_provider(pid) is None:
                raise HTTPException(
                    400,
                    t("admin.providers.userChoiceUnknownProvider", locale, provider_id=pid),
                )

    if body.provider_order is not None:
        _aus_reihenfolge(feature, body, locale)
    sampling = _pruefe_sampling(feature, body.provider_sampling, locale)
    fallback_id = _check_fallback(feature, body, locale)

    row = db.set_route(
        feature,
        provider_id=body.provider_id,
        model_name=(body.model_name or None),
        user_choices=body.user_choices,
        provider_models=body.provider_models,
        provider_sampling=sampling,
        fallback_provider_id=fallback_id,
        provider_order=body.provider_order,
    )

    # Changing the embedding route invalidates the stored fingerprint.
    if feature == "embedding":
        from src.routes.admin._embedding import invalidate_fingerprint_cache
        invalidate_fingerprint_cache()

    # A newly registered model is measured right away.
    limits = None
    if body.provider_id is not None:
        provider = _shared_provider(body.provider_id)
        modelle = row.get("provider_models") or {}
        modell = modelle.get(str(body.provider_id)) or row.get("model_name")
        if provider:
            limits = _measure_route_model(provider, modell, feature)

    return {"route": row, "limits": limits}
