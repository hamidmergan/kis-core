"""Unit tests for AI config export/import endpoints.

Style: monkeypatch on src.routes.admin.providers.db.* — matches
test_translate_provider.py, no real DB required.
"""
from unittest.mock import MagicMock


def _make_provider(id, name, *, protocol="openai_compat", api_key=None,
                   base_url="http://example.com", capabilities=None,
                   voices=None, enabled=True):
    return {
        "id": id, "name": name, "protocol": protocol, "api_key": api_key,
        "base_url": base_url, "enabled": enabled,
        "capabilities": capabilities or [],
        "voices": voices or [],
    }


def _make_route(feature, provider_id=None, model_name=None,
                user_choices=None, provider_models=None):
    return {
        "feature": feature, "provider_id": provider_id,
        "model_name": model_name,
        "user_choices": user_choices or [],
        "provider_models": provider_models or {},
    }


def test_export_empty_db_returns_empty_arrays(monkeypatch):
    from src.routes.admin.providers import build_export

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])

    result = build_export(exported_from=None)
    assert result["schema_version"] == 1
    assert result["providers"] == []
    assert result["feature_routes"] == []
    assert "exported_at" in result


def test_export_strips_api_keys_and_ids(monkeypatch):
    from src.routes.admin.providers import build_export

    monkeypatch.setattr(
        "src.routes.admin.providers.db.list_providers",
        lambda: [_make_provider(1, "KISSKI", api_key="sk-secret",
                                capabilities=["chat"])],
    )
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])

    result = build_export(exported_from=None)
    assert len(result["providers"]) == 1
    p = result["providers"][0]
    assert "api_key" not in p
    assert "id" not in p
    assert p["name"] == "KISSKI"
    assert p["capabilities"] == ["chat"]


def test_export_translates_route_ids_to_provider_names(monkeypatch):
    from src.routes.admin.providers import build_export

    providers = [
        _make_provider(1, "KISSKI"),
        _make_provider(2, "DeepL DE-EN", protocol="deepl"),
    ]
    routes = [
        _make_route("chat", provider_id=1, model_name="mistral-large"),
        _make_route("doc_translate", provider_id=2,
                    user_choices=[1, 2],
                    provider_models={"1": "mistral-small", "2": ""}),
    ]
    monkeypatch.setattr(
        "src.routes.admin.providers.db.list_providers", lambda: providers
    )
    monkeypatch.setattr(
        "src.routes.admin.providers.db.list_routes", lambda: routes
    )

    result = build_export(exported_from=None)
    chat = next(r for r in result["feature_routes"] if r["feature"] == "chat")
    assert chat["provider_name"] == "KISSKI"
    assert chat["model_name"] == "mistral-large"

    tr = next(r for r in result["feature_routes"]
              if r["feature"] == "doc_translate")
    assert tr["provider_name"] == "DeepL DE-EN"
    assert sorted(tr["user_choices"]) == sorted(["KISSKI", "DeepL DE-EN"])
    assert tr["provider_models"] == {
        "KISSKI": "mistral-small", "DeepL DE-EN": ""
    }


def test_export_drops_routes_with_missing_provider_id(monkeypatch):
    """An orphaned route (provider_id refers to a deleted provider) should
    not crash the export — its provider_name becomes null."""
    from src.routes.admin.providers import build_export

    monkeypatch.setattr(
        "src.routes.admin.providers.db.list_providers",
        lambda: [_make_provider(1, "KISSKI")],
    )
    monkeypatch.setattr(
        "src.routes.admin.providers.db.list_routes",
        lambda: [_make_route("chat", provider_id=999, model_name="x")],
    )

    result = build_export(exported_from=None)
    chat = next(r for r in result["feature_routes"] if r["feature"] == "chat")
    assert chat["provider_name"] is None
