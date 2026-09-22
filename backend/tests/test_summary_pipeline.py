"""Prüft den Ablauf der Zusammenfassung: Sprache, Grundlage, Plan, Abschnitte, Zusammenbau."""

import asyncio
import json

import pytest

from src.features.summary import pipeline as pl
from src.features.summary.models import Caller, LANGUAGE_FALLBACK
from src.features.summary.templates import get_template
from src.services.source_reading import Piece, Source
from tests.summary_helpers import FakeClient


def _quelle(text: str = "Ein Satz. " * 50, name: str = "a.pdf") -> Source:
    return Source(dateiname=name, fassung="x", text=text, seiten=1,
                  stuecke=[Piece(seite=1, von=0, bis=len(text))])


def _gruppe(*titel: str) -> str:
    """Eine Antwort fuer eine ganze Gruppe, mit Ueberschriften zum Auftrennen."""
    return "\n\n".join(f"## {t}\nText {t}" for t in titel)


def _plan(*titel: str) -> str:
    return json.dumps({"title": "Der Titel", "intro": "Die Einleitung.", "sections": [
        {"section_index": i, "title": t, "description": "d", "refs": ["1"]}
        for i, t in enumerate(titel)]})


class _Store:
    def __init__(self):
        self.sprache = None
        self.plan = None
        self.abschnitte: dict[int, str] = {}
        self.grundlage = None
        self.fortschritt: list[tuple] = []

    def load_map(self):
        return self.grundlage

    def save_map(self, daten):
        self.grundlage = daten

    def progress(self, step, part=None, total=None):
        self.fortschritt.append((step, part, total))

    def load_language(self):
        return self.sprache

    def save_language(self, sprache):
        self.sprache = sprache

    def load_outline(self):
        return self.plan

    def save_outline(self, plan):
        self.plan = plan

    def load_sections(self):
        return dict(self.abschnitte)

    def save_section(self, index, text):
        self.abschnitte[index] = text


def _caller(antworten):
    return Caller(FakeClient(antworten), "m", window_tokens=262_144)


def _lauf(antworten, quellen=None, store=None, vorlage="kurzbriefing"):
    store = store or _Store()
    ergebnis = asyncio.run(pl.run(_caller(antworten), sources=quellen or [_quelle()],
                                  template=get_template(vorlage), store=store))
    return ergebnis, store


# ── Sprache ──────────────────────────────────────────────────────────────────

def test_die_sprache_wird_einmal_gefragt_und_gemerkt():
    _, store = _lauf(["German", _plan("A", "B", "C"), _gruppe("A", "B", "C")])
    assert store.sprache == "German"


def test_eine_gemerkte_sprache_wird_nicht_erneut_gefragt():
    store = _Store()
    store.sprache = "German"
    _lauf([_plan("A", "B", "C"),
           _gruppe("A", "B", "C")], store=store)
    assert store.sprache == "German"


def test_eine_unbrauchbare_sprachantwort_faellt_zurueck():
    _, store = _lauf(["Das ist eindeutig kein einzelnes Sprachwort sondern ein ganzer Satz",
                      _plan("A", "B", "C"),
                      _gruppe("A", "B", "C")])
    assert store.sprache == LANGUAGE_FALLBACK


def test_zu_wenig_text_fragt_gar_nicht_erst():
    _, store = _lauf([_plan("A", "B", "C"),
                      _gruppe("A", "B", "C")], quellen=[_quelle("Kurz.")])
    assert store.sprache == LANGUAGE_FALLBACK


# ── Grundlage und Plan ──────────────────────────────────────────────────────────

def test_ein_lauf_liefert_den_zusammengesetzten_text():
    ergebnis, _ = _lauf(["German", _plan("A", "B", "C"), _gruppe("A", "B", "C")])
    assert "Die Einleitung." in ergebnis
    assert "Text A" in ergebnis and "Text C" in ergebnis


def test_die_grundlage_wird_gesichert():
    _, store = _lauf(["German", _plan("A", "B", "C"), _gruppe("A", "B", "C")])
    assert store.grundlage == {"modus": "stellen", "themen": []}


def test_ohne_text_scheitert_der_lauf():
    leer = Source(dateiname="a.pdf", fassung="x", text="", seiten=0, stuecke=[])
    with pytest.raises(RuntimeError):
        _lauf(["German"], quellen=[leer])


def test_ein_zu_langer_text_wird_ueber_themen_geplant():
    """Passt der Text nicht in ein Fenster, liest jeder Teil nur seine Themen heraus."""
    stuecke = [Piece(seite=1 + i // 5, von=i * 1000, bis=(i + 1) * 1000) for i in range(300)]
    gross = Source(dateiname="g.pdf", fassung="x", text="Ein Wort " * 33_334, seiten=60,
                   stuecke=stuecke)
    themen = json.dumps({"topics": [{"title": "Thema", "gist": "g", "refs": ["1-3"]}]})
    caller = Caller(FakeClient(["German", themen, themen, themen,
                                _plan("A", "B", "C"), _gruppe("A", "B", "C")]),
                    "m", window_tokens=50_000)
    store = _Store()
    asyncio.run(pl.run(caller, sources=[gross], template=get_template("kurzbriefing"),
                       store=store))
    assert store.grundlage["modus"] == "themen"
    assert "numbered list of topics" in caller.client.system_prompts()[4]


def test_der_plan_wird_gesichert_und_nicht_neu_geholt():
    store = _Store()
    _lauf(["German", _plan("A", "B", "C"),
           _gruppe("A", "B", "C")], store=store)
    assert [a["title"] for a in store.plan["sections"]] == ["A", "B", "C"]


def test_fertige_abschnitte_werden_nicht_neu_geschrieben():
    store = _Store()
    store.abschnitte = {0: "Schon da"}
    _lauf(["German", _plan("A", "B", "C"),
           _gruppe("B", "C")], store=store)
    assert store.abschnitte[0] == "Schon da"


# ── Was der Schreiber sieht ──────────────────────────────────────────────────

def test_ein_abschnitt_bekommt_die_passage_aus_dem_original():
    text = "Die Frist betraegt dreissig Tage ab Zugang des Bescheids. " * 20
    caller = _caller(["German", _plan("A", "B", "C"), _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=[_quelle(text)], template=get_template("kurzbriefing"),
                       store=_Store()))
    schreibauftrag = caller.client.user_prompts()[-1]
    assert "Die Frist betraegt dreissig Tage" in schreibauftrag
    assert "[a.pdf, S. 1]" in schreibauftrag


def test_der_plan_liest_den_nummerierten_text():
    caller = _caller(["German", _plan("A", "B", "C"), _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=[_quelle()], template=get_template("kurzbriefing"),
                       store=_Store()))
    assert "[1] Ein Satz." in caller.client.user_prompts()[1]


# ── Sprachprobe ──────────────────────────────────────────────────────────────

def test_die_sprachprobe_kommt_aus_der_mitte():
    text = "A" * 5000 + "MITTE" + "B" * 5000
    assert "MITTE" in pl.language_sample(text)


def test_ein_kurzer_text_ist_seine_eigene_probe():
    assert pl.language_sample("Kurzer Satz.") == "Kurzer Satz."


@pytest.mark.parametrize("roh,erwartet", [
    ("German", "German"), (" german. ", "german"), ('"Swiss German"', "Swiss German"),
    ("", None), ("Das ist ein ganzer Satz ueber die Sprache", None), ("12345", None),
])
def test_der_sprachname_wird_auf_einen_namen_reduziert(roh, erwartet):
    assert pl.clean_language_name(roh) == erwartet
