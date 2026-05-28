# AI Configuration Export/Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin kann die komplette KI-Konfiguration (Provider, Voices, Capabilities, Feature-Routes inkl. Modellnamen und user_choices) als JSON-Datei exportieren, importieren (Merge-Modus), und über ein separates Drei-Punkte-Menü einen Komplett-Reset durchführen. API-Keys werden niemals exportiert.

**Architecture:**
- **Backend:** Vier neue Endpoints in `backend/src/routes/admin/providers.py`: `GET /export`, `POST /import/preview` (dry-run), `POST /import` (commit), `DELETE /all`. Pydantic-Modelle in `_models.py`. Provider-Identifikation portabel über `name` statt `id`.
- **Frontend:** Neue Buttons im `ProviderListCard`-Header (Export/Import + Drei-Punkte-Menü), neue Komponenten `ImportPreviewDialog.tsx` und `ClearAllConfirmDialog.tsx`. Warn-Indikator (⚠ Icon) bei Providern ohne Key in der Provider-Liste.
- **Tests:** Backend via `monkeypatch` auf `src.routes.admin.providers.db.*` (Pattern matching `test_translate_provider.py`). Frontend: manuelle Checkliste (Projekt-Konvention).

**Tech Stack:** FastAPI, Pydantic, psycopg2, Next.js 14 (App Router), React, TypeScript, Tailwind, next-intl, Phosphor Icons.

**Reference Spec:** [docs/superpowers/specs/2026-05-28-ai-config-export-import-design.md](../specs/2026-05-28-ai-config-export-import-design.md)

---

## File Map

**Backend — Modify:**
- `backend/src/routes/admin/_models.py` — neue Pydantic-Modelle für Export-Schema
- `backend/src/routes/admin/providers.py` — vier neue Endpoints + Helper-Funktionen

**Backend — Create:**
- `backend/tests/test_provider_import_export.py` — vollständige Tests für alle vier Endpoints

**Frontend — Modify:**
- `frontend/src/app/[locale]/admin/_components/providers/_api.ts` — vier neue API-Funktionen
- `frontend/src/app/[locale]/admin/_components/providers/_types.ts` — Types für Preview-Response
- `frontend/src/app/[locale]/admin/_components/providers/index.tsx` — Handler für Export/Import/Clear, Dialog-State
- `frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx` — neue Buttons im Header + Warn-Indikator pro Row
- `frontend/messages/de.json` — neue Strings unter `admin.providers.exportImport.*` + `admin.providers.clearAll.*` + `admin.providers.row.missingKeyTooltip`
- `frontend/messages/en.json` — analog

**Frontend — Create:**
- `frontend/src/app/[locale]/admin/_components/providers/ImportPreviewDialog.tsx`
- `frontend/src/app/[locale]/admin/_components/providers/ClearAllConfirmDialog.tsx`

---

## Task 1: Pydantic-Modelle für Export-Schema

**Files:**
- Modify: `backend/src/routes/admin/_models.py` (append at end)

- [ ] **Step 1: Add export schema models**

Append to `backend/src/routes/admin/_models.py`:

```python
# ─── Export/Import schema ──────────────────────────────────────────────────

class ExportedProvider(BaseModel):
    name: str
    protocol: str
    base_url: str
    capabilities: list[str] = []
    voices: list[VoiceEntry] = []
    enabled: bool = True


class ExportedFeatureRoute(BaseModel):
    feature: str
    provider_name: str | None = None
    model_name: str | None = None
    user_choices: list[str] = []
    provider_models: dict[str, str] = {}


class ExportedConfig(BaseModel):
    schema_version: int
    exported_at: str
    exported_from: str | None = None
    providers: list[ExportedProvider] = []
    feature_routes: list[ExportedFeatureRoute] = []


class ImportConfigRequest(BaseModel):
    config: ExportedConfig
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/routes/admin/_models.py
git commit -m "feat(admin): add pydantic models for AI config export/import"
```

---

## Task 2: Export-Endpoint mit Test

**Files:**
- Create: `backend/tests/test_provider_import_export.py`
- Modify: `backend/src/routes/admin/providers.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_provider_import_export.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_export'`

- [ ] **Step 3: Implement build_export and the endpoint**

Append to `backend/src/routes/admin/providers.py` (just below the existing helpers section, before the `_mask_provider` definition):

```python
# ─── Export / Import ───────────────────────────────────────────────────────


SCHEMA_VERSION = 1


def build_export(*, exported_from: str | None) -> dict:
    """Build the export payload from current DB state.

    Strips api_key and id from providers. Translates feature_routes'
    provider_id (+ user_choices / provider_models keys) into provider names
    for portability.
    """
    from datetime import datetime, timezone

    providers = db.list_providers()
    routes = db.list_routes()

    id_to_name = {p["id"]: p["name"] for p in providers}

    exported_providers: list[dict] = []
    for p in providers:
        exported_providers.append({
            "name": p["name"],
            "protocol": p["protocol"],
            "base_url": p["base_url"],
            "capabilities": list(p.get("capabilities") or []),
            "voices": list(p.get("voices") or []),
            "enabled": bool(p.get("enabled", True)),
        })

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
        "providers": exported_providers,
        "feature_routes": exported_routes,
    }


@router.get("/providers/export")
async def export_config(
    _admin=Depends(get_admin_user),
):
    """Download the full AI config as JSON. Never includes api_keys."""
    from datetime import date
    from fastapi.responses import JSONResponse

    payload = build_export(exported_from=None)
    filename = f"kis-ai-config-{date.today().isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/routes/admin/providers.py backend/tests/test_provider_import_export.py
git commit -m "feat(admin): add GET /admin/providers/export endpoint

Builds JSON snapshot of providers + feature_routes. Strips api_key
and id from providers; translates route provider_id (and user_choices,
provider_models keys) to portable provider names."
```

---

## Task 3: Import-Preview-Endpoint (Dry-Run) mit Test

**Files:**
- Modify: `backend/tests/test_provider_import_export.py` (append)
- Modify: `backend/src/routes/admin/providers.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_provider_import_export.py`:

```python
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
```

