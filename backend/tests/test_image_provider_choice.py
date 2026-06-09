"""Image tools: end-user provider choice (generate / edit / analyze).

Covers the route-level validation + listing delegation and that the task HTTP
client routes an explicit pick through the capability-based service.
"""

import pytest
from fastapi import HTTPException


# ─── route validation + listing ─────────────────────────────────────────────


def test_validate_provider_allows_none(monkeypatch):
    from src.routes import image
    # None must never be rejected and must not consult the service.
    monkeypatch.setattr(
        image.feature_provider_choices, "is_eligible",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("checked on None")),
    )
    image._validate_provider("image_gen", None, "de")  # no raise


def test_validate_provider_rejects_ineligible(monkeypatch):
    from src.routes import image
    monkeypatch.setattr(image.feature_provider_choices, "is_eligible", lambda f, pid: False)
    with pytest.raises(HTTPException) as exc:
        image._validate_provider("image_gen", 999, "de")
    assert exc.value.status_code == 400


def test_validate_provider_accepts_eligible(monkeypatch):
    from src.routes import image
    monkeypatch.setattr(image.feature_provider_choices, "is_eligible", lambda f, pid: True)
    image._validate_provider("vision", 21, "de")  # no raise


async def test_list_image_providers_maps_tab_to_feature(monkeypatch):
    from src.routes import image
    seen = {}

    async def fake_list(feature):
        seen["feature"] = feature
        return {"providers": [], "default_id": None}

    monkeypatch.setattr(image.feature_provider_choices, "list_reachable_choices", fake_list)

    await image.list_image_providers("generate", _user={})
    assert seen["feature"] == "image_gen"
    await image.list_image_providers("edit", _user={})
    assert seen["feature"] == "image_edit"
    await image.list_image_providers("analyze", _user={})
    assert seen["feature"] == "vision"


async def test_list_image_providers_unknown_tab(monkeypatch):
    from src.routes import image
    result = await image.list_image_providers("bogus", _user={})
    assert result == {"providers": [], "default_id": None}


# ─── task HTTP client routing ────────────────────────────────────────────────


def _binding(model="flux.1-dev"):
    from src.services.feature_router import FeatureBinding
    return FeatureBinding(
        feature="image_gen",
        provider={"base_url": "http://img.example.com", "name": "myLab", "api_key": "k"},
        model=model,
    )


def test_image_http_client_explicit_provider_uses_service(monkeypatch):
    from src.tasks import general_tasks
    captured = {}

    def fake_resolve_binding(feature, provider_id):
        captured["feature"] = feature
        captured["provider_id"] = provider_id
        return _binding()

    monkeypatch.setattr(
        "src.services.feature_provider_choices.resolve_binding", fake_resolve_binding
    )
    monkeypatch.setattr(
        "src.services.feature_router.resolve",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("default path used")),
    )

    base, model, client = general_tasks._image_http_client("image_gen", provider_id=5)
    client.close()
    assert captured == {"feature": "image_gen", "provider_id": 5}
    assert base == "http://img.example.com/v1"
    assert model == "flux.1-dev"


def test_image_http_client_default_uses_route(monkeypatch):
    from src.tasks import general_tasks
    captured = {}

    def fake_resolve(feature):
        captured["feature"] = feature
        return _binding()

    monkeypatch.setattr("src.services.feature_router.resolve", fake_resolve)

    base, model, client = general_tasks._image_http_client("vision")
    client.close()
    assert captured == {"feature": "vision"}
    assert base == "http://img.example.com/v1"
