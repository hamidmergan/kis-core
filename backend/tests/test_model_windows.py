"""The context window an admin enters by hand, and which models the admin page lists."""

from src import database as db
from src.routes.admin import model_windows as mw
from src.services import model_limits as ml


class _Tabelle:
    """model_limits in memory, keyed by provider and model."""

    def __init__(self, monkeypatch):
        self.zeilen: dict[tuple[int, str], dict] = {}
        monkeypatch.setattr(db, "get_model_limit", lambda pid, m: self.zeilen.get((pid, m)))
        monkeypatch.setattr(db, "set_model_limit", self._setzen)
        monkeypatch.setattr(db, "set_manual_window", self._von_hand)
        monkeypatch.setattr(db, "delete_model_limit", lambda pid, m: self.zeilen.pop((pid, m), None))

    def _setzen(self, pid, m, *, window_tokens, source, thinks=False, think_off=""):
        self.zeilen[(pid, m)] = {"window_tokens": window_tokens, "source": source,
                                 "thinks": thinks, "think_off": think_off}

    def _von_hand(self, pid, m, window_tokens):
        alt = self.zeilen.get((pid, m)) or {"thinks": False, "think_off": ""}
        self.zeilen[(pid, m)] = {**alt, "window_tokens": window_tokens, "source": "gesetzt"}


_ANBIETER = {"id": 21, "name": "myLab", "base_url": "http://x", "api_key": ""}


def _messung(fenster, quelle, thinks=False):
    return lambda base_url, api_key, model: ml.ModelProfile(fenster, quelle, thinks, "")


def test_handeintrag_uebersteht_die_neumessung(monkeypatch):
    tabelle = _Tabelle(monkeypatch)
    ml.set_window_by_hand(_ANBIETER, "chat-fast", 262_144)
    monkeypatch.setattr(ml, "measure_provider_model", _messung(0, ml.QUELLE_UNBEKANNT, thinks=True))

    profil = ml.remeasure(_ANBIETER, "chat-fast")

    assert (profil.window_tokens, profil.source) == (262_144, ml.QUELLE_GESETZT)
    assert tabelle.zeilen[(21, "chat-fast")]["window_tokens"] == 262_144
    assert tabelle.zeilen[(21, "chat-fast")]["thinks"] is True


def test_handeintrag_zaehlt_als_bekanntes_fenster(monkeypatch):
    _Tabelle(monkeypatch)
    profil = ml.set_window_by_hand(_ANBIETER, "chat-fast", 262_144)
    assert profil.measured


def test_leeren_misst_neu(monkeypatch):
    tabelle = _Tabelle(monkeypatch)
    ml.set_window_by_hand(_ANBIETER, "qwen", 99_000)
    monkeypatch.setattr(ml, "measure_provider_model", _messung(131_072, ml.QUELLE_GEMESSEN))

    profil = ml.set_window_by_hand(_ANBIETER, "qwen", None)

    assert (profil.window_tokens, profil.source) == (131_072, ml.QUELLE_GEMESSEN)
    assert tabelle.zeilen[(21, "qwen")]["source"] == ml.QUELLE_GEMESSEN


def test_leeren_ohne_messbares_fenster_bleibt_unbekannt(monkeypatch):
    _Tabelle(monkeypatch)
    ml.set_window_by_hand(_ANBIETER, "chat-fast", 262_144)
    monkeypatch.setattr(ml, "measure_provider_model", _messung(0, ml.QUELLE_UNBEKANNT))

    profil = ml.set_window_by_hand(_ANBIETER, "chat-fast", None)

    assert not profil.measured


def test_listet_nur_die_chat_modelle_je_anbieter_einmal(monkeypatch):
    monkeypatch.setattr(db, "list_routes", lambda: [
        {"feature": "chat", "provider_id": 21, "model_name": "chat-fast",
         "provider_models": {"20": "qwen3", "21": "chat-fast", "25": ""}},
        {"feature": "doc_translate", "provider_id": 21, "model_name": "chat-fast",
         "provider_models": {"21": "chat-fast"}},
        {"feature": "vision", "provider_id": 21, "model_name": "gemma4-31b",
         "provider_models": {"21": "gemma4-31b"}},
        {"feature": "embedding", "provider_id": 21, "model_name": "qwen3-embedding-4b",
         "provider_models": {"21": "qwen3-embedding-4b"}},
    ])
    assert mw._routed_models() == [(20, "qwen3"), (21, "chat-fast")]


def test_je_anbieter_nur_das_modell_das_der_chat_dort_nutzt(monkeypatch):
    monkeypatch.setattr(db, "list_routes", lambda: [
        {"feature": "chat", "provider_id": 21, "model_name": "alt",
         "provider_models": {"21": "chat-fast"}},
    ])
    assert mw._routed_models() == [(21, "chat-fast")]


def test_unbekanntes_modell_zeigt_kein_fenster():
    zeile = mw._row(21, "chat-fast", ml.ModelProfile(0, ml.QUELLE_UNBEKANNT, False, ""))
    assert zeile["window_tokens"] is None and zeile["source"] == ml.QUELLE_UNBEKANNT