`_valid_config`, `_exported_provider`, `_exported_route` are now defined in the test file — make sure they appear before the tests that reference them. (The order in the snippet above is correct.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: 11 new tests FAIL with `ImportError: cannot import name 'build_import_preview'` / `'validate_import_config'`.

- [ ] **Step 3: Implement validation + preview**

Append to `backend/src/routes/admin/providers.py` (after `build_export`):

```python
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
        provider_diffs.append({
            "name": p["name"],
            "action": action,
            "needs_api_key": _needs_api_key(p["protocol"], p["base_url"]),
            "existing_has_key": existing_has_key,
            "protocol_change": protocol_change,
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
    return any(r["feature"] == feature for r in db.list_routes())


@router.post("/providers/import/preview")
async def import_preview(
    body: ImportConfigRequest,
    _admin=Depends(get_admin_user),
):
    return build_import_preview(body.config.model_dump())
```

Also add the import at the top of the file (extend the existing import line):

```python
from src.routes.admin._models import (
    CreateProviderRequest,
    DiscoverVoicesRequest,
    ImportConfigRequest,
    SetFeatureRouteRequest,
    UpdateProviderRequest,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/routes/admin/providers.py backend/tests/test_provider_import_export.py
git commit -m "feat(admin): add POST /admin/providers/import/preview (dry-run)

Computes diff between DB state and import payload without mutations.
Validates schema_version, protocols, capabilities, features and
duplicate names. Routes whose provider is neither in the import nor
in the target DB are marked skip_unresolved."
```

---

## Task 4: Import-Commit-Endpoint mit Test

**Files:**
- Modify: `backend/tests/test_provider_import_export.py` (append)
- Modify: `backend/src/routes/admin/providers.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_provider_import_export.py`:

```python
# ─── Import commit ─────────────────────────────────────────────────────────


def test_import_creates_new_provider_without_api_key(monkeypatch):
    from src.routes.admin.providers import perform_import

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    create_mock = MagicMock(return_value=_make_provider(10, "KISSKI"))
    monkeypatch.setattr("src.routes.admin.providers.db.create_provider",
                        create_mock)
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    cfg = _valid_config(providers=[_exported_provider("KISSKI")])
    result = perform_import(cfg)

    create_mock.assert_called_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["api_key"] is None  # never carries a key in
    assert kwargs["name"] == "KISSKI"
    assert result["providers_created"] == 1
    assert result["providers_updated"] == 0


def test_import_update_preserves_existing_api_key(monkeypatch):
    from src.routes.admin.providers import perform_import

    existing = _make_provider(1, "KISSKI", api_key="sk-existing")
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [existing])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    update_mock = MagicMock(return_value=existing)
    monkeypatch.setattr("src.routes.admin.providers.db.update_provider",
                        update_mock)
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    cfg = _valid_config(providers=[_exported_provider("KISSKI")])
    perform_import(cfg)

    update_mock.assert_called_once()
    kwargs = update_mock.call_args.kwargs
    assert "api_key" not in kwargs  # never touches the key on update


def test_import_creates_route_resolving_provider_names(monkeypatch):
    from src.routes.admin.providers import perform_import

    # Existing on DB: nothing. Import: 1 provider + 1 route referring to it.
    created = _make_provider(42, "KISSKI")
    list_calls = {"n": 0}

    def fake_list_providers():
        list_calls["n"] += 1
        # Before merge: empty. After create_provider call: contains KISSKI.
        return [] if list_calls["n"] == 1 else [created]

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        fake_list_providers)
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.create_provider",
                        lambda **kw: created)
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    set_route_mock = MagicMock()
    monkeypatch.setattr("src.routes.admin.providers.db.set_route",
                        set_route_mock)

    cfg = _valid_config(
        providers=[_exported_provider("KISSKI")],
        routes=[_exported_route("chat", provider_name="KISSKI",
                                model_name="mistral")],
    )
    result = perform_import(cfg)

    set_route_mock.assert_called_once()
    kwargs = set_route_mock.call_args.kwargs
    assert kwargs["provider_id"] == 42
    assert kwargs["model_name"] == "mistral"
    assert result["routes_created"] + result["routes_updated"] == 1


def test_import_skips_route_with_unresolved_provider(monkeypatch):
    from src.routes.admin.providers import perform_import

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    set_route_mock = MagicMock()
    monkeypatch.setattr("src.routes.admin.providers.db.set_route",
                        set_route_mock)

    cfg = _valid_config(
        routes=[_exported_route("chat", provider_name="Missing")],
    )
    result = perform_import(cfg)

    set_route_mock.assert_not_called()
    assert result["routes_skipped"] == 1


def test_import_filters_unresolved_user_choices(monkeypatch):
    """A user_choices list with a mix of resolvable and unresolvable names
    should keep only the resolvable ones and still set the route."""
    from src.routes.admin.providers import perform_import

    p = _make_provider(7, "KISSKI")
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [p])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    set_route_mock = MagicMock()
    monkeypatch.setattr("src.routes.admin.providers.db.set_route",
                        set_route_mock)

    cfg = _valid_config(routes=[
        _exported_route(
            "tts",
            provider_name="KISSKI",
            user_choices=["KISSKI", "Ghost"],
            provider_models={"KISSKI": "m1", "Ghost": "m2"},
        ),
    ])
    perform_import(cfg)

    kwargs = set_route_mock.call_args.kwargs
    assert kwargs["user_choices"] == [7]
    assert kwargs["provider_models"] == {"7": "m1"}


def test_import_triggers_reprobe_for_each_provider(monkeypatch):
    from src.routes.admin.providers import perform_import

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    monkeypatch.setattr(
        "src.routes.admin.providers.db.create_provider",
        lambda **kw: _make_provider(99, kw["name"]),
    )
    probe_mock = MagicMock()
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        probe_mock)

    cfg = _valid_config(providers=[
        _exported_provider("A"), _exported_provider("B"),
    ])
    perform_import(cfg)

    assert probe_mock.call_count == 2


def test_import_invalidates_fingerprint_cache_when_embedding_route_set(monkeypatch):
    from src.routes.admin.providers import perform_import

    p = _make_provider(5, "EmbedProvider")
    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [p])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.set_route",
                        lambda *a, **kw: None)
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    invalidate_mock = MagicMock()
    monkeypatch.setattr(
        "src.routes.admin._embedding.invalidate_fingerprint_cache",
        invalidate_mock,
    )

    cfg = _valid_config(routes=[_exported_route(
        "embedding", provider_name="EmbedProvider", model_name="emb")])
    perform_import(cfg)

    invalidate_mock.assert_called_once()


def test_import_response_lists_providers_needing_key(monkeypatch):
    from src.routes.admin.providers import perform_import

    monkeypatch.setattr("src.routes.admin.providers.db.list_providers",
                        lambda: [])
    monkeypatch.setattr("src.routes.admin.providers.db.list_routes",
                        lambda: [])
    monkeypatch.setattr(
        "src.routes.admin.providers.db.create_provider",
        lambda **kw: _make_provider(1, kw["name"], protocol=kw["protocol"],
                                    base_url=kw["base_url"]),
    )
    monkeypatch.setattr("src.routes.admin.providers.probe_provider",
                        lambda pid, **kw: None)

    cfg = _valid_config(providers=[
        _exported_provider("KISSKI",
                           base_url="https://chat-ai.example.de"),
        _exported_provider("Kokoro",
                           base_url="http://localhost:8880/v1"),
    ])
    result = perform_import(cfg)

    assert "KISSKI" in result["providers_needing_key"]
    assert "Kokoro" not in result["providers_needing_key"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: 8 new tests FAIL with `ImportError: cannot import name 'perform_import'`.

- [ ] **Step 3: Implement perform_import + the commit endpoint**

Append to `backend/src/routes/admin/providers.py`:

```python
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
        if existing is None:
            row = db.create_provider(
                name=p["name"], protocol=p["protocol"],
                base_url=p["base_url"], api_key=None,
                capabilities=capabilities, voices=voices,
                enabled=bool(p.get("enabled", True)),
            )
            providers_created += 1
        else:
            row = db.update_provider(
                existing["id"],
                protocol=p["protocol"], base_url=p["base_url"],
                capabilities=capabilities, voices=voices,
                enabled=bool(p.get("enabled", True)),
            )
            providers_updated += 1
        # Re-probe so probe_status reflects current reachability.
        probe_provider(row["id"])
        # row already carries api_key via the RETURNING clause; for create
        # we passed None, for update we never touch the field.
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
async def import_config(
    body: ImportConfigRequest,
    _admin=Depends(get_admin_user),
):
    return perform_import(body.config.model_dump())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: All 23 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/routes/admin/providers.py backend/tests/test_provider_import_export.py
git commit -m "feat(admin): add POST /admin/providers/import (merge commit)

Merge-only semantics: providers matched by name; existing api_keys
preserved; new providers created without keys. Routes resolve
provider names back to IDs against the post-merge DB; unresolvable
routes are skipped. Embedding-route changes invalidate the fingerprint
cache. Response carries providers_needing_key for the UI."
```

---

## Task 5: Clear-All-Endpoint mit Test

**Files:**
- Modify: `backend/tests/test_provider_import_export.py` (append)
- Modify: `backend/src/routes/admin/providers.py` (append)
- Modify: `backend/src/features/ai_providers/repository/providers.py` (add helper)
- Modify: `backend/src/features/ai_providers/repository/feature_routes.py` (add helper)

- [ ] **Step 1: Add `delete_all_providers` and `delete_all_routes` repo helpers**

Append to `backend/src/features/ai_providers/repository/providers.py`:

```python
def delete_all_providers() -> int:
    """Delete every row from the providers table. Returns count deleted."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM providers")
            deleted = cur.rowcount
            conn.commit()
            return deleted
```

Append to `backend/src/features/ai_providers/repository/feature_routes.py`:

```python
def delete_all_routes() -> int:
    """Delete every row from the feature_routes table. Returns count deleted."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM feature_routes")
            deleted = cur.rowcount
            conn.commit()
            return deleted
