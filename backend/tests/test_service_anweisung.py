"""Die Anweisung an Podcast, Präsentation und Zusammenfassung: Thema engt ein, Stil formt, Unsinn fällt weg."""

import asyncio
import json

import pytest

from src.services import anweisung
from src.services.source_reading import Piece, Source


def _quelle(name: str, text: str = "Ein Satz. " * 50) -> Source:
    return Source(dateiname=name, fassung="x", text=text, seiten=1,
                  stuecke=[Piece(seite=1, von=0, bis=len(text))])


# ── Der Weg selbst ───────────────────────────────────────────────────────────

class TestWeg:
    def test_liest_die_drei_wege(self):
        assert anweisung.lies_weg('{"way": "topic"}') == anweisung.THEMA
        assert anweisung.lies_weg('<think>hm</think>{"way": "ignored"}') == anweisung.WEG
        assert anweisung.lies_weg('{"way": "nonsense"}') == anweisung.UNSINN
        assert anweisung.lies_weg('```json\n{"way": "Manner"}\n```') == anweisung.STIL

    def test_eine_unlesbare_antwort_gilt_als_stil(self):
        assert anweisung.lies_weg("Quatsch") == anweisung.STIL
        assert anweisung.lies_weg('{"way": "vielleicht"}') == anweisung.STIL
        assert anweisung.lies_weg(None) == anweisung.STIL

    def test_ein_verlorener_aufruf_gilt_als_stil(self):
        def kaputt(nachrichten):
            raise ValueError("kaputt")
        assert anweisung.entscheide(kaputt, "nur Kapitel 2", "M", "x") == anweisung.STIL

    def test_ein_voller_anbieter_bricht_die_etappe_ab(self):
        def voll(nachrichten):
            raise RuntimeError("429 too many requests")
        with pytest.raises(RuntimeError):
            anweisung.entscheide(voll, "nur Kapitel 2", "M", "x")

    def test_der_aufruf_liest_material_und_anweisung(self):
        gesehen = []
        anweisung.entscheide(lambda n: gesehen.append(n) or '{"way": "topic"}', "nur Kühlung", "STOFF", "x")
        assert "STOFF" in gesehen[0][1]["content"] and "nur Kühlung" in gesehen[0][1]["content"]


class TestZusatz:
    def test_ein_thema_ueberstimmt_den_dateiausgleich(self):
        text = anweisung.plan_zusatz("nur Zitieren", anweisung.THEMA, "slide")
        assert '"nur Zitieren"' in text and "leave everything else out" in text

    def test_ein_stil_formt_nur(self):
        text = anweisung.plan_zusatz("leichte Sprache", anweisung.STIL, "part")
        assert "only says how" in text and "never add content" in text

    def test_ohne_entscheidung_gilt_die_anweisung_als_stil(self):
        assert anweisung.plan_zusatz("leichte Sprache", "", "part") == anweisung.plan_zusatz(
            "leichte Sprache", anweisung.STIL, "part")

    def test_eine_weggefallene_anweisung_erreicht_keinen_aufruf(self):
        assert anweisung.plan_zusatz("Bananenkuchen", anweisung.WEG, "part") == ""
        assert anweisung.schreib_zusatz("Bananenkuchen", anweisung.WEG) == ""
        assert anweisung.plan_zusatz("asdf", anweisung.UNSINN, "part") == ""
        assert anweisung.schreib_zusatz("asdf", anweisung.UNSINN) == ""
        assert anweisung.schreib_zusatz("", anweisung.STIL) == ""

    def test_nur_ein_thema_engt_ein(self):
        assert anweisung.fokus("nur Zitieren", anweisung.THEMA)
        assert not anweisung.fokus("leicht", anweisung.STIL)
        assert not anweisung.fokus("", anweisung.THEMA)


# ── Podcast ──────────────────────────────────────────────────────────────────

def _podcast(**kw):
    from src.features.podcast.schemas import Person, PodcastParams

    return PodcastParams(persons=[Person(name="A"), Person(name="B", role="expert")], **kw)


