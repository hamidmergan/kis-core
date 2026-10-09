"""The admin's order of providers per feature: the first usable one is the standard, the next ones step in."""

import os
import uuid
from unittest.mock import MagicMock

import pytest

from src.features.ai_providers.repository.feature_routes import ordered_ids
from src.routes.admin import providers as admin
from src.routes.admin._models import SetFeatureRouteRequest, UpdateProviderRequest


def _provider(pid, *, protocol="openai_compat", caps=("chat",), enabled=True, voices=()):
    return {"id": pid, "name": f"P{pid}", "protocol": protocol, "base_url": f"http://p{pid}",
            "api_key": None, "enabled": enabled, "capabilities": list(caps), "voices": list(voices),
            "concurrency": {}, "owner_user_id": None}


_PROVIDERS = {
    1: _provider(1, caps=("chat", "embedding")),
    2: _provider(2, caps=("chat", "embedding")),
    3: _provider(3, enabled=False),
    4: _provider(4, protocol="deepl", caps=("translation",)),
    5: _provider(5),
}


# ─── Die Reihenfolge selbst ──────────────────────────────────────────────────


def test_gespeicherte_reihenfolge_geht_vor_dem_anlegedatum():
    assert ordered_ids({"provider_order": [5, 2]}, [1, 2, 5]) == [5, 2, 1]


def test_alte_route_stellt_erste_wahl_und_rueckfall_nach_vorn():
    assert ordered_ids({"provider_id": 5, "fallback_provider_id": 2}, [1, 2, 5]) == [5, 2, 1]


def test_unbekannte_und_doppelte_ids_fallen_weg():
    assert ordered_ids({"provider_order": [9, 2, 2]}, [1, 2]) == [2, 1]
    assert ordered_ids(None, [1, 2]) == [1, 2]


# ─── Speichern im Adminbereich ───────────────────────────────────────────────


@pytest.fixture
def route_env(monkeypatch):
    monkeypatch.setattr(admin.db, "get_provider", lambda pid: _PROVIDERS.get(pid))
    stored = MagicMock(side_effect=lambda feature, **kw: {"feature": feature, **kw})
    monkeypatch.setattr(admin.db, "set_route", stored)
    monkeypatch.setattr(admin, "_measure_route_model", lambda *a, **kw: None)
    monkeypatch.setattr("src.routes.admin._embedding.invalidate_fingerprint_cache", MagicMock())
    return stored


def _speichern(feature, order, models):
    body = SetFeatureRouteRequest(provider_order=order, provider_models=models)
    return admin.set_feature_route(feature, body, _admin=None, locale="de")["route"]


def test_der_erste_mit_modell_ist_standard_der_naechste_rueckfall(route_env):
    route = _speichern("chat", [5, 1, 2], {"5": "m5", "1": "m1", "2": "m2"})
    assert (route["provider_id"], route["model_name"], route["fallback_provider_id"]) == (5, "m5", 1)
    assert route["provider_order"] == [5, 1, 2]


def test_ohne_modell_oder_abgeschaltet_rueckt_der_naechste_auf(route_env):
    route = _speichern("chat", [3, 5, 1, 2], {"3": "m3", "1": "m1", "2": "m2"})
    assert (route["provider_id"], route["fallback_provider_id"]) == (1, 2)
    assert route["provider_order"] == [3, 5, 1, 2]


def test_uebersetzen_darf_deepl_ohne_modell_vorn_haben(route_env):
    route = _speichern("doc_translate", [4, 1], {"1": "m1"})
    assert (route["provider_id"], route["model_name"], route["fallback_provider_id"]) == (4, None, 1)


def test_einbettungen_springen_nur_mit_demselben_modell_ein(route_env):
    route = _speichern("embedding", [1, 2], {"1": "e5", "2": "bge"})
    assert (route["provider_id"], route["fallback_provider_id"]) == (1, None)
    route = _speichern("embedding", [1, 2], {"1": "e5", "2": "e5"})
    assert route["fallback_provider_id"] == 2


def test_ohne_nutzbaren_anbieter_bleibt_die_route_leer(route_env):
    route = _speichern("chat", [3, 5], {})
    assert (route["provider_id"], route["fallback_provider_id"]) == (None, None)