```

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_provider_import_export.py`:

```python
# ─── Clear all ─────────────────────────────────────────────────────────────


def test_clear_all_deletes_providers_and_routes(monkeypatch):
    from src.routes.admin.providers import perform_clear_all

    del_providers = MagicMock(return_value=3)
    del_routes = MagicMock(return_value=5)
    monkeypatch.setattr("src.routes.admin.providers.db.delete_all_providers",
                        del_providers)
    monkeypatch.setattr("src.routes.admin.providers.db.delete_all_routes",
                        del_routes)
    monkeypatch.setattr(
        "src.routes.admin._embedding.invalidate_fingerprint_cache",
        MagicMock(),
    )

    result = perform_clear_all()
    del_providers.assert_called_once()
    del_routes.assert_called_once()
    assert result == {"providers_deleted": 3, "routes_deleted": 5}


def test_clear_all_invalidates_fingerprint_cache(monkeypatch):
    from src.routes.admin.providers import perform_clear_all

    monkeypatch.setattr("src.routes.admin.providers.db.delete_all_providers",
                        lambda: 0)
    monkeypatch.setattr("src.routes.admin.providers.db.delete_all_routes",
                        lambda: 0)
    invalidate_mock = MagicMock()
    monkeypatch.setattr(
        "src.routes.admin._embedding.invalidate_fingerprint_cache",
        invalidate_mock,
    )

    perform_clear_all()
    invalidate_mock.assert_called_once()


def test_clear_all_routes_deleted_before_providers(monkeypatch):
    """Routes reference providers via FK; if FK is RESTRICT, routes must
    go first. If it's CASCADE/SET NULL it doesn't matter, but the safe
    order shouldn't change either way."""
    from src.routes.admin.providers import perform_clear_all

    call_order: list[str] = []
    monkeypatch.setattr(
        "src.routes.admin.providers.db.delete_all_routes",
        lambda: call_order.append("routes") or 0,
    )
    monkeypatch.setattr(
        "src.routes.admin.providers.db.delete_all_providers",
        lambda: call_order.append("providers") or 0,
    )
    monkeypatch.setattr(
        "src.routes.admin._embedding.invalidate_fingerprint_cache",
        MagicMock(),
    )

    perform_clear_all()
    assert call_order == ["routes", "providers"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: 3 new tests FAIL with `ImportError: cannot import name 'perform_clear_all'`.

- [ ] **Step 4: Implement perform_clear_all + endpoint**

Append to `backend/src/routes/admin/providers.py`:

```python
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


