"""Zahlen zum Screencast-Lauf: phasenweise anhaengen, nichts verlieren."""

import pytest

from src.services.screencast.statistik import messe, notiere
from src.storage import load_result_meta, save_result_meta


UID = 7
JOB = "a" * 32


def test_notiere_legt_stats_an(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 12})

    assert load_result_meta(UID, JOB) == {"stats": {"vertonung": {"folien": 12}}}


def test_notiere_behaelt_bestehende_meta(lokal):
    save_result_meta(UID, JOB, {"target_lang": "EN-US"})

    notiere(UID, JOB, "vertonung", {"folien": 12})

    meta = load_result_meta(UID, JOB)
    assert meta["target_lang"] == "EN-US"
    assert meta["stats"]["vertonung"] == {"folien": 12}


def test_notiere_behaelt_fruehere_phasen(lokal):
    notiere(UID, JOB, "uebersetzung", {"anbieter": "myLab"})

    notiere(UID, JOB, "vertonung", {"folien": 12})

    stats = load_result_meta(UID, JOB)["stats"]
    assert stats["uebersetzung"] == {"anbieter": "myLab"}
    assert stats["vertonung"] == {"folien": 12}


def test_notiere_ersetzt_dieselbe_phase(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 12, "zeichen": 900})

    notiere(UID, JOB, "vertonung", {"folien": 3})

    assert load_result_meta(UID, JOB)["stats"]["vertonung"] == {"folien": 3}


def test_messe_schreibt_dauer_und_werte(lokal):
    with messe(UID, JOB, "vertonung") as werte:
        werte["folien"] = 12

    eintrag = load_result_meta(UID, JOB)["stats"]["vertonung"]
    assert eintrag["folien"] == 12
    assert eintrag["dauer_s"] >= 0


def test_messe_schreibt_auch_bei_fehler(lokal):
    with pytest.raises(RuntimeError):
        with messe(UID, JOB, "vertonung") as werte:
            werte["folien"] = 12
            raise RuntimeError("kaputt")

    eintrag = load_result_meta(UID, JOB)["stats"]["vertonung"]
    assert eintrag["folien"] == 12
    assert eintrag["fehler"] == "kaputt"


def test_notiere_schluckt_speicherfehler(lokal, monkeypatch):
    from src.services.screencast import statistik

    def _kaputt(*_args, **_kwargs):
        raise OSError("Speicher weg")

    monkeypatch.setattr(statistik, "save_result_meta", _kaputt)

    notiere(UID, JOB, "vertonung", {"folien": 12})


def _stelle_anbieter(monkeypatch, provider: dict | None, route: dict | None) -> None:
    from src import database as db
    monkeypatch.setattr(db, "get_provider", lambda _pid: provider)
    monkeypatch.setattr(db, "get_route", lambda _feature: route)


def test_anbieter_und_modell_nimmt_das_anbieterspezifische_modell(monkeypatch):
    from src.services.screencast.statistik import anbieter_und_modell

    _stelle_anbieter(
        monkeypatch,
        {"name": "myLab"},
        {"model_name": "allgemein", "provider_models": {"3": "qwen3-32b"}},
    )

    assert anbieter_und_modell(3, "doc_translate") == {
        "anbieter": "myLab", "modell": "qwen3-32b", "route": "doc_translate",
    }


def test_anbieter_und_modell_faellt_auf_das_routenmodell_zurueck(monkeypatch):
    from src.services.screencast.statistik import anbieter_und_modell

    _stelle_anbieter(monkeypatch, {"name": "myLab"}, {"model_name": "allgemein", "provider_models": {}})

    assert anbieter_und_modell(3, "doc_translate") == {
        "anbieter": "myLab", "modell": "allgemein", "route": "doc_translate",
    }


def test_anbieter_und_modell_bleibt_leer_wenn_es_den_anbieter_nicht_gibt(monkeypatch):
    from src.services.screencast.statistik import anbieter_und_modell

    _stelle_anbieter(monkeypatch, None, None)

    assert anbieter_und_modell(3, "doc_translate") == {
        "anbieter": "", "modell": "", "route": "doc_translate",
    }


def test_zeichen_zahlen_zaehlt_folien_zeichen_und_leere():
    from src.services.screencast.statistik import zeichen_zahlen

    assert zeichen_zahlen(["Hallo", "", "  ", "Guten Tag zusammen"]) == {
        "folien": 4,
        "zeichen": 23,
        "laengste_folie_zeichen": 18,
        "leere_folien": 2,
    }


def test_zeichen_zahlen_vertraegt_null_folien():
    from src.services.screencast.statistik import zeichen_zahlen

    assert zeichen_zahlen([]) == {
        "folien": 0,
        "zeichen": 0,
        "laengste_folie_zeichen": 0,
        "leere_folien": 0,
    }


class _FakeTts:
    def synthesize_with_timestamps(self, text, language, *, voice_id, speed):
        return {"audio_bytes": b"mp3", "alignment": None}


def _vertone(tmp_path, scripts: list[str], zaehler: dict) -> None:
    import asyncio

    from src.services.screencast.generation import generate_all_tts

    asyncio.run(generate_all_tts(
        scripts, _FakeTts(), tmp_path, 1.0, voice_id="alloy",
        job_uuid=JOB, user_id=UID, zaehler=zaehler,
    ))


def test_zaehler_meldet_null_wenn_nichts_im_zwischenspeicher_liegt(lokal, tmp_path):
    zaehler: dict = {}

    _vertone(tmp_path, ["Erste Folie.", "Zweite Folie."], zaehler)

    assert zaehler == {"aus_zwischenspeicher": 0}


def test_zaehler_meldet_die_folien_aus_dem_zwischenspeicher(lokal, tmp_path):
    from src.storage import save_job_file
    save_job_file(UID, JOB, "render_cache/slide_000.mp3", b"alt")
    zaehler: dict = {}

    _vertone(tmp_path, ["Erste Folie.", "Zweite Folie."], zaehler)

    assert zaehler == {"aus_zwischenspeicher": 1}


def test_route_kennung_nennt_anbieter_und_modell_der_route(monkeypatch):
    from src.services import feature_router
    from src.services.screencast.statistik import route_kennung

    binding = feature_router.FeatureBinding(
        feature="chat", provider={"name": "myLab", "protocol": "openai_compat"}, model="qwen3-32b",
    )
    monkeypatch.setattr(feature_router, "resolve", lambda _feature: binding)

    assert route_kennung("chat") == {"anbieter": "myLab", "modell": "qwen3-32b", "route": "chat"}


def test_route_kennung_bleibt_leer_wenn_keine_route_gesetzt_ist(monkeypatch):
    from src.services import feature_router
    from src.services.screencast.statistik import route_kennung

    def _keine(_feature):
        raise RuntimeError("keine Route")

    monkeypatch.setattr(feature_router, "resolve", _keine)

    assert route_kennung("chat") == {"anbieter": "", "modell": "", "route": "chat"}
