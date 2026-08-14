"""Ein Werkzeug schickt zu viel Kontext: kuerzen und einmal wiederholen.

Der Chat kann das seit dem 14.08.2026 (chat.py, ``_open_stream``). Die Werkzeuge nicht,
und seit die Budgets eine feste Obergrenze haben statt eines Vorsichtswerts, trifft es
sie wirklich: 600.000 Zeichen sind rund 200.000 Token, ``openai-gpt-oss-120b`` verraet
seine Groesse nicht und hat nur 131.072. Ohne Wiederholung braeche dort jeder Quiz-,
Lernkarten- und Mindmap-Lauf ab, und zwar bei jedem Versuch aufs Neue.
"""
from unittest.mock import patch

import pytest

from src.services import llm_context_healing as heilung
from src.services import model_limits as ml


_ABSAGE = ("This model's maximum context length is 131072 tokens. However, your request "
           "has 205000 input tokens. Please reduce the length of the input messages.")


class _Anbieter:
    """Lehnt zu lange Nachrichten ab, genau wie vLLM es tut."""

    def __init__(self, grenze_zeichen: int, absage: str = _ABSAGE):
        self.grenze = grenze_zeichen
        self.absage = absage
        self.laengen: list[int] = []

    def create(self, *, model, messages, **kwargs):
        laenge = sum(len(m.get("content") or "") for m in messages)
        self.laengen.append(laenge)
        if laenge > self.grenze:
            raise RuntimeError(self.absage)
        return f"ok nach {laenge}"


class _Client:
    def __init__(self, anbieter):
        self.chat = type("_", (), {"completions": anbieter})()


def _nachrichten(zeichen: int) -> list[dict]:
    return [
        {"role": "system", "content": "S" * 500},
        {"role": "user", "content": "K" * zeichen},
    ]


@pytest.fixture(autouse=True)
def _kein_speicher(monkeypatch):
    """Kein Netz, keine Datenbank: das Gelernte wird nur eingesammelt."""
    from src import database as db

    gemerkt: list[tuple] = []
    monkeypatch.setattr(db, "shrink_model_window",
                        lambda pid, model, fenster: gemerkt.append((pid, model, fenster)))
    monkeypatch.setattr(heilung, "_provider_id_for_chat", lambda: 1)
    return gemerkt


def test_kuerzt_und_wiederholt_nach_einer_absage():
    anbieter = _Anbieter(grenze_zeichen=400_000)
    antwort = heilung.create_with_shrink(
        _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(600_000),
    )
    assert antwort.startswith("ok")
    assert len(anbieter.laengen) == 2
    assert anbieter.laengen[1] < anbieter.laengen[0]


def test_der_zweite_versuch_passt_ins_gelernte_fenster():
    """131.072 Token mal 0,75 mal 3,0 Zeichen. Wer nur "irgendwie kuerzer" sendet,
    faellt beim naechsten Mal wieder auf die Nase."""
    anbieter = _Anbieter(grenze_zeichen=400_000)
    heilung.create_with_shrink(
        _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(600_000),
    )
    assert anbieter.laengen[1] <= ml.context_chars(131072, ml.TOOL_SHARE)


def test_merkt_sich_die_groesse_fuer_alle_weiteren_laeufe(_kein_speicher):
    anbieter = _Anbieter(grenze_zeichen=400_000)
    heilung.create_with_shrink(
        _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(600_000),
    )
    assert _kein_speicher == [(1, "gpt-oss-120b", 131072)]


def test_ein_passender_aufruf_geht_ohne_umweg_durch():
    anbieter = _Anbieter(grenze_zeichen=400_000)
    heilung.create_with_shrink(
        _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(1000),
    )
    assert len(anbieter.laengen) == 1


def test_absage_ohne_zahl_bleibt_ein_fehler():
    """Nur eine Absage, die die Groesse nennt, kann etwas verbessern. Blind kuerzen und
    nochmal senden kostet nur Zeit und Ratenkontingent."""
    anbieter = _Anbieter(grenze_zeichen=400_000, absage="Bad Request")
    with pytest.raises(RuntimeError, match="Bad Request"):
        heilung.create_with_shrink(
            _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(600_000),
        )
    assert len(anbieter.laengen) == 1


def test_reicht_die_uebrigen_angaben_unveraendert_weiter():
    """Temperatur und Antwortlaenge gehoeren zum Aufruf, nicht zum Kontext."""
    gesehen = {}

    class _Merker(_Anbieter):
        def create(self, **kwargs):
            gesehen.update(kwargs)
            return super().create(**kwargs)

    anbieter = _Merker(grenze_zeichen=10_000_000)
    heilung.create_with_shrink(
        _Client(anbieter), model="m", messages=_nachrichten(10), temperature=0.6,
    )
    assert gesehen["temperature"] == 0.6


def test_ohne_bekannten_anbieter_wird_nicht_gelernt(monkeypatch):
    """Ohne Kennung gibt es keine Zeile, in die die Groesse gehoert. Dann lieber der
    ehrliche Fehler als ein zweiter Versuch, der nichts merkt."""
    monkeypatch.setattr(heilung, "_provider_id_for_chat", lambda: None)
    anbieter = _Anbieter(grenze_zeichen=400_000)
    with pytest.raises(RuntimeError):
        heilung.create_with_shrink(
            _Client(anbieter), model="gpt-oss-120b", messages=_nachrichten(600_000),
        )
    assert len(anbieter.laengen) == 1