@router.delete("/providers/all")
async def clear_all(_admin=Depends(get_admin_user)):
    return perform_clear_all()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: All 26 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/routes/admin/providers.py backend/tests/test_provider_import_export.py backend/src/features/ai_providers/repository/providers.py backend/src/features/ai_providers/repository/feature_routes.py
git commit -m "feat(admin): add DELETE /admin/providers/all (clear-all)

Routes are deleted first to avoid FK conflicts, then providers,
then the embedding fingerprint cache is invalidated. Endpoint is
protected only by get_admin_user; the UI provides two-stage
confirmation (kebab menu + modal)."
```

---

## Task 6: Frontend — TypeScript-Types + API-Layer

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/_types.ts`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/_api.ts`

- [ ] **Step 1: Add Preview / Result types**

Read the existing `_types.ts` first to know its style, then append:

```ts
// ─── Export / Import ──────────────────────────────────────────────────────

export type ImportPreviewProvider = {
  name: string;
  action: "create" | "update";
  needs_api_key: boolean;
  existing_has_key: boolean;
  protocol_change: { from: string; to: string } | null;
};

export type ImportPreviewRoute =
  | { feature: string; action: "create" | "update"; resolved_provider: string }
  | { feature: string; action: "skip_unresolved"; reason: string };

export type ImportPreviewResult = {
  providers: ImportPreviewProvider[];
  routes: ImportPreviewRoute[];
};

export type ImportResult = {
  providers_created: number;
  providers_updated: number;
  routes_created: number;
  routes_updated: number;
  routes_skipped: number;
  providers_needing_key: string[];
};

export type ClearAllResult = {
  providers_deleted: number;
  routes_deleted: number;
};
```

- [ ] **Step 2: Add API functions**

Append to `frontend/src/app/[locale]/admin/_components/providers/_api.ts`:

```ts
// ─── Export / Import / Clear ──────────────────────────────────────────────

export async function exportConfig(): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}/providers/export`, { credentials: "include" });
  if (!res.ok) {
    throw new Error((await res.text()) || `HTTP ${res.status}`);
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match ? match[1] : `kis-ai-config-${new Date().toISOString().slice(0, 10)}.json`;
  const blob = await res.blob();
  return { blob, filename };
}

export async function importPreview(
  config: unknown,
): Promise<import("./_types").ImportPreviewResult> {
  const res = await fetch(`${BASE}/providers/import/preview`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return jsonOrThrow<import("./_types").ImportPreviewResult>(res);
}

export async function importConfig(
  config: unknown,
): Promise<import("./_types").ImportResult> {
  const res = await fetch(`${BASE}/providers/import`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return jsonOrThrow<import("./_types").ImportResult>(res);
}

export async function clearAllProviders(): Promise<import("./_types").ClearAllResult> {
  const res = await fetch(`${BASE}/providers/all`, {
    method: "DELETE",
    credentials: "include",
  });
  return jsonOrThrow<import("./_types").ClearAllResult>(res);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/_types.ts frontend/src/app/\[locale\]/admin/_components/providers/_api.ts
git commit -m "feat(frontend): add export/import/clear API + types for providers"
```

---

## Task 7: i18n-Strings (DE + EN)

**Files:**
- Modify: `frontend/messages/de.json`
- Modify: `frontend/messages/en.json`

- [ ] **Step 1: Find the existing admin.providers block**

Run: `grep -n '"providers"' frontend/messages/de.json | head -5`
Locate the `admin.providers.*` object so the new keys are nested inside it.

- [ ] **Step 2: Add the new strings under admin.providers in de.json**

Add (inside the `admin.providers` object — pick a spot at the end, before the closing brace of that block):

```json
"exportImport": {
  "exportButton": "Exportieren",
  "importButton": "Importieren",
  "exportToast": "Konfiguration heruntergeladen. Wichtig: Die Datei enthält KEINE API-Keys — diese müssen auf dem Zielsystem manuell neu gesetzt werden.",
  "preview": {
    "title": "Konfiguration importieren",
    "source": "Quelle: {filename}",
    "createdAt": "Erstellt am {date}{from, select, none {} other {, von {from}}}",
    "providersHeading": "Provider ({count})",
    "routesHeading": "Feature-Routes ({count})",
    "badge": {
      "new": "NEU",
      "merge": "MERGE",
      "skip": "ÜBERSPRUNGEN"
    },
    "apiKeyMissing": "API-Key fehlt — nach Import setzen!",
    "apiKeyNotNeeded": "Kein API-Key nötig",
    "apiKeyPreserved": "Bestehender API-Key bleibt erhalten",
    "protocolChange": "Protocol ändert sich: {from} → {to}",
    "routeSkipped": "übersprungen (Provider „{provider}\" nicht im Import)",
    "confirm": "Import bestätigen",
    "cancel": "Abbrechen"
  },
  "importSuccessToast": "Import erfolgreich. {count, plural, =0 {Alle Provider haben einen Key} one {# Provider benötigt noch einen API-Key} other {# Provider benötigen noch einen API-Key}}.",
  "errors": {
    "invalidJson": "Die Datei ist kein gültiges JSON.",
    "importFailed": "Import fehlgeschlagen: {message}"
  }
},
"clearAll": {
  "menuItem": "Alles löschen…",
  "title": "Alle Provider und Routes löschen?",
  "bodyCounts": "Diese Aktion löscht UNWIDERRUFLICH:\n  • {providers, plural, one {# Provider} other {# Provider}} (inkl. aller API-Keys)\n  • {routes, plural, one {# Feature-Route-Zuordnung} other {# Feature-Route-Zuordnungen}}",
  "warningFeaturesUnavailable": "KI-Funktionen (Chat, TTS, ASR, Übersetzung, Embedding) stehen danach NICHT mehr zur Verfügung, bis Provider neu angelegt oder importiert wurden.",
  "warningIrreversible": "Diese Aktion kann NICHT rückgängig gemacht werden. Vorher ggf. Export erstellen.",
  "confirm": "Ja, alles löschen",
  "cancel": "Abbrechen",
  "successToast": "Alle Provider und Routes gelöscht."
},
```

