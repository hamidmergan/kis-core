"""Planning follows the material, writing follows the plan, both follow the build plan."""

import json

import pytest
from tests.summary_helpers import FakeClient

from src.features.summary import writing as wr
from src.features.summary.facts import Fact
from src.features.summary.models import Caller, Section
from src.limits import SUMMARY_MAX_SECTIONS, SUMMARY_MIN_SECTIONS

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a", "fact_ids": [1]},
    {"title": "B", "description": "b", "fact_ids": [2]},
    {"title": "C", "description": "c", "fact_ids": [3]}]})


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


def _vorrat(anzahl: int = 3, datei: str = "a.pdf") -> list[Fact]:
    return [Fact(i, "figure", f"Aussage {i}", f"Beleg {i}", "doc_01", datei)
            for i in range(1, anzahl + 1)]


async def _plane(caller, **kwargs):
    vorrat = kwargs.pop("pool", _vorrat())
    return await wr.plan_outline(caller, **{
        "language": "German", "template_body": "BAUPLAN", "sources": ["a.pdf"],
        "pool": vorrat, "pool_text": "#1 A", "target": 12, **kwargs})


async def _schreibe(caller, **kwargs):
    return await wr.write_section(caller, **{
        "language": "German", "template_body": "B", "section": Section(title="B", scope="b"),
        "others": [], "written": [], "facts": _vorrat(1), "budget": 10_000, **kwargs})


class TestRichtwert:
    def test_wenig_stoff_gibt_die_untergrenze(self):
        assert wr.target_sections(1_000) == SUMMARY_MIN_SECTIONS

    def test_der_richtwert_waechst_mit_dem_stoff(self):
        assert wr.target_sections(48_000) == 12
        assert wr.target_sections(80_000) == 20

    def test_die_obergrenze_haelt(self):
        assert wr.target_sections(10_000_000) == SUMMARY_MAX_SECTIONS


class TestGliederungLesen:
    def test_eine_saubere_antwort_wird_gelesen(self):
        plan = wr.parse_outline(_PLAN)
        assert plan.intro == "Vorweg."
        assert [s.title for s in plan.sections] == ["A", "B", "C"]
        assert [s.fact_ids for s in plan.sections] == [[1], [2], [3]]
        assert plan.sections[0].scope == "a"

    def test_ein_zaun_und_ein_denkblock_werden_abgestreift(self):
        roh = "<think>hm</think>```json\n" + _PLAN + "\n```"
        assert len(wr.parse_outline(roh).sections) == 3

    def test_kein_json_gibt_eine_leere_gliederung(self):
        assert wr.parse_outline("Ich kann das nicht.").sections == []

    def test_zu_wenige_abschnitte_gelten_als_misslungen(self):
        roh = json.dumps({"sections": [{"title": "Nur einer", "fact_ids": [1]}]})
        assert wr.parse_outline(roh).sections == []

    def test_doppelte_und_leere_titel_fallen_weg(self):
        roh = json.dumps({"sections": [{"title": "A"}, {"title": "a"}, {"title": ""},
                                        {"title": "B"}, {"title": "C"}]})
        assert [s.title for s in wr.parse_outline(roh).sections] == ["A", "B", "C"]

    def test_ein_fakt_in_zwei_abschnitten_bleibt_im_ersten(self):
        roh = json.dumps({"sections": [
            {"title": "A", "fact_ids": [1, 2]}, {"title": "B", "fact_ids": [2, 3]},
            {"title": "C", "fact_ids": [3]}]})
        plan = wr.parse_outline(roh, {1, 2, 3})
        assert [s.fact_ids for s in plan.sections] == [[1, 2], [3], []]

    def test_erfundene_nummern_fallen_weg(self):
        roh = json.dumps({"sections": [
            {"title": "A", "fact_ids": [1, 99]}, {"title": "B", "fact_ids": ["2"]},
            {"title": "C", "fact_ids": ["keine Zahl"]}]})
        plan = wr.parse_outline(roh, {1, 2, 3})
        assert [s.fact_ids for s in plan.sections] == [[1], [2], []]


