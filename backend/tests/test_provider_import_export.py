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


# ─── Import preview ────────────────────────────────────────────────────────


def _valid_config(providers=None, routes=None):
    return {
        "schema_version": 1,
        "exported_at": "2026-05-28T12:00:00Z",
        "exported_from": "https://test.example",
        "providers": providers or [],
        "feature_routes": routes or [],
    }


def _exported_provider(name, *, protocol="openai_compat",
                       base_url="https://example.com",
                       capabilities=None, voices=None, enabled=True):
    return {
        "name": name, "protocol": protocol, "base_url": base_url,
        "capabilities": capabilities or [], "voices": voices or [],
        "enabled": enabled,
    }


def _exported_route(feature, provider_name=None, model_name=None,
                    user_choices=None, provider_models=None):
    return {
        "feature": feature, "provider_name": provider_name,
        "model_name": model_name,
        "user_choices": user_choices or [],
        "provider_models": provider_models or {},
    }


def test_preview_new_provider_action_create(monkeypatch):
    from src.routes.admin.providers import build_import_preview

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    cfg = _valid_config(providers=[_exported_provider("KISSKI")])

    result = build_import_preview(cfg)
    assert len(result["providers"]) == 1
    p = result["providers"][0]
    assert p["name"] == "KISSKI"
    assert p["action"] == "create"
    assert p["needs_api_key"] is True  # remote openai_compat
    assert p["existing_has_key"] is False
    assert p["protocol_change"] is None


def test_preview_existing_provider_action_update_preserves_key_flag(monkeypatch):
    from src.routes.admin.providers import build_import_preview

    existing = _make_provider(1, "KISSKI", api_key="sk-existing")
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [existing])
    cfg = _valid_config(providers=[_exported_provider("KISSKI")])

    result = build_import_preview(cfg)
    p = result["providers"][0]
    assert p["action"] == "update"
    assert p["existing_has_key"] is True


def test_preview_protocol_change_detected(monkeypatch):
    from src.routes.admin.providers import build_import_preview

    existing = _make_provider(1, "AltProvider", protocol="openai_compat")
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [existing])
    cfg = _valid_config(providers=[
        _exported_provider("AltProvider", protocol="deepl")
    ])

    result = build_import_preview(cfg)
    p = result["providers"][0]
    assert p["protocol_change"] == {"from": "openai_compat", "to": "deepl"}


def test_preview_needs_api_key_false_for_localhost(monkeypatch):
    from src.routes.admin.providers import build_import_preview

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    cfg = _valid_config(providers=[
        _exported_provider("Kokoro lokal",
                           base_url="http://localhost:8880/v1"),
    ])

    result = build_import_preview(cfg)
    p = result["providers"][0]
    assert p["needs_api_key"] is False


def test_preview_route_with_unknown_provider_skipped(monkeypatch):
    from src.routes.admin.providers import build_import_preview

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.get_route",
                        lambda f: None)
    cfg = _valid_config(
        providers=[_exported_provider("KISSKI")],
        routes=[
            _exported_route("chat", provider_name="KISSKI",
                            model_name="m1"),
            _exported_route("doc_translate", provider_name="GhostProvider"),
        ],
    )

    result = build_import_preview(cfg)
    routes_by_feature = {r["feature"]: r for r in result["routes"]}
    assert routes_by_feature["chat"]["action"] == "create"
    assert routes_by_feature["chat"]["resolved_provider"] == "KISSKI"
    assert routes_by_feature["doc_translate"]["action"] == "skip_unresolved"
    assert "GhostProvider" in routes_by_feature["doc_translate"]["reason"]


def test_preview_does_not_modify_db(monkeypatch):
    """Preview must be a pure read — verify no mutating DB calls happen."""
    from src.routes.admin.providers import build_import_preview

    create_mock = MagicMock()
    update_mock = MagicMock()
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.create_provider",
                        create_mock)
    monkeypatch.setattr("src.routes.admin.providers.db.update_provider",
                        update_mock)

    cfg = _valid_config(providers=[_exported_provider("KISSKI")])
    build_import_preview(cfg)

    create_mock.assert_not_called()
    update_mock.assert_not_called()


def test_validate_rejects_unknown_schema_version():
    from src.routes.admin.providers import validate_import_config
    import pytest
    from fastapi import HTTPException

    cfg = {"schema_version": 99, "exported_at": "x", "providers": [],
           "feature_routes": []}
    with pytest.raises(HTTPException) as exc:
        validate_import_config(cfg)
    assert exc.value.status_code == 400
    assert "schema" in exc.value.detail.lower() or "version" in exc.value.detail.lower()


def test_validate_rejects_unknown_protocol():
    from src.routes.admin.providers import validate_import_config
    import pytest
    from fastapi import HTTPException

    cfg = _valid_config(providers=[
        _exported_provider("X", protocol="nonsense_protocol")
    ])
    with pytest.raises(HTTPException) as exc:
        validate_import_config(cfg)
    assert exc.value.status_code == 400


def test_validate_rejects_unknown_capability():
    from src.routes.admin.providers import validate_import_config
    import pytest
    from fastapi import HTTPException

    cfg = _valid_config(providers=[
        _exported_provider("X", capabilities=["nonsense_capability"])
    ])
    with pytest.raises(HTTPException) as exc:
        validate_import_config(cfg)
    assert exc.value.status_code == 400


def test_validate_rejects_unknown_feature():
    from src.routes.admin.providers import validate_import_config
    import pytest
    from fastapi import HTTPException

    cfg = _valid_config(routes=[_exported_route("nonsense_feature")])
    with pytest.raises(HTTPException) as exc:
        validate_import_config(cfg)
    assert exc.value.status_code == 400


def test_validate_rejects_duplicate_provider_names():
    from src.routes.admin.providers import validate_import_config
    import pytest
    from fastapi import HTTPException

    cfg = _valid_config(providers=[
        _exported_provider("A"), _exported_provider("A"),
    ])
    with pytest.raises(HTTPException) as exc:
        validate_import_config(cfg)
    assert exc.value.status_code == 400