Inside `admin.providers.row.*` add:

```json
"missingKeyTooltip": "API-Key fehlt — Provider ist nicht funktionsfähig"
```

- [ ] **Step 3: Add the English mirror in en.json**

Add the same structure with translated strings:

```json
"exportImport": {
  "exportButton": "Export",
  "importButton": "Import",
  "exportToast": "Configuration downloaded. Important: the file contains NO API keys — these must be set manually on the target system.",
  "preview": {
    "title": "Import configuration",
    "source": "Source: {filename}",
    "createdAt": "Created {date}{from, select, none {} other {, from {from}}}",
    "providersHeading": "Providers ({count})",
    "routesHeading": "Feature routes ({count})",
    "badge": { "new": "NEW", "merge": "MERGE", "skip": "SKIPPED" },
    "apiKeyMissing": "API key missing — set after import!",
    "apiKeyNotNeeded": "No API key needed",
    "apiKeyPreserved": "Existing API key will be preserved",
    "protocolChange": "Protocol will change: {from} → {to}",
    "routeSkipped": "skipped (provider \"{provider}\" not in import)",
    "confirm": "Confirm import",
    "cancel": "Cancel"
  },
  "importSuccessToast": "Import successful. {count, plural, =0 {All providers have a key} one {# provider still needs an API key} other {# providers still need an API key}}.",
  "errors": {
    "invalidJson": "The file is not valid JSON.",
    "importFailed": "Import failed: {message}"
  }
},
"clearAll": {
  "menuItem": "Delete everything…",
  "title": "Delete all providers and routes?",
  "bodyCounts": "This action IRREVERSIBLY deletes:\n  • {providers, plural, one {# provider} other {# providers}} (incl. all API keys)\n  • {routes, plural, one {# feature route assignment} other {# feature route assignments}}",
  "warningFeaturesUnavailable": "AI features (chat, TTS, ASR, translation, embedding) will NOT be available afterwards until providers are created or imported.",
  "warningIrreversible": "This action CANNOT be undone. Consider creating an export first.",
  "confirm": "Yes, delete everything",
  "cancel": "Cancel",
  "successToast": "All providers and routes deleted."
},
```

Inside `admin.providers.row.*` add:

```json
"missingKeyTooltip": "API key missing — provider is not functional"
```

