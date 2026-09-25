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


def _lauf(antworten, quellen=None, store=None, vorlage="zeitstrahl"):
    store = store or _Store()
    ergebnis = asyncio.run(pl.run(_caller(antworten), sources=quellen or [_quelle()],
                                  template=get_template(vorlage), store=store))
    return ergebnis, store


# ── Sprache ──────────────────────────────────────────────────────────────────

def test_die_sprache_wird_ohne_modellaufruf_erkannt_und_gemerkt():
    client = FakeClient([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    store = _Store()
    asyncio.run(pl.run(Caller(client, "m"), sources=[_quelle()],
                       template=get_template("zeitstrahl"), store=store))
    assert store.sprache == "German"
    assert all(k.get("name") != "language" for k in client.optionen)


def test_englischer_text_wird_als_englisch_erkannt():
    text = "This is a plain English sentence about the weather. " * 5
    assert pl.detect_language([_quelle(text)]) == "English"


def test_eine_gemerkte_sprache_wird_nicht_erneut_erkannt():
    store = _Store()
    store.sprache = "Swiss German"
    _lauf([_plan("A", "B", "C"),
           _gruppe("A", "B", "C")], store=store)
    assert store.sprache == "Swiss German"


def test_text_ohne_sprache_faellt_zurueck():
    assert pl.detect_language([_quelle("1234 5678 " * 20)]) == LANGUAGE_FALLBACK


def test_zu_wenig_text_faellt_zurueck():
    assert pl.detect_language([_quelle("Kurz.")]) == LANGUAGE_FALLBACK


# ── Grundlage und Plan ──────────────────────────────────────────────────────────

def test_ein_lauf_liefert_den_zusammengesetzten_text():
    ergebnis, _ = _lauf([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    assert "Die Einleitung." in ergebnis
    assert "Text A" in ergebnis and "Text C" in ergebnis


def test_die_grundlage_wird_gesichert():
    _, store = _lauf([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    assert store.grundlage == {"modus": "stellen", "themen": []}


def test_ohne_text_scheitert_der_lauf():
    leer = Source(dateiname="a.pdf", fassung="x", text="", seiten=0, stuecke=[])
    with pytest.raises(RuntimeError):
        _lauf([], quellen=[leer])


def test_ein_zu_langer_text_wird_ueber_themen_geplant():
    """Passt der Text nicht in ein Fenster, liest jeder Teil nur seine Themen heraus."""
    stuecke = [Piece(seite=1 + i // 5, von=i * 1000, bis=(i + 1) * 1000) for i in range(300)]
    gross = Source(dateiname="g.pdf", fassung="x", text="Ein Wort " * 33_334, seiten=60,
                   stuecke=stuecke)
    themen = json.dumps({"topics": [{"title": "Thema", "gist": "g", "refs": ["1-3"]}]})
    caller = Caller(FakeClient([themen, themen, themen,
                                _plan("A", "B", "C"), _gruppe("A", "B", "C")]),
                    "m", window_tokens=50_000)
    store = _Store()
    asyncio.run(pl.run(caller, sources=[gross], template=get_template("zeitstrahl"),
                       store=store))
    assert store.grundlage["modus"] == "themen"
    assert "numbered list of topics" in caller.client.system_prompts()[3]


def test_der_plan_wird_gesichert_und_nicht_neu_geholt():
    store = _Store()
    _lauf([_plan("A", "B", "C"),
           _gruppe("A", "B", "C")], store=store)
    assert [a["title"] for a in store.plan["sections"]] == ["A", "B", "C"]


def test_fertige_abschnitte_werden_nicht_neu_geschrieben():
    store = _Store()
    store.abschnitte = {0: "Schon da"}
    _lauf([_plan("A", "B", "C"),
           _gruppe("B", "C")], store=store)
    assert store.abschnitte[0] == "Schon da"


# ── Was der Schreiber sieht ──────────────────────────────────────────────────

def test_ein_abschnitt_bekommt_die_passage_aus_dem_original():
    text = "Die Frist betraegt dreissig Tage ab Zugang des Bescheids. " * 20
    caller = _caller([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=[_quelle(text)], template=get_template("zeitstrahl"),
                       store=_Store()))
    schreibauftrag = caller.client.user_prompts()[-1]
    assert "Die Frist betraegt dreissig Tage" in schreibauftrag
    assert "[a.pdf, S. 1]" in schreibauftrag


def test_der_plan_liest_den_nummerierten_text():
    caller = _caller([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=[_quelle()], template=get_template("zeitstrahl"),
                       store=_Store()))
    assert "[1] Ein Satz." in caller.client.user_prompts()[0]


# ── Sprachprobe ──────────────────────────────────────────────────────────────

def test_die_sprachprobe_kommt_aus_der_mitte():
    text = "A" * 5000 + "MITTE" + "B" * 5000
    assert "MITTE" in pl.language_sample(text)


def test_ein_kurzer_text_ist_seine_eigene_probe():
    assert pl.language_sample("Kurzer Satz.") == "Kurzer Satz."


# ── Fortschritt ──────────────────────────────────────────────────────────────

# Mirrors tools.summarize.step in frontend/messages, a step outside it breaks the page.
SCHRITTE_IM_FRONTEND = {"extract", "map", "outline", "section", "compose"}


def test_jeder_gemeldete_schritt_ist_dem_frontend_bekannt():
    _, store = _lauf([_plan("A", "B", "C"), _gruppe("A", "B", "C")])
    gemeldet = {schritt for schritt, _, _ in store.fortschritt}
    assert gemeldet
    assert gemeldet <= SCHRITTE_IM_FRONTEND


# ── Gleichzeitig schreiben ───────────────────────────────────────────────────

class _NachUeberschrift:
    """Beantwortet jeden Abschnitt nach seiner Überschrift und zählt, wie viele gleichzeitig laufen."""

    def __init__(self, plan: str):
        self.plan = plan
        self.jetzt = 0
        self.hoechstens = 0
        self.abschnitte: list[tuple[str, str]] = []
        self.chat = type("Chat", (), {"completions": self})()

    def with_options(self, **_):
        return self

    async def create(self, *, model, messages, **kwargs):
        from tests.summary_helpers import FakeAntwort
        name = kwargs.get("name", "")
        if name.startswith("outline"):
            return FakeAntwort(self.plan)
        self.jetzt += 1
        self.hoechstens = max(self.hoechstens, self.jetzt)
        try:
            await asyncio.sleep(0.01)
        finally:
            self.jetzt -= 1
        user = messages[-1]["content"]
        titel = user.split("YOUR HEADING: ", 1)[1].split("\n", 1)[0]
        self.abschnitte.append((titel, user))
        return FakeAntwort(f"Text {titel}")


def _gleichzeitig(monkeypatch, titel, vorlage="zeitstrahl"):
    # Every section its own group, so each one is a call of its own.
    monkeypatch.setattr(pl, "SUMMARY_SECTION_GROUP_CHARS", 1)
    client = _NachUeberschrift(_plan(*titel))
    ergebnis = asyncio.run(pl.run(Caller(client, "m", window_tokens=262_144),
                                  sources=[_quelle()], template=get_template(vorlage),
                                  store=_Store()))
    return ergebnis, client


def test_die_abschnitte_laufen_zu_dritt_gleichzeitig(monkeypatch):
    ergebnis, client = _gleichzeitig(monkeypatch, ["A", "B", "C", "D", "E", "F"])
    assert client.hoechstens == 3
    assert all(f"Text {t}" in ergebnis for t in "ABCDEF")


def test_ohne_abhaengigen_schluss_sieht_kein_abschnitt_fremden_text(monkeypatch):
    _, client = _gleichzeitig(monkeypatch, ["A", "B", "C", "D"])
    assert not any("Text " in user for _, user in client.abschnitte)


def test_im_lernleitfaden_kommt_der_schluss_zuletzt_und_liest_den_text(monkeypatch):
    _, client = _gleichzeitig(monkeypatch, ["A", "B", "C", "Antworten"], vorlage="lernleitfaden")
    titel, user = client.abschnitte[-1]
    assert titel == "Antworten"
    assert "Text A" in user and "Text B" in user and "Text C" in user


# ── Jede Datei kommt vor ─────────────────────────────────────────────────────

def _plan_mit_refs(*paare) -> str:
    return json.dumps({"title": "T", "intro": "I.", "sections": [
        {"section_index": i, "title": t, "description": "d", "refs": refs}
        for i, (t, refs) in enumerate(paare)]})


def test_ein_plan_der_eine_datei_auslaesst_wird_mit_hinweis_neu_verlangt():
    zwei = [_quelle(name="a.pdf"), _quelle(name="b.pdf")]
    einseitig = _plan_mit_refs(("A", ["1"]), ("B", ["1"]), ("C", ["1"]))
    ausgewogen = _plan_mit_refs(("A", ["1"]), ("B", ["2"]), ("C", ["1-2"]))
    caller = _caller([einseitig, ausgewogen, _gruppe("A", "B", "C")])
    store = _Store()
    asyncio.run(pl.run(caller, sources=zwei, template=get_template("zeitstrahl"), store=store))
    zweiter_plan = caller.client.user_prompts()[1]
    assert "b.pdf" in zweiter_plan.split("MATERIAL:")[0]
    assert [a["stellen"] for a in store.plan["sections"]][1] == [2]


def test_ein_ausgewogener_plan_wird_nicht_neu_verlangt():
    zwei = [_quelle(name="a.pdf"), _quelle(name="b.pdf")]
    ausgewogen = _plan_mit_refs(("A", ["1"]), ("B", ["2"]), ("C", ["1-2"]))
    caller = _caller([ausgewogen, _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=zwei, template=get_template("zeitstrahl"),
                       store=_Store()))
    assert sum(1 for o in caller.client.optionen if o.get("name", "").startswith("outline")) == 1


# ── Die Vorlage bestimmt die Form ────────────────────────────────────────────

def test_das_kurzbriefing_bleibt_bei_wenigen_abschnitten_auch_bei_viel_stoff():
    from src.features.summary import writing
    vorlage = get_template("kurzbriefing")
    ziel = writing.target_sections(500_000, 4, vorlage.sections)
    assert vorlage.sections[0] <= ziel <= vorlage.sections[1]


def test_jeder_schreiber_bekommt_seine_wortzahl_aus_der_vorlage(monkeypatch):
    _, client = _gleichzeitig(monkeypatch, ["A", "B", "C", "D"], vorlage="kurzbriefing")
    vorlage = get_template("kurzbriefing")
    worte = vorlage.length_chars // 4 // 6
    assert all(f"about {worte} words" in user for _, user in client.abschnitte)


def test_die_kurznamen_aus_dem_plan_erreichen_jeden_schreiber(monkeypatch):
    monkeypatch.setattr(pl, "SUMMARY_SECTION_GROUP_CHARS", 1)
    plan = json.dumps({"title": "T", "intro": "I.",
                       "documents": [{"file": "a.pdf", "short_name": "AGes"}],
                       "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
    client = _NachUeberschrift(plan)
    asyncio.run(pl.run(Caller(client, "m", window_tokens=262_144), sources=[_quelle()],
                       template=get_template("zeitstrahl"), store=_Store()))
    assert all("a.pdf = AGes" in user for _, user in client.abschnitte)


# ── Vorrang der vom Plan genannten Stellen ──────────────────────────────────────

def _markiert(stuecke: int) -> Source:
    text = "".join(f"<{i + 1:03d}>".ljust(10, ".") for i in range(stuecke))
    return Source(dateiname="a.pdf", fassung="x", text=text, seiten=1,
                  stuecke=[Piece(seite=1, von=i * 10, bis=i * 10 + 10) for i in range(stuecke)])


def test_der_plan_merkt_sich_seine_eigenen_stellen():
    store = _Store()
    _lauf([_plan_mit_refs(("A", ["3"]), ("B", ["17"]), ("C", ["10"])), _gruppe("A", "B", "C")],
          quellen=[_markiert(20)], store=store)
    assert [a["genannt"] for a in store.plan["sections"]] == [[3], [17], [10]]
    assert sum(len(a["stellen"]) for a in store.plan["sections"]) == 20


def test_ein_knappes_budget_behaelt_die_vom_plan_genannten_stellen(monkeypatch):
    monkeypatch.setattr(pl, "MAP_MATERIAL_MAX_CHARS", 240)
    caller = _caller([_plan_mit_refs(("A", ["3"]), ("B", ["17"]), ("C", ["10"])),
                      _gruppe("A", "B", "C")])
    asyncio.run(pl.run(caller, sources=[_markiert(20)], template=get_template("zeitstrahl"),
                       store=_Store()))
    schreibauftrag = caller.client.user_prompts()[-1]
    assert all(m in schreibauftrag for m in ("<003>", "<017>", "<010>"))


def test_eine_von_zwei_abschnitten_genannte_stelle_bleibt_beim_ersten():
    store = _Store()
    _lauf([_plan_mit_refs(("A", ["3", "10"]), ("B", ["17"]), ("C", ["10", "12"])),
           _gruppe("A", "B", "C")], quellen=[_markiert(20)], store=store)
    assert [a["genannt"] for a in store.plan["sections"]] == [[3, 10], [17], [12]]


class TestAnweisung:
    """Die eigene Anweisung reist in Planung und Schreiben mit, als letzter Absatz."""

    def test_die_planung_liest_die_anweisung_zuletzt(self):
        from src.features.summary.writing import _outline_user

        text = _outline_user(["a.pdf"], "MATERIAL", instructions="nur Kapitel 2")
        assert text.rstrip().endswith("nur Kapitel 2")
        assert "INSTRUCTION FROM THE TEACHER" in text

    def test_ein_abschnitt_liest_die_anweisung_zuletzt(self):
        from src.features.summary.models import Section
        from src.features.summary.writing import _section_user

        text = _section_user([Section(title="A")], [], None, ["Stoff"], instructions="für Erstsemester")
        assert text.rstrip().endswith("für Erstsemester")

    def test_ohne_anweisung_kein_zusatz(self):
        from src.features.summary.writing import _outline_user

        assert "INSTRUCTION" not in _outline_user(["a.pdf"], "MATERIAL", instructions="  ")