class TestPodcast:
    def test_ein_thema_verlangt_nicht_jede_datei(self):
        from src.features.podcast import script as skript

        p = _podcast(instructions="nur Zitieren", instruction_way=anweisung.THEMA)
        system, user = (m["content"] for m in skript.plan_messages("M", "stellen", p, 2, ["a.pdf", "b.pdf"]))
        assert "EVERY one of them" not in system
        assert '"nur Zitieren"' in user

    def test_ohne_thema_bleibt_jede_datei(self):
        from src.features.podcast import script as skript

        p = _podcast(instructions="locker", instruction_way=anweisung.STIL)
        system = skript.plan_messages("M", "stellen", p, 2, ["a.pdf", "b.pdf"])[0]["content"]
        assert "EVERY one of them" in system

    def test_unsinn_erreicht_weder_plan_noch_skript(self):
        from src.features.podcast import script as skript

        p = _podcast(instructions="Bananenkuchen backen", instruction_way=anweisung.WEG)
        plan = skript.plan_messages("M", "stellen", p, 2, ["a.pdf"])
        teil = skript.build_messages("M", p, anzahl=4, teil=1, teile=1)
        assert all("Bananenkuchen" not in m["content"] for m in plan + teil)

    def test_unsinn_faellt_ohne_hinweis_weg(self, monkeypatch):
        from src.tasks.podcast_tasks import _script
        from src.services import text_map as tm

        monkeypatch.setattr(_script.store, "save_params", lambda u, j, p: None)
        antwort = type("A", (), {"choices": [type("C", (), {"message": type("M", (), {
            "content": '{"way": "nonsense"}'})()})()]})()
        monkeypatch.setattr("src.services.json_llm.call_json_llm", lambda llm, n, endpoint="tool": antwort)
        p = _podcast(instructions="asdf qwertz")
        _script._weg(object(), tm.Grundlage(material="M", modus=tm.STELLEN, themen=[]), p, 1, "job")
        assert p.instruction_way == anweisung.UNSINN and not p.instruction_unmatched

    def test_der_weg_wird_einmal_entschieden_und_gemerkt(self, monkeypatch):
        from src.tasks.podcast_tasks import _script
        from src.services import text_map as tm

        gespeichert = []
        monkeypatch.setattr(_script.store, "save_params", lambda u, j, p: gespeichert.append(p.model_copy()))
        aufrufe = []
        antwort = type("A", (), {"choices": [type("C", (), {"message": type("M", (), {
            "content": '{"way": "ignored"}'})()})()]})()
        monkeypatch.setattr("src.services.json_llm.call_json_llm",
                            lambda llm, n, endpoint="tool": aufrufe.append(n) or antwort)
        p = _podcast(instructions="Bananenkuchen backen")
        g = tm.Grundlage(material="M", modus=tm.STELLEN, themen=[])
        _script._weg(object(), g, p, 1, "job")
        _script._weg(object(), g, p, 1, "job")
        assert len(aufrufe) == 1
        assert p.instruction_way == anweisung.WEG and p.instruction_unmatched
        assert gespeichert[0].instruction_unmatched


# ── Präsentation ─────────────────────────────────────────────────────────────