- [ ] **Step 4: Verify JSON syntax**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('messages/de.json'));JSON.parse(require('fs').readFileSync('messages/en.json'));console.log('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add frontend/messages/de.json frontend/messages/en.json
git commit -m "i18n(admin): add export/import/clearAll strings for providers"
```

---

## Task 8: Frontend — Export-Button + Handler

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx`

- [ ] **Step 1: Wire export handler in index.tsx**

In `index.tsx`, add this import at the top with the other API imports:

```ts
import {
  // ... existing imports
  exportConfig,
} from "./_api";
```

Inside the `ProvidersTab` component, add a handler before `if (loading...`:

```ts
const handleExport = useCallback(async () => {
  try {
    const { blob, filename } = await exportConfig();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    window.alert(t("exportImport.exportToast"));
  } catch (err) {
    window.alert((err as Error).message);
  }
}, [t]);
```

Pass it through to `ProviderListCard`:

```tsx
<ProviderListCard
  providers={providers}
  onAdd={() => setDialog({ open: true, mode: "create" })}
  onEdit={(p) => setDialog({ open: true, mode: "edit", provider: p })}
  onProbe={handleProbe}
  onDelete={handleDelete}
  onExport={handleExport}
/>
```

- [ ] **Step 2: Add Export button to ProviderListCard.tsx**

Read the file first. In the `Props` type, add:

```ts
type Props = {
  // ... existing
  onExport: () => void | Promise<void>;
};
```

Update the destructure and add a wrapper button next to the existing "Add" button. Change the existing markup from:

```tsx
{providers.length > 0 && (
  <button
    type="button"
    onClick={onAdd}
    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
  >
    <Plus size={14} weight="bold" />
    {t("list.add")}
  </button>
)}
```

To (note: the Plus button stays, two more buttons + a placeholder for the kebab join it — kebab arrives in Task 11):

```tsx
{providers.length > 0 && (
  <div className="flex items-center gap-2">
    <button
      type="button"
      onClick={onExport}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
    >
      <DownloadSimple size={14} weight="bold" />
      {t("exportImport.exportButton")}
    </button>
    {/* Import button + kebab inserted in later tasks */}
    <button
      type="button"
      onClick={onAdd}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb transition-colors"
    >
      <Plus size={14} weight="bold" />
      {t("list.add")}
    </button>
  </div>
)}
```

Update the icon import at the top:

```ts
import { ArrowsClockwise, Cube, DownloadSimple, NotePencil, Plus, Trash } from "@phosphor-icons/react";
```

- [ ] **Step 3: Manual smoke test**

Boot the frontend. Open the admin "KI" tab, click "Exportieren":
- Browser downloads a `kis-ai-config-YYYY-MM-DD.json`.
- `window.alert` shows the "no API keys" message.
- Open the downloaded file: confirm no `api_key` and no `id` fields appear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/index.tsx frontend/src/app/\[locale\]/admin/_components/providers/ProviderListCard.tsx
git commit -m "feat(frontend): add export button to admin AI providers tab

Downloads kis-ai-config-YYYY-MM-DD.json via GET /admin/providers/export
and shows an alert reminding the admin the file contains no API keys."
```

---

## Task 9: Frontend — Import-Button + File-Picker

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx`

(Note: the `ImportPreviewDialog` itself is built in Task 10; this task just wires the entry point + dialog state.)

- [ ] **Step 1: Extend dialog state in index.tsx**

Change `DialogState` to include the preview state:

```ts
type DialogState =
  | { open: false }
  | { open: true; mode: "create" }
  | { open: true; mode: "edit"; provider: Provider }
  | {
      open: true;
      mode: "import-preview";
      filename: string;
      config: unknown;
      preview: import("./_types").ImportPreviewResult;
    };
```

Add the import-preview API import:

```ts
import {
  // ... existing
  importPreview,
} from "./_api";
```

Add a handler:

```ts
const handleImportFile = useCallback(async (file: File) => {
  try {
    const text = await file.text();
    let config: unknown;
    try {
      config = JSON.parse(text);
    } catch {
      window.alert(t("exportImport.errors.invalidJson"));
      return;
    }
    const preview = await importPreview(config);
    setDialog({
      open: true,
      mode: "import-preview",
      filename: file.name,
      config,
      preview,
    });
  } catch (err) {
    window.alert(t("exportImport.errors.importFailed", { message: (err as Error).message }));
  }
}, [t]);
```

Pass through:

```tsx
<ProviderListCard
  // ... existing
  onImport={handleImportFile}
/>
```

The existing `if (dialog.open && dialog.mode === "edit")` and `if (dialog.open)` blocks remain — the new `import-preview` mode is rendered conditionally further below (Task 10).

- [ ] **Step 2: Add Import button to ProviderListCard.tsx**

Update Props:

```ts
type Props = {
  // ... existing
  onImport: (file: File) => void | Promise<void>;
};
```

Inside the component body (above `return`), add a hidden file input ref:

```tsx
import { useRef, useState } from "react";
// ...
const fileInputRef = useRef<HTMLInputElement>(null);
```

Then add the input + button next to Export (the {/* placeholder */} comment from Task 8):

```tsx
<input
  ref={fileInputRef}
  type="file"
  accept="application/json"
  className="hidden"
  onChange={(e) => {
    const file = e.target.files?.[0];
    if (file) onImport(file);
    e.target.value = "";  // allow re-selecting the same file
  }}
/>
<button
  type="button"
  onClick={() => fileInputRef.current?.click()}
  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-foreground border border-border-soft bg-background rounded-md hover:bg-surface transition-colors"
>
  <UploadSimple size={14} weight="bold" />
  {t("exportImport.importButton")}
</button>
```

Update the icon import:

```ts
import { ArrowsClockwise, Cube, DownloadSimple, NotePencil, Plus, Trash, UploadSimple } from "@phosphor-icons/react";
```

- [ ] **Step 3: Verify**

Compile check: `cd frontend && pnpm run build` (or `npm run build`) — expected: no type errors.

Manual smoke: clicking "Importieren" opens a file picker. Selecting a valid export JSON triggers the preview API call — for now, since the dialog isn't built yet, the dialog state changes but nothing renders. (That's intentional; Task 10 wires the visible dialog.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/index.tsx frontend/src/app/\[locale\]/admin/_components/providers/ProviderListCard.tsx
git commit -m "feat(frontend): wire import file picker + preview API call"
```

---

## Task 10: Frontend — ImportPreviewDialog

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/providers/ImportPreviewDialog.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx`

- [ ] **Step 1: Create the dialog component**

Create `frontend/src/app/[locale]/admin/_components/providers/ImportPreviewDialog.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Warning, CheckCircle } from "@phosphor-icons/react";
import type { ImportPreviewResult } from "./_types";

type Props = {
  filename: string;
  exportedAt?: string;
  exportedFrom?: string;
  preview: ImportPreviewResult;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
};

export default function ImportPreviewDialog({
  filename, exportedAt, exportedFrom, preview, onCancel, onConfirm,
}: Props) {
  const t = useTranslations("admin.providers.exportImport.preview");
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-border-soft rounded-xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto">
        <div className="p-5 border-b border-border-soft">
          <h2 className="text-base font-semibold text-foreground">{t("title")}</h2>
          <p className="text-xs text-muted mt-1">{t("source", { filename })}</p>
          {exportedAt && (
            <p className="text-xs text-muted">
              {t("createdAt", {
                date: exportedAt.slice(0, 10),
                from: exportedFrom ?? "none",
              })}
            </p>
          )}
        </div>

        <div className="p-5 space-y-5">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
              {t("providersHeading", { count: preview.providers.length })}
            </h3>
            <ul className="space-y-3">
              {preview.providers.map((p) => (
                <li key={p.name}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground truncate">
                      {p.name}
                    </span>
                    <Badge action={p.action} />
                  </div>
                  {p.protocol_change && (
                    <p className="mt-1 text-[12px] text-amber-700 dark:text-amber-400 border-l-2 border-amber-500 pl-2">
                      {t("protocolChange", p.protocol_change)}
                    </p>
                  )}
                  {p.needs_api_key && !p.existing_has_key && (
                    <p className="mt-1 text-[12px] text-red-600 dark:text-red-400 border-l-2 border-red-600 pl-2 flex items-center gap-1">
                      <Warning size={12} weight="bold" />
                      {t("apiKeyMissing")}
                    </p>
                  )}
                  {p.needs_api_key && p.existing_has_key && (
                    <p className="mt-1 text-[12px] text-green-700 dark:text-green-400 border-l-2 border-green-600 pl-2 flex items-center gap-1">
                      <CheckCircle size={12} weight="bold" />
                      {t("apiKeyPreserved")}
                    </p>
                  )}
                  {!p.needs_api_key && (
                    <p className="mt-1 text-[12px] text-green-700 dark:text-green-400 border-l-2 border-green-600 pl-2 flex items-center gap-1">
                      <CheckCircle size={12} weight="bold" />
                      {t("apiKeyNotNeeded")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted mb-2">
              {t("routesHeading", { count: preview.routes.length })}
            </h3>
            <ul className="space-y-1.5">
              {preview.routes.map((r, i) => (
                <li key={`${r.feature}-${i}`} className="text-sm flex items-start gap-2">
                  {r.action === "skip_unresolved" ? (
                    <>
                      <Warning size={14} weight="bold" className="text-amber-600 mt-0.5" />
                      <span className="text-foreground">
                        <span className="font-medium">{r.feature}</span> —{" "}
                        <span className="text-amber-700 dark:text-amber-400">
                          {t("routeSkipped", { provider: extractProviderFromReason(r.reason) })}
                        </span>
                      </span>
                    </>
                  ) : (
                    <>
                      <CheckCircle size={14} weight="bold" className="text-green-600 mt-0.5" />
                      <span className="text-foreground">
                        <span className="font-medium">{r.feature}</span> →{" "}
                        {r.resolved_provider}
                      </span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="p-5 border-t border-border-soft flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="px-3 py-1.5 text-sm font-medium bg-kb text-white rounded-md border-2 border-kb hover:bg-background hover:text-kb disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

function Badge({ action }: { action: "create" | "update" }) {
  const t = useTranslations("admin.providers.exportImport.preview.badge");
  const classes = action === "create"
    ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300"
    : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${classes}`}>
      {t(action === "create" ? "new" : "merge")}
    </span>
  );
}

