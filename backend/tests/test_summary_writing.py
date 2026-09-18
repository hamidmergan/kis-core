"""Planning follows the material, writing follows the plan, both follow the build plan."""

import json

import pytest
from tests.summary_helpers import FakeClient

from src.features.summary import writing as wr
from src.features.summary.models import Caller, Section
from src.limits import SUMMARY_MAX_SECTIONS, SUMMARY_MIN_SECTIONS

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "scope": "a"}, {"title": "B", "scope": "b"}, {"title": "C", "scope": "c"}]})


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


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

    def test_ein_zaun_und_ein_denkblock_werden_abgestreift(self):
        roh = "<think>hm</think>```json\n" + _PLAN + "\n```"
        assert len(wr.parse_outline(roh).sections) == 3

    def test_kein_json_gibt_eine_leere_gliederung(self):
        assert wr.parse_outline("Ich kann das nicht.").sections == []

    def test_zu_wenige_abschnitte_gelten_als_misslungen(self):
        roh = json.dumps({"sections": [{"title": "Nur einer"}]})
        assert wr.parse_outline(roh).sections == []

    def test_doppelte_und_leere_titel_fallen_weg(self):
        roh = json.dumps({"sections": [{"title": "A"}, {"title": "a"}, {"title": ""},
                                        {"title": "B"}, {"title": "C"}]})
        assert [s.title for s in wr.parse_outline(roh).sections] == ["A", "B", "C"]


class TestPlanen:
    async def test_der_planer_bekommt_vorlage_richtwert_und_teile(self):
        caller = _caller([_PLAN])
        plan = await wr.plan_outline(caller, language="German", template_body="BAUPLAN",
                                     sources=["q1 (a.pdf)"], facts="F", part_note="- a.pdf: q1t1, q1t2",
                                     target=12)
        system = caller.client.system_prompts()[0]
        assert "BAUPLAN" in system and "around 12 sections" in system
        assert "PARTS OF ONE FILE" in system and "q1t1, q1t2" in system
        assert caller.client.optionen[0]["response_format"] == {"type": "json_object"}
        assert len(plan.sections) == 3

    async def test_ohne_teile_steht_kein_teilehinweis_im_auftrag(self):
        caller = _caller([_PLAN])
        await wr.plan_outline(caller, language="German", template_body="B",
                              sources=["q1 (a.pdf)"], facts="F", part_note="", target=3)
        assert "PARTS OF ONE FILE" not in caller.client.system_prompts()[0]

    async def test_zwei_unlesbare_antworten_geben_eine_leere_gliederung(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", "wieder nix"])
        plan = await wr.plan_outline(caller, language="German", template_body="B",
                                     sources=[], facts="F", part_note="", target=3)
        assert plan.sections == []
        assert len(caller.client.gesendet) == 2


class TestSchreiben:
    async def test_ein_abschnitt_sieht_die_vorigen_und_meidet_die_kommenden(self):
        caller = _caller(["Text B"])
        text = await wr.write_section(
            caller, language="German", template_body="B",
            section=Section(title="B", scope="b"), others=[Section(title="C", scope="c")],
            written=[("A", "Text A")], facts="F", part_note="")
        user = caller.client.user_prompts()[0]
        assert text == "Text B"
        assert "YOUR HEADING: B" in user and "## A\nText A" in user and "- C: c" in user

    async def test_schreibaufrufe_sind_gedeckelt_und_verlieren_nur_die_halbe_zeile(self):
        from src.limits import SUMMARY_WRITE_MAX_TOKENS
        caller = _caller([("Zeile eins.\nZeile zwei.\nZeile dr", "length")])
        text = await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="A", scope="a"),
            others=[], written=[], facts="F", part_note="")
        assert text == "Zeile eins.\nZeile zwei."
        assert caller.client.optionen[0]["max_tokens"] == SUMMARY_WRITE_MAX_TOKENS

    async def test_das_dokument_bisher_wird_auf_die_reserve_gekuerzt(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_PROMPT_RESERVE_CHARS", 200)
        caller = _caller(["Text C"])
        lang = "x" * 500
        await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="C", scope="c"),
            others=[], written=[("A", lang), ("B", "kurz")], facts="F", part_note="")
        user = caller.client.user_prompts()[0]
        assert "## A\n## B" in user and "[...]" in user and "kurz" in user
        assert user.count("x") < 500

    async def test_eine_wiederholte_ueberschrift_wird_abgeschnitten(self):
        caller = _caller(["## B\n\nText B"])
        text = await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="B", scope="b"),
            others=[], written=[], facts="F", part_note="")
        assert text == "Text B"

    async def test_eine_anders_formulierte_ueberschrift_wird_ebenfalls_abgeschnitten(self):
        caller = _caller(["### Ganz anders gesagt\n\nText B"])
        text = await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="B", scope="b"),
            others=[], written=[], facts="F", part_note="")
        assert text == "Text B"

    async def test_eine_zwischenueberschrift_bleibt_stehen(self):
        caller = _caller(["Text B\n\n## Unterpunkt\n\nmehr Text"])
        text = await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="B", scope="b"),
            others=[], written=[], facts="F", part_note="")
        assert text == "Text B\n\n## Unterpunkt\n\nmehr Text"

    async def test_nur_eine_ueberschrift_gilt_als_leere_antwort(self):
        caller = _caller(["## B"])
        with pytest.raises(RuntimeError):
            await wr.write_section(
                caller, language="German", template_body="B", section=Section(title="B", scope="b"),
                others=[], written=[], facts="F", part_note="")

    async def test_der_einzelaufruf_schreibt_alles_auf_einmal(self):
        caller = _caller(["Alles."])
        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["q1 (a.pdf)", "q2 (b.pdf)"], facts="F", part_note="")
        assert text == "Alles."
        assert "ONE document covering all of them" in caller.client.user_prompts()[0]

    async def test_wenn_die_ueberschriften_allein_die_reserve_sprengen_bleibt_keine_prosa(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_PROMPT_RESERVE_CHARS", 200)
        caller = _caller(["Text Z"])
        written = [(f"Kapitel{i:02d}", "y" * 50) for i in range(20)]
        await wr.write_section(
            caller, language="German", template_body="B", section=Section(title="Z", scope="z"),
            others=[], written=written, facts="F", part_note="")
        user = caller.client.user_prompts()[0]
        praefix, suffix = "THE DOCUMENT SO FAR:\n", "\n\nFacts:\n\n"
        anfang = user.index(praefix) + len(praefix)
        bisher = user[anfang:user.index(suffix, anfang)]
        koepfe = "\n".join(f"## {titel}" for titel, _ in written)
        assert len(koepfe) > 200
        assert bisher == f"{koepfe}\n\n[...]\n"


class TestZusammensetzen:
    def test_mit_ueberschriften(self):
        assert wr.assemble("Vorweg.", ["A", "B"], ["ta", "tb"], True) == \
            "Vorweg.\n\n## A\n\nta\n\n## B\n\ntb"

    def test_ohne_ueberschriften_laeuft_die_prosa_durch(self):
        assert wr.assemble("", ["A", "B"], ["ta", "tb"], False) == "ta\n\ntb"

    def test_leere_abschnitte_fallen_weg(self):
        assert wr.assemble("", ["A", "B"], ["", "tb"], True) == "## B\n\ntb"