class TestPraesentation:
    def test_ein_thema_verlangt_keine_folien_je_datei(self):
        from src.features.praesentation import gliederung
        from src.features.praesentation.schemas import PraesentationParams

        p = PraesentationParams(instructions="nur Zitieren", instruction_way=anweisung.THEMA)
        system, user = (m["content"] for m in gliederung.build_messages("M", p, ["text"]))
        assert "EVERY one of" not in system
        assert "leave everything else out" in user

    def test_unsinn_erreicht_keine_folie(self):
        from src.features.praesentation import folien
        from src.features.praesentation.schemas import OutlineRow, PraesentationParams

        p = PraesentationParams(instructions="Bananenkuchen", instruction_way=anweisung.WEG)
        form = {"ueberschrift": 8, "zwischentitel": [], "fliesstexte": [], "bilder": 0, "body_kinds": []}
        n = folien.build_messages("M", p, [OutlineRow(id="s1", title="T", gist="g")], {"s1": form})
        assert "Bananenkuchen" not in n[1]["content"]

    def test_eine_folie_ohne_stellen_ist_unbrauchbar(self):
        from src.features.praesentation import gliederung

        with pytest.raises(gliederung.Unusable):
            gliederung.parse_einzel('{"covered": true, "title": "T", "gist": "g", "refs": []}', lambda r: [])

    def test_eine_neue_folie_bekommt_ihre_stellen(self, monkeypatch):
        from src.features.praesentation.schemas import Outline, OutlineRow, PraesentationParams
        from src.tasks.praesentation_tasks import _build

        antwort = json.dumps({"covered": False, "title": "Sekundärzitate meiden", "gist": "Warum",
                              "refs": [1]})
        gesehen = []
        monkeypatch.setattr(_build, "call_json_llm", lambda llm, n, endpoint="tool": gesehen.append(n) or type(
            "A", (), {"choices": [type("C", (), {"message": type("M", (), {"content": antwort})()})()]})())
        monkeypatch.setattr(_build.feature_router, "make_llm_client", lambda b: object())
        monkeypatch.setattr(_build, "binding_for", lambda f, p: None)
        monkeypatch.setattr(_build, "assert_not_cancelled", lambda job: None)
        gesichert = []
        monkeypatch.setattr(_build.store, "load_map", lambda u, j: None)
        monkeypatch.setattr(_build.store, "save_user_outline", lambda u, j, o: gesichert.append(o))
        neu = OutlineRow(id="s9", title="Bananenkuchen", wunsch="Bananenkuchen mit Einhörnern")
        agenda = OutlineRow(id="s2", title="Überblick")
        outline = Outline(rows=[OutlineRow(id="s1", title="Zitieren", stellen=[1]), agenda, neu])
        _build._wuensche_verorten("job", 1, PraesentationParams(), [_quelle("a.pdf")], outline, [neu, agenda])
        assert len(gesehen) == 1 and "Bananenkuchen mit Einhörnern" in gesehen[0][1]["content"]
        # Not in the material, so the system chose the subject and its title replaces the wish.
        assert neu.title == "Sekundärzitate meiden" and neu.stellen == [1] and neu.wunsch == ""
        assert agenda.stellen == [] and gesichert

    def test_ein_getippter_titel_bleibt_wenn_das_material_ihn_traegt(self, monkeypatch):
        from src.features.praesentation.schemas import Outline, OutlineRow, PraesentationParams
        from src.tasks.praesentation_tasks import _build

        antwort = json.dumps({"covered": True, "title": "Anders", "gist": "g", "refs": [1]})
        monkeypatch.setattr(_build, "call_json_llm", lambda llm, n, endpoint="tool": type(
            "A", (), {"choices": [type("C", (), {"message": type("M", (), {"content": antwort})()})()]})())
        monkeypatch.setattr(_build.feature_router, "make_llm_client", lambda b: object())
        monkeypatch.setattr(_build, "binding_for", lambda f, p: None)
        monkeypatch.setattr(_build, "assert_not_cancelled", lambda job: None)
        monkeypatch.setattr(_build.store, "load_map", lambda u, j: None)
        monkeypatch.setattr(_build.store, "save_user_outline", lambda u, j, o: None)
        neu = OutlineRow(id="s9", title="Zitierstile", wunsch="Zitierstile")
        _build._wuensche_verorten("job", 1, PraesentationParams(), [_quelle("a.pdf")], Outline(rows=[neu]), [neu])
        assert neu.title == "Zitierstile" and neu.stellen == [1]


# ── Zusammenfassung ──────────────────────────────────────────────────────────

class TestZusammenfassung:
    def test_ein_thema_verlangt_nicht_jede_datei(self):
        from src.features.summary.writing import _outline_system

        mit = _outline_system("German", "BP", 4, 2, fokus=True)
        ohne = _outline_system("German", "BP", 4, 2)
        assert "EVERY one of" not in mit and "EVERY one of" in ohne

    def test_unsinn_erreicht_keinen_schreiber(self):
        from src.features.summary import pipeline as pl
        from src.features.summary.models import Caller
        from src.features.summary.templates import get_template
        from tests.summary_helpers import FakeClient
        from tests.test_summary_pipeline import _Store, _gruppe, _plan

        client = FakeClient(['{"way": "ignored"}', _plan("A", "B", "C"), _gruppe("A", "B", "C")])
        store = _Store()
        asyncio.run(pl.run(Caller(client, "m", window_tokens=262_144), sources=[_quelle("a.pdf")],
                           template=get_template("zeitstrahl"), store=store,
                           instructions="Bananenkuchen backen"))
        assert "Bananenkuchen" in client.user_prompts()[0]
        assert all("Bananenkuchen" not in u for u in client.user_prompts()[1:])
        assert store.plan["instruction_way"] == anweisung.WEG

    def test_ein_thema_laesst_den_rest_des_textes_draussen(self):
        from src.features.summary import pipeline as pl
        from src.features.summary.models import Caller
        from src.features.summary.templates import get_template
        from tests.summary_helpers import FakeClient
        from tests.test_summary_pipeline import _Store, _gruppe, _plan

        client = FakeClient(['{"way": "topic"}', _plan("A", "B", "C"), _gruppe("A", "B", "C")])
        store = _Store()
        quellen = [_quelle("a.pdf"), _quelle("b.pdf")]
        asyncio.run(pl.run(Caller(client, "m", window_tokens=262_144), sources=quellen,
                           template=get_template("zeitstrahl"), store=store, instructions="nur A"))
        # No second plan for the file left out, and its passage goes to no section.
        assert len(client.gesendet) == 3
        assert all(2 not in a["stellen"] for a in store.plan["sections"])