/** Extracts the quoted provider name out of the backend's
 *  "Provider 'X' nicht im Import enthalten" message so the UI message
 *  can use its own translated wrapper. Falls back to the whole reason. */
function extractProviderFromReason(reason: string): string {
  const m = /['"„]([^'"]+)['"]/.exec(reason);
  return m ? m[1] : reason;
}
```

- [ ] **Step 2: Wire the dialog in index.tsx**

Add the import:

```ts
import ImportPreviewDialog from "./ImportPreviewDialog";
import { importConfig } from "./_api";
```

Add a confirm handler:

```ts
const handleImportConfirm = useCallback(async () => {
  if (!dialog.open || dialog.mode !== "import-preview") return;
  const result = await importConfig(dialog.config);
  setDialog({ open: false });
  await refreshAll();
  window.alert(
    t("exportImport.importSuccessToast", {
      count: result.providers_needing_key.length,
    }),
  );
}, [dialog, refreshAll, t]);
```

Render the dialog (next to the existing `{dialog.open && <ProviderFormDialog … />}` block):

```tsx
{dialog.open && dialog.mode === "import-preview" && (
  <ImportPreviewDialog
    filename={dialog.filename}
    exportedAt={(dialog.config as { exported_at?: string }).exported_at}
    exportedFrom={(dialog.config as { exported_from?: string }).exported_from ?? undefined}
    preview={dialog.preview}
    onCancel={() => setDialog({ open: false })}
    onConfirm={handleImportConfirm}
  />
)}
```

The existing `ProviderFormDialog` render block should be wrapped in `mode === "create" || mode === "edit"`:

```tsx
{dialog.open && (dialog.mode === "create" || dialog.mode === "edit") && (
  <ProviderFormDialog ... />
)}
```

- [ ] **Step 3: Manual end-to-end test**

1. Start the frontend.
2. Export the current config (Task 8 button).
3. Click "Importieren", select the just-downloaded file.
4. Verify: Preview dialog opens, all existing providers are `[MERGE]`, all routes have green ✓.
5. Click "Import bestätigen" → dialog closes, alert shows.
6. On a hypothetical config exported from another system with a missing provider: import shows a `[NEU]` badge + red ⚠ row, route resolution shows `skip_unresolved`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ImportPreviewDialog.tsx frontend/src/app/\[locale\]/admin/_components/providers/index.tsx
git commit -m "feat(frontend): add ImportPreviewDialog with per-provider key warning

Shows preview of import with [NEW]/[MERGE] badges, per-provider red
warning line when an API key will be missing after import, green
confirmation for preserved keys and key-not-needed providers, and
amber notice for skipped routes."
```

---

## Task 11: Frontend — Drei-Punkte-Menü + ClearAllConfirmDialog

**Files:**
- Create: `frontend/src/app/[locale]/admin/_components/providers/ClearAllConfirmDialog.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/index.tsx`

- [ ] **Step 1: Create the confirm dialog**

Create `frontend/src/app/[locale]/admin/_components/providers/ClearAllConfirmDialog.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Warning } from "@phosphor-icons/react";

type Props = {
  providerCount: number;
  routeCount: number;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
};

export default function ClearAllConfirmDialog({
  providerCount, routeCount, onCancel, onConfirm,
}: Props) {
  const t = useTranslations("admin.providers.clearAll");
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    try {
      await onConfirm();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-background border border-red-300 dark:border-red-700 rounded-xl shadow-xl w-full max-w-md">
        <div className="p-5 bg-red-50 dark:bg-red-950/30 border-b border-red-200 dark:border-red-800 rounded-t-xl flex items-start gap-3">
          <Warning size={22} weight="fill" className="text-red-600 dark:text-red-400 shrink-0" />
          <h2 className="text-base font-semibold text-red-700 dark:text-red-300">{t("title")}</h2>
        </div>

        <div className="p-5 space-y-3 text-sm text-foreground">
          <p className="whitespace-pre-line">
            {t("bodyCounts", { providers: providerCount, routes: routeCount })}
          </p>
          <p className="text-amber-700 dark:text-amber-400 flex gap-2">
            <Warning size={14} weight="bold" className="shrink-0 mt-0.5" />
            <span>{t("warningFeaturesUnavailable")}</span>
          </p>
          <p className="text-muted text-xs">{t("warningIrreversible")}</p>
        </div>

        <div className="p-5 border-t border-border-soft flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="px-3 py-1.5 text-sm font-medium border border-border-soft rounded-md hover:bg-surface"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting}
            className="px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
          >
            {t("confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add kebab menu to ProviderListCard.tsx**

Update icon import:

```ts
import { ArrowsClockwise, Cube, DotsThreeVertical, DownloadSimple, NotePencil, Plus, Trash, UploadSimple } from "@phosphor-icons/react";
```

Extend Props:

```ts
type Props = {
  // ... existing
  onClearAll: () => void;
};
```

Add a state hook and click-away handling at the top of `ProviderListCard`:

```tsx
const [menuOpen, setMenuOpen] = useState(false);
```

After the `[+ Provider hinzufügen]` button, add:

```tsx
<div className="relative">
  <button
    type="button"
    onClick={() => setMenuOpen((v) => !v)}
    aria-label="More actions"
    className="w-8 h-8 inline-flex items-center justify-center text-muted border border-border-soft rounded-md bg-background hover:bg-surface"
  >
    <DotsThreeVertical size={16} weight="bold" />
  </button>
  {menuOpen && (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={() => setMenuOpen(false)}
      />
      <div className="absolute right-0 top-full mt-1 w-48 bg-background border border-border-soft rounded-md shadow-lg z-50 py-1">
        <button
          type="button"
          onClick={() => {
            setMenuOpen(false);
            onClearAll();
          }}
          className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30"
        >
          {t("clearAll.menuItem")}
        </button>
      </div>
    </>
  )}