class TestAbdeckung:
    def test_alles_zugeordnet_ist_voll(self):
        plan = wr.parse_outline(_PLAN, {1, 2, 3})
        assert wr.coverage(plan, _vorrat()) == 1.0

    def test_die_haelfte_zugeordnet_ist_die_haelfte(self):
        plan = wr.parse_outline(_PLAN, {1, 2, 3})
        assert wr.coverage(plan, _vorrat(6)) == 0.5

    def test_ein_leerer_vorrat_gilt_als_abgedeckt(self):
        assert wr.coverage(wr.parse_outline(_PLAN), []) == 1.0


class TestPlanen:
    async def test_der_planer_bekommt_vorlage_richtwert_und_das_feste_schema(self):
        caller = _caller([_PLAN])
        plan = await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "BAUPLAN" in system and "around 12 sections" in system
        assert "Assign EVERY fact number" in system
        assert caller.client.optionen[0]["response_format"] is wr.OUTLINE_SCHEMA
        assert len(plan.sections) == 3

    async def test_die_abschnitte_folgen_dem_thema_nicht_der_datei(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        assert "never the file a fact came from" in caller.client.system_prompts()[0]

    async def test_eine_lueckenhafte_gliederung_wird_einmal_wiederholt(self, monkeypatch):
        """Deckt die erste Antwort zu wenig ab, fragt der Planer genau noch einmal."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        duenn = json.dumps({"sections": [{"title": "A", "fact_ids": [1]}, {"title": "B"},
                                          {"title": "C"}]})
        voll = json.dumps({"sections": [{"title": "A", "fact_ids": [1, 2]},
                                         {"title": "B", "fact_ids": [3, 4]},
                                         {"title": "C", "fact_ids": [5, 6]}]})
        caller = _caller([duenn, voll])
        plan = await _plane(caller, pool=_vorrat(6))
        assert len(caller.client.gesendet) == 2
        assert sum(len(s.fact_ids) for s in plan.sections) == 6

    async def test_eine_volle_gliederung_wird_nicht_wiederholt(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        assert len(caller.client.gesendet) == 1

    async def test_bleibt_es_lueckenhaft_wird_die_bessere_antwort_aufgefuellt(self, monkeypatch):
        """Kein Nachfass-Aufruf mehr in der Warteschlange heisst: round robin schliesst die Luecke."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        schlecht = json.dumps({"sections": [{"title": "A", "fact_ids": [1]}, {"title": "B"},
                                             {"title": "C"}]})
        besser = json.dumps({"sections": [{"title": "A", "fact_ids": [1, 2]}, {"title": "B"},
                                           {"title": "C"}]})
        caller = _caller([schlecht, besser])
        plan = await _plane(caller, pool=_vorrat(6))
        assert sum(len(s.fact_ids) for s in plan.sections) == 6
        assert {1, 2}.issubset(plan.sections[0].fact_ids)

    async def test_eine_luecke_wird_zuerst_per_nachfass_aufruf_geschlossen(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        duenn = json.dumps({"sections": [{"title": "A", "fact_ids": [1]}, {"title": "B"},
                                          {"title": "C"}]})
        nachfass = json.dumps({"assignments": [
            {"fact_id": 2, "section_index": 1}, {"fact_id": 3, "section_index": 2},
            {"fact_id": 4, "section_index": 1}, {"fact_id": 5, "section_index": 2}]})
        caller = _caller([duenn, duenn, nachfass])
        plan = await _plane(caller, pool=_vorrat(5))
        assert sum(len(s.fact_ids) for s in plan.sections) == 5
        assert plan.sections[1].fact_ids == [2, 4]
        assert plan.sections[2].fact_ids == [3, 5]
        assert "outline:gaps" in [o.get("name") for o in caller.client.optionen]

    async def test_zwei_unlesbare_antworten_geben_eine_leere_gliederung(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", "wieder nix"])
        plan = await _plane(caller)
        assert plan.sections == []
        assert len(caller.client.gesendet) == 2


class TestNachfassZuordnung:
    def test_parse_liest_gueltige_zuordnungen(self):
        roh = json.dumps({"assignments": [{"fact_id": 1, "section_index": 0},
                                          {"fact_id": 2, "section_index": 1}]})
        assert wr.parse_assignments(roh, {1, 2}, 2) == {1: 0, 2: 1}

    def test_unbekannter_fakt_und_ungueltiger_abschnitt_fallen_weg(self):
        roh = json.dumps({"assignments": [{"fact_id": 99, "section_index": 0},
                                          {"fact_id": 1, "section_index": 5}]})
        assert wr.parse_assignments(roh, {1}, 2) == {}

    def test_unlesbare_antwort_gibt_leere_zuordnung(self):
        assert wr.parse_assignments("nix", {1}, 2) == {}

    def test_round_robin_verteilt_ohne_luecke(self):
        sections = [Section(title="A"), Section(title="B")]
        wr.distribute_remaining(sections, _vorrat(3))
        assert [s.fact_ids for s in sections] == [[1, 3], [2]]

    async def test_nachfass_aufruf_nennt_die_bestehenden_abschnitte(self):
        caller = _caller([json.dumps({"assignments": []})])
        sections = [Section(title="A", scope="erstens"), Section(title="B", scope="zweitens")]
        await wr.fill_gaps(caller, language="German", sections=sections, facts=_vorrat(1))
        system = caller.client.system_prompts()[0]
        assert "0: A. erstens" in system and "1: B. zweitens" in system
        assert "never invent a section" in system.casefold() or "never invent" in system

    async def test_ein_gescheiterter_nachfass_aufruf_verhindert_close_gaps_nicht(self):
        caller = _caller([RuntimeError("kaputt")])
        outline = wr.Outline(sections=[Section(title="A", fact_ids=[1])])
        await wr.close_gaps(caller, language="German", outline=outline, pool=_vorrat(3))
        assert sum(len(s.fact_ids) for s in outline.sections) == 3


class TestSchreiben:
    async def test_ein_abschnitt_sieht_die_vorigen_und_meidet_die_kommenden(self):
        caller = _caller(["Text B"])
        text = await _schreibe(caller, others=[Section(title="C", scope="c")],
                               written=[("A", "Text A")])
        user = caller.client.user_prompts()[0]
        assert text == "Text B"
        assert "YOUR HEADING: B" in user and "## A\nText A" in user and "- C: c" in user

    async def test_ein_abschnitt_bekommt_nur_seine_eigenen_fakten(self):
        caller = _caller(["Text B"])
        await _schreibe(caller, facts=[_vorrat(3)[1]])
        user = caller.client.user_prompts()[0]
        assert "#2" in user and "Aussage 2" in user
        assert "Aussage 1" not in user and "Aussage 3" not in user

    async def test_die_fakten_tragen_ihren_beleg(self):
        caller = _caller(["Text B"])
        await _schreibe(caller)
        assert 'Beleg: "Beleg 1"' in caller.client.user_prompts()[0]

    async def test_die_quellenmarke_ist_der_dateiname(self):
        caller = _caller(["Text B"])
        await _schreibe(caller, facts=_vorrat(1, "AMG74.pdf"))
        system = caller.client.system_prompts()[0]
        user = caller.client.user_prompts()[0]
        assert "[AMG74.pdf]" in system and "[AMG74.pdf]" in user
        assert "never collect them at the end" in system

    async def test_schreibaufrufe_sind_gedeckelt_und_verlieren_nur_die_halbe_zeile(self):
        from src.limits import SUMMARY_WRITE_MAX_TOKENS
        caller = _caller([("Zeile eins.\nZeile zwei.\nZeile dr", "length")])
        text = await _schreibe(caller)
        assert text == "Zeile eins.\nZeile zwei."
        assert caller.client.optionen[0]["max_tokens"] == SUMMARY_WRITE_MAX_TOKENS

    async def test_die_fakten_eines_abschnitts_sind_gedeckelt(self):
        caller = _caller(["Text B"])
        await _schreibe(caller, facts=_vorrat(50), budget=200)
        user = caller.client.user_prompts()[0]
        anfang = user.index("YOUR FACTS:\n\n") + len("YOUR FACTS:\n\n")
        assert len(user[anfang:]) == 200

    async def test_das_dokument_bisher_wird_auf_die_reserve_gekuerzt(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_PROMPT_RESERVE_CHARS", 200)
        caller = _caller(["Text C"])
        lang = "x" * 500
        await _schreibe(caller, section=Section(title="C", scope="c"),
                        written=[("A", lang), ("B", "kurz")])
        user = caller.client.user_prompts()[0]
        assert "## A\n## B" in user and "[...]" in user and "kurz" in user
        assert user.count("x") < 500

    async def test_eine_wiederholte_ueberschrift_wird_abgeschnitten(self):
        caller = _caller(["## B\n\nText B"])
        assert await _schreibe(caller) == "Text B"

    async def test_eine_anders_formulierte_ueberschrift_wird_ebenfalls_abgeschnitten(self):
        caller = _caller(["### Ganz anders gesagt\n\nText B"])
        assert await _schreibe(caller) == "Text B"

    async def test_eine_zwischenueberschrift_bleibt_stehen(self):
        caller = _caller(["Text B\n\n## Unterpunkt\n\nmehr Text"])
        assert await _schreibe(caller) == "Text B\n\n## Unterpunkt\n\nmehr Text"

    async def test_nur_eine_ueberschrift_gilt_als_leere_antwort(self):
        caller = _caller(["## B"])
        with pytest.raises(RuntimeError):
            await _schreibe(caller)

    async def test_der_einzelaufruf_schreibt_alles_auf_einmal(self):
        caller = _caller(["Alles."])
        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["a.pdf", "b.pdf"], pool=_vorrat(),
                                       pool_text="#1 A")
        assert text == "Alles."
        assert "ONE document covering all sources" in caller.client.system_prompts()[0]

    async def test_wenn_die_ueberschriften_allein_die_reserve_sprengen_bleibt_keine_prosa(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_PROMPT_RESERVE_CHARS", 200)
        caller = _caller(["Text Z"])
        written = [(f"Kapitel{i:02d}", "y" * 50) for i in range(20)]
        await _schreibe(caller, section=Section(title="Z", scope="z"), written=written)
        user = caller.client.user_prompts()[0]
        praefix, suffix = "THE DOCUMENT SO FAR:\n", "\n\nYOUR FACTS:\n\n"
        anfang = user.index(praefix) + len(praefix)
        bisher = user[anfang:user.index(suffix, anfang)]
        koepfe = "\n".join(f"## {titel}" for titel, _ in written)
        assert len(koepfe) > 200
        assert bisher == f"{koepfe}\n\n[...]\n"


class TestFaktenEinesAbschnitts:
    def test_ein_abschnitt_bekommt_die_ihm_zugeordneten(self):
        vorrat = _vorrat(3)
        eigene = wr.section_facts(Section(title="A", fact_ids=[2, 3]), vorrat)
        assert [f.fact_id for f in eigene] == [2, 3]

    def test_ein_abschnitt_ohne_zuordnung_bekommt_den_ganzen_vorrat(self):
        """Ein Bauplan darf einen Teil verlangen, der sich auf alles stuetzt."""
        vorrat = _vorrat(3)
        assert wr.section_facts(Section(title="Glossar"), vorrat) == vorrat


class TestZusammensetzen:
    def test_mit_ueberschriften(self):
        assert wr.assemble("Vorweg.", ["A", "B"], ["ta", "tb"], True) == \
            "Vorweg.\n\n## A\n\nta\n\n## B\n\ntb"

    def test_ohne_ueberschriften_laeuft_die_prosa_durch(self):
        assert wr.assemble("", ["A", "B"], ["ta", "tb"], False) == "ta\n\ntb"

    def test_leere_abschnitte_fallen_weg(self):
        assert wr.assemble("", ["A", "B"], ["", "tb"], True) == "## B\n\ntb"