def test_ein_abgeschalteter_anbieter_gibt_seinen_platz_ab(monkeypatch, route_env):
    route = {"feature": "chat", "provider_id": 1, "fallback_provider_id": 2, "provider_order": [1, 2, 5],
             "provider_models": {"1": "m1", "2": "m2", "5": "m5"}, "user_choices": [], "provider_sampling": {}}
    monkeypatch.setattr(admin.db, "list_routes", lambda: [route])
    aus = {**_PROVIDERS, 1: _provider(1, enabled=False)}
    monkeypatch.setattr(admin.db, "get_provider", lambda pid: aus.get(pid))
    monkeypatch.setattr(admin.db, "update_provider", lambda pid, **kw: {**aus[pid], **kw})
    admin.update_provider(1, UpdateProviderRequest(enabled=False), _admin=None, locale="de")
    gespeichert = route_env.call_args.kwargs
    assert (gespeichert["provider_id"], gespeichert["fallback_provider_id"]) == (2, 5)


# ─── Wer einspringt ──────────────────────────────────────────────────────────


@pytest.fixture
def anbieter(monkeypatch):
    from src import database as db
    stand = {"route": {"provider_id": 1, "fallback_provider_id": 5, "provider_order": [1, 5, 2],
                       "provider_models": {"1": "m1", "2": "m2", "5": "m5"}},
             "providers": {pid: _PROVIDERS[pid] for pid in (1, 2, 5)}}
    monkeypatch.setattr(db, "get_route", lambda feature: stand["route"])
    monkeypatch.setattr(db, "get_provider", lambda pid: stand["providers"].get(pid))
    monkeypatch.setattr(db, "list_providers_with_capability", lambda cap: [
        p for p in stand["providers"].values() if cap in p["capabilities"]])
    return stand


def test_weitere_anbieter_folgen_der_reihenfolge(anbieter):
    from src.services import provider_transport as pt
    anbieter["route"]["provider_order"] = [1, 5, 2]
    assert [z.provider_id for z in pt.further_targets("chat", skip={1})] == [5, 2]
    anbieter["route"]["provider_order"] = [1, 2, 5]
    assert [z.provider_id for z in pt.further_targets("chat", skip={1})] == [2, 5]


def test_personen_sehen_die_anbieter_in_der_reihenfolge(anbieter):
    from src.services import feature_provider_choices as wahl
    anbieter["route"]["provider_order"] = [5, 2, 1]
    zeilen, _ = wahl._candidates("chat")
    assert [p["id"] for p in zeilen] == [5, 2, 1]


# ─── Echte Datenbank ─────────────────────────────────────────────────────────


def test_reihenfolge_auf_der_echten_datenbank():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("kein DATABASE_URL gesetzt (Test braucht echtes Postgres)")
    from src.core.db.pool import get_connection
    from src.core.db.schema import init_db
    from src.features.ai_providers.repository import feature_routes as routes_repo
    from src.features.ai_providers.repository import providers as repo

    init_db()
    kennung = uuid.uuid4().hex[:8]
    feature = f"test_reihenfolge_{kennung}"
    a = repo.create_provider(name=f"test-reihe-a-{kennung}", protocol="openai_compat",
                             base_url="http://a", capabilities=["chat"])
    b = repo.create_provider(name=f"test-reihe-b-{kennung}", protocol="openai_compat",
                             base_url="http://b", capabilities=["chat"])
    try:
        routes_repo.set_route(feature, provider_id=b["id"], provider_order=[b["id"], a["id"]])
        assert routes_repo.get_route(feature)["provider_order"] == [b["id"], a["id"]]
        assert any(r["feature"] == feature for r in routes_repo.routes_using_provider(a["id"]))
        routes_repo.clear_provider_from_routes(a["id"])
        assert routes_repo.get_route(feature)["provider_order"] == [b["id"]]
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM feature_routes WHERE feature = %s", (feature,))
                cur.execute("DELETE FROM providers WHERE id IN (%s, %s)", (a["id"], b["id"]))
            conn.commit()