</div>
```

- [ ] **Step 3: Wire clear-all in index.tsx**

Add imports:

```ts
import ClearAllConfirmDialog from "./ClearAllConfirmDialog";
import { clearAllProviders } from "./_api";
```

Add state for the clear-all dialog:

```ts
const [clearAllOpen, setClearAllOpen] = useState(false);
```

Add handlers:

```ts
const handleClearAllRequest = useCallback(() => {
  setClearAllOpen(true);
}, []);

const handleClearAllConfirm = useCallback(async () => {
  await clearAllProviders();
  setClearAllOpen(false);
  await refreshAll();
  window.alert(t("clearAll.successToast"));
}, [refreshAll, t]);
```

Pass through:

```tsx
<ProviderListCard
  // ... existing
  onClearAll={handleClearAllRequest}
/>
```

Render the modal:

```tsx
{clearAllOpen && (
  <ClearAllConfirmDialog
    providerCount={providers.length}
    routeCount={routes.length}
    onCancel={() => setClearAllOpen(false)}
    onConfirm={handleClearAllConfirm}
  />
)}
```

- [ ] **Step 4: Manual test**

1. Click `[⋮]` → menu opens with "Alles löschen…" in red.
2. Click "Alles löschen…" → modal appears with correct counts.
3. Focus is on "Abbrechen". Press Enter → modal closes, nothing deleted.
4. Reopen → click "Ja, alles löschen" → list empties, alert shows.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ClearAllConfirmDialog.tsx frontend/src/app/\[locale\]/admin/_components/providers/ProviderListCard.tsx frontend/src/app/\[locale\]/admin/_components/providers/index.tsx
git commit -m "feat(frontend): add kebab menu + ClearAllConfirmDialog

Two-stage protection for the destructive clear-all action: click the
three-dot kebab to reveal 'Alles löschen…', then a red-themed modal
confirms with concrete provider/route counts. Default focus on Cancel
so Enter cannot accidentally wipe."
```

---

## Task 12: Frontend — Warn-Indikator in Provider-Liste

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx`

- [ ] **Step 1: Add the needs-key heuristic and warning icon to ProviderRow**

Update icon import:

```ts
import { ArrowsClockwise, Cube, DotsThreeVertical, DownloadSimple, NotePencil, Plus, Trash, UploadSimple, Warning } from "@phosphor-icons/react";
```

Add a helper above `ProviderRow`:

```ts
function providerNeedsKey(p: Provider): boolean {
  if (p.api_key_set) return false;
  if (p.protocol === "deepl") return true;
  if (p.protocol === "openai_compat") {
    const url = p.base_url.toLowerCase();
    if (url.includes("localhost") || url.includes("127.0.0.1") || url.includes("0.0.0.0")) {
      return false;
    }
    return true;
  }
  return false;
}
```

In `ProviderRow`, alongside the name + `<StatusPill>`, add:

```tsx
<div className="flex items-center gap-2 text-sm font-medium text-foreground mb-0.5">
  <span className="truncate">{provider.name}</span>
  <StatusPill provider={provider} probing={probing} />
  {providerNeedsKey(provider) && (
    <span
      title={t("row.missingKeyTooltip")}
      className="inline-flex items-center text-amber-500"
    >
      <Warning size={14} weight="fill" />
    </span>
  )}
</div>
```

- [ ] **Step 2: Manual test**

1. Create a new provider with protocol `openai_compat` + base URL `https://kisski.example.de` + leave api_key blank → ⚠ icon appears next to its name.
2. Edit it, add a key → save → ⚠ disappears.
3. Add a provider with `http://localhost:8880/v1` + no key → no ⚠ icon (local heuristic).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/\[locale\]/admin/_components/providers/ProviderListCard.tsx
git commit -m "feat(frontend): show ⚠ indicator on providers missing required api_key

Heuristic mirrors the backend needs_api_key check: deepl always
needs one; openai_compat needs one unless base_url is localhost."
```

---

## Final Verification

- [ ] **Backend full test run**

Run: `cd backend && python -m pytest tests/test_provider_import_export.py -v`
Expected: All 26 tests PASS.

Also run the full backend test suite to ensure nothing regressed:
`cd backend && python -m pytest -q`

- [ ] **Frontend build**

Run: `cd frontend && pnpm run build` (or `npm run build`)
Expected: no TypeScript errors.

- [ ] **End-to-end manual checklist (from the spec)**

- [ ] Export-Button → JSON-Datei wird heruntergeladen, Alert erscheint.
- [ ] Heruntergeladene Datei enthält weder `api_key`-Felder noch `id`-Felder.
- [ ] Import einer eigenen Export-Datei → Preview zeigt alle Provider als `[MERGE]`, alle Routes als `✓`.
- [ ] Import auf leerem System → alle Provider als `[NEU]`, rote Warnzeilen sichtbar.
- [ ] Import mit Protocol-Change → orange Warnzeile in der Preview.
- [ ] Import mit Route auf nicht-existierenden Provider → ⚠ "übersprungen" in der Route-Liste.
- [ ] Nach Bestätigung: Provider-Liste zeigt ⚠-Indikatoren bei Providern ohne Key.
- [ ] Datei kaputt / kein JSON → Fehler-Alert, kein Crash.
- [ ] Falsches `schema_version` → Fehlermeldung.
- [ ] Drei-Punkte-Menü → "Alles löschen" → Bestätigungs-Modal erscheint mit korrekten Zählern.
- [ ] Bestätigungs-Modal "Abbrechen" → keine Änderung.
- [ ] Bestätigungs-Modal "Ja, alles löschen" → Provider-Liste ist leer, Alert erscheint.
- [ ] Default-Fokus im Modal liegt auf "Abbrechen" (Enter löscht nicht).
