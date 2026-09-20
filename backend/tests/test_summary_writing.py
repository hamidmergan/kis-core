"""Planning follows the material, writing follows the plan, both follow the build plan."""

import json

import pytest
from tests.summary_helpers import FakeClient

from src.features.summary import writing as wr
from src.services.facts.pool import Fact
from src.features.summary.models import Caller, Section
from src.limits import SUMMARY_MAX_SECTIONS, SUMMARY_MIN_SECTIONS

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a"},
    {"title": "B", "description": "b"},
    {"title": "C", "description": "c"}]})


def _zuordnung(paare: dict[int, int]) -> str:
    return json.dumps({"assignments": [{"fact_id": f, "section_index": i}
                                       for f, i in paare.items()]})


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
    """Ein einzelner Abschnitt, also eine Gruppe von einem, wie die Pipeline sie schickt."""
    abschnitt = kwargs.pop("section", Section(title="B", scope="b"))
    fakten = kwargs.pop("facts", _vorrat(1))
    texte = await wr.write_sections(caller, **{
        "language": "German", "template_body": "B", "group": [abschnitt],
        "others": [], "written": [], "facts": [fakten], "budget": 10_000, **kwargs})
    return texte[0] if texte else ""


class TestRichtwert:
    def test_wenig_stoff_gibt_die_untergrenze(self):
        assert wr.target_sections(1_000) == SUMMARY_MIN_SECTIONS

    def test_der_richtwert_waechst_mit_dem_stoff(self):
        assert wr.target_sections(48_000) == 12
        assert wr.target_sections(80_000) == 20

    def test_die_obergrenze_haelt(self):
        assert wr.target_sections(10_000_000) == SUMMARY_MAX_SECTIONS

    def test_jede_quelle_bekommt_ihre_abschnitte(self):
        """Sechs fremde Dateien brauchen mehr Ueberschriften als ihr Umfang allein hergibt."""
        assert wr.target_sections(8_000, 6) == 12
        assert wr.target_sections(8_000, 1) == SUMMARY_MIN_SECTIONS

    def test_die_obergrenze_haelt_auch_gegen_viele_quellen(self):
        assert wr.target_sections(1_000, 50) == SUMMARY_MAX_SECTIONS


class TestGliederungLesen:
    def test_eine_saubere_antwort_wird_gelesen(self):
        plan = wr.parse_outline(_PLAN)
        assert plan.intro == "Vorweg."
        assert [s.title for s in plan.sections] == ["A", "B", "C"]
        assert plan.sections[0].scope == "a"

    def test_die_gliederung_bringt_noch_keine_fakten_mit(self):
        """Wer die Nummern hier schon verteilt, verliert das Ende des Vorrats."""
        assert [s.fact_ids for s in wr.parse_outline(_PLAN).sections] == [[], [], []]

    def test_mitgeschickte_nummern_werden_ignoriert(self):
        roh = json.dumps({"sections": [
            {"title": "A", "fact_ids": [1, 2]}, {"title": "B", "fact_ids": [2, 3]},
            {"title": "C", "fact_ids": [99]}]})
        assert [s.fact_ids for s in wr.parse_outline(roh).sections] == [[], [], []]

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


class TestAbdeckung:
    def _plan(self, *nummern: list[int]) -> wr.Outline:
        return wr.Outline(sections=[Section(title=f"S{i}", fact_ids=list(n))
                                    for i, n in enumerate(nummern)])

    def test_alles_zugeordnet_ist_voll(self):
        assert wr.coverage(self._plan([1], [2], [3]), _vorrat()) == 1.0

    def test_die_haelfte_zugeordnet_ist_die_haelfte(self):
        assert wr.coverage(self._plan([1], [2], [3]), _vorrat(6)) == 0.5

    def test_ein_leerer_vorrat_gilt_als_abgedeckt(self):
        assert wr.coverage(self._plan([1]), []) == 1.0


class TestPlanen:
    async def test_der_planer_bekommt_vorlage_richtwert_und_das_feste_schema(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        plan = await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "BAUPLAN" in system and "around 12 sections" in system
        assert caller.client.optionen[0]["response_format"] is wr.OUTLINE_SCHEMA
        assert len(plan.sections) == 3

    async def test_der_planer_plant_nur_ueberschriften(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        await _plane(caller)
        assert "headings only" in caller.client.system_prompts()[0]

    async def test_die_abschnitte_folgen_dem_thema_nicht_der_datei(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        await _plane(caller)
        assert "never the file a fact came from" in caller.client.system_prompts()[0]

    async def test_jede_quelle_muss_vorkommen(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        await _plane(caller, sources=["a.pdf", "b.pdf"])
        system = caller.client.system_prompts()[0]
        assert "2 file(s)" in system and "EVERY one of them must be covered" in system

    async def test_die_einleitung_ordnet_ein_und_nennt_dann_die_zahlen(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "first sentence says what the material covers" in system
        assert "never say what the reader will receive" in system.casefold()

    async def test_der_planer_benennt_das_dokument(self):
        caller = _caller([json.dumps({"title": "Pflichten im Arzneimittelrecht",
                                      "intro": "Vorweg.",
                                      "sections": [{"title": "A", "description": "a"},
                                                   {"title": "B", "description": "b"},
                                                   {"title": "C", "description": "c"}]}),
                          _zuordnung({1: 0, 2: 1, 3: 2})])
        plan = await _plane(caller)
        assert plan.title == "Pflichten im Arzneimittelrecht"
        assert "The title names what the material is about" in caller.client.system_prompts()[0]

    async def test_der_plan_wird_erst_geholt_dann_befuellt(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        plan = await _plane(caller)
        assert [o.get("name") for o in caller.client.optionen] == ["outline:1", "assign:1-3"]
        assert [s.fact_ids for s in plan.sections] == [[1], [2], [3]]

    async def test_eine_unlesbare_gliederung_wird_einmal_wiederholt(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", _PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        plan = await _plane(caller)
        assert len(plan.sections) == 3
        assert [o.get("name") for o in caller.client.optionen][:2] == ["outline:1", "outline:2"]

    async def test_eine_lesbare_gliederung_wird_nicht_wiederholt(self):
        caller = _caller([_PLAN, _zuordnung({1: 0, 2: 1, 3: 2})])
        await _plane(caller)
        assert [o.get("name") for o in caller.client.optionen].count("outline:2") == 0

    async def test_zwei_unlesbare_antworten_geben_eine_leere_gliederung(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", "wieder nix"])
        plan = await _plane(caller)
        assert plan.sections == []
        assert len(caller.client.gesendet) == 2


class TestZuordnung:
    def test_parse_liest_gueltige_zuordnungen(self):
        assert wr.parse_assignments(_zuordnung({1: 0, 2: 1}), {1, 2}, 2) == {1: 0, 2: 1}

    def test_unbekannter_fakt_und_ungueltiger_abschnitt_fallen_weg(self):
        roh = json.dumps({"assignments": [{"fact_id": 99, "section_index": 0},
                                          {"fact_id": 1, "section_index": 5}]})
        assert wr.parse_assignments(roh, {1}, 2) == {}

    def test_unlesbare_antwort_gibt_leere_zuordnung(self):
        assert wr.parse_assignments("nix", {1}, 2) == {}

    async def test_der_zuordner_nennt_die_bestehenden_abschnitte(self):
        caller = _caller([_zuordnung({})])
        sections = [Section(title="A", scope="erstens"), Section(title="B", scope="zweitens")]
        await wr.assign_batch(caller, language="German", sections=sections, facts=_vorrat(1))
        system = caller.client.system_prompts()[0]
        assert "0: A. erstens" in system and "1: B. zweitens" in system
        assert "Never invent a section" in system

    async def test_ein_grosser_vorrat_geht_in_stapeln_raus(self, monkeypatch):
        """187 Nummern in einer Antwort war die Ursache, also wird gestapelt."""
        monkeypatch.setattr(wr, "SUMMARY_ASSIGN_BATCH_FACTS", 2)
        outline = wr.Outline(sections=[Section(title="A"), Section(title="B")])
        caller = _caller([_zuordnung({1: 0, 2: 1}), _zuordnung({3: 0, 4: 1}),
                          _zuordnung({5: 0})])
        await wr.assign_pool(caller, language="German", outline=outline, pool=_vorrat(5))
        assert [o.get("name") for o in caller.client.optionen] == \
            ["assign:1-2", "assign:3-4", "assign:5-5"]
        assert [s.fact_ids for s in outline.sections] == [[1, 3, 5], [2, 4]]

    async def test_ein_gescheiterter_stapel_verliert_keinen_fakt(self):
        caller = _caller([RuntimeError("kaputt")])
        outline = wr.Outline(sections=[Section(title="A"), Section(title="B")])
        await wr.assign_pool(caller, language="German", outline=outline, pool=_vorrat(3))
        assert sorted(n for s in outline.sections for n in s.fact_ids) == [1, 2, 3]

    async def test_bereits_zugeordnete_fakten_werden_nicht_erneut_gefragt(self):
        caller = _caller([_zuordnung({2: 1})])
        outline = wr.Outline(sections=[Section(title="A", fact_ids=[1]), Section(title="B")])
        await wr.assign_pool(caller, language="German", outline=outline, pool=_vorrat(2))
        assert "Aussage 1" not in caller.client.user_prompts()[0]
        assert [s.fact_ids for s in outline.sections] == [[1], [2]]


class TestEinordnenNachWortlaut:
    def test_ein_fakt_geht_zum_passenden_abschnitt(self):
        """Umsatzsteuer darf nie im Bewacherregister landen, das war der Fehler."""
        sections = [Section(title="Bewacherregister", scope="Wachpersonen und Bewachung"),
                    Section(title="Umsatzsteuer", scope="Lieferungen und Entgelt")]
        fakt = Fact(1, "figure", "Der Umsatzsteuer unterliegen Lieferungen gegen Entgelt.",
                    "", "doc_06", "UStG98.pdf")
        wr.place_by_wording(sections, [fakt])
        assert [s.fact_ids for s in sections] == [[], [1]]

    def test_ohne_treffer_geht_es_zum_leersten_abschnitt(self):
        sections = [Section(title="A", scope="", fact_ids=[7, 8]), Section(title="B", scope="")]
        wr.place_by_wording(sections, _vorrat(1))
        assert [s.fact_ids for s in sections] == [[7, 8], [1]]

    def test_ohne_abschnitte_passiert_nichts(self):
        wr.place_by_wording([], _vorrat(1))


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

    async def test_der_dateiname_kommt_im_text_nicht_vor(self):
        """NotebookLM zeigt im Briefing keine Quellen, und je Zeile eine Datei liest schlechter."""
        caller = _caller(["Text B"])
        await _schreibe(caller, facts=_vorrat(1, "AMG74.pdf"))
        system = caller.client.system_prompts()[0]
        assert "AMG74.pdf" not in system and "AMG74.pdf" not in caller.client.user_prompts()[0]
        assert "never write a file name into your text" in system

    async def test_die_stelle_gehoert_in_den_satz(self):
        caller = _caller(["Text B"])
        fakt = Fact(1, "figure", "A", "Beleg A", "doc_01", "a.pdf", "§ 27 Abs. 3")
        await _schreibe(caller, facts=[fakt])
        assert "in square brackets at the end of the statement" in \
            caller.client.system_prompts()[0]
        assert "Stelle: § 27 Abs. 3" in caller.client.user_prompts()[0]

    async def test_doppelte_aussagen_werden_zu_einer(self):
        caller = _caller(["Text B"])
        await _schreibe(caller)
        system = caller.client.system_prompts()[0]
        assert "become ONE statement" in system
        assert "Every fact you are given appears in your section" in system

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
        """Nichts zurueck heisst None, die Pipeline macht daraus den Fehler."""
        caller = _caller(["## B"])
        assert await wr.write_sections(
            caller, language="German", template_body="B", group=[Section(title="B", scope="b")],
            others=[], written=[], facts=[_vorrat(1)], budget=10_000) is None

    async def test_der_einzelaufruf_schreibt_alles_auf_einmal(self):
        caller = _caller(["Alles."])
        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["a.pdf", "b.pdf"], pool=_vorrat(),
                                       pool_text="#1 A")
        assert text == "Alles."
        assert "ONE document covering all sources" in caller.client.system_prompts()[0]

    async def test_der_einzelaufruf_wird_nach_einem_fehlschlag_wiederholt(self, monkeypatch):
        """Die Fakten stehen schon auf der Platte, ein einzelner Aussetzer darf sie nicht kosten."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([RuntimeError("Zeitgrenze"), "Alles."])

        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["a.pdf"], pool=_vorrat(), pool_text="#1 A")

        assert text == "Alles."
        assert len(caller.client.gesendet) == 2

    async def test_der_einzelaufruf_gibt_den_fehler_weiter_wenn_auch_der_zweite_scheitert(
            self, monkeypatch):
        """Nach dem letzten Versuch scheitert die Etappe sichtbar, der Wiederanlauf holt sie."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([RuntimeError("Zeitgrenze"), RuntimeError("Zeitgrenze")])

        with pytest.raises(RuntimeError):
            await wr.compose_single(caller, language="German", template_body="B",
                                    sources=["a.pdf"], pool=_vorrat(), pool_text="#1 A")

        assert len(caller.client.gesendet) == 2

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


class TestGruppieren:
    """Kleine Abschnitte kosten je einen Aufruf und nutzen davon einen Bruchteil."""

    def _abschnitte(self, *fakten: int) -> list[Section]:
        return [Section(title=f"S{i}", fact_ids=list(range(1, n + 1)))
                for i, n in enumerate(fakten)]

    def test_der_richtwert_folgt_der_messung(self):
        assert wr.expected_chars(0) == 600
        assert wr.expected_chars(30) == 5_400

    def test_kleine_abschnitte_teilen_einen_aufruf(self):
        assert wr.group_sections(self._abschnitte(1, 1, 1, 1), budget=9_000) == [[0, 1, 2, 3]]

    def test_grosse_abschnitte_gehen_allein(self):
        assert wr.group_sections(self._abschnitte(30, 30), budget=9_000) == [[0], [1]]

    def test_gruppen_bleiben_benachbart_und_in_reihenfolge(self):
        gruppen = wr.group_sections(self._abschnitte(1, 1, 50, 1, 1), budget=9_000)
        assert gruppen == [[0, 1], [2], [3, 4]]
        assert [i for g in gruppen for i in g] == [0, 1, 2, 3, 4]

    def test_ein_zu_grosser_abschnitt_bekommt_trotzdem_seinen_aufruf(self):
        assert wr.group_sections(self._abschnitte(500), budget=9_000) == [[0]]

    def test_ohne_abschnitte_gibt_es_keine_gruppe(self):
        assert wr.group_sections([]) == []


class TestGruppeTrennen:
    """Ein falscher Schnitt wuerde Prosa unter die falsche Ueberschrift legen."""

    def test_ein_einzelner_abschnitt_braucht_keinen_schnitt(self):
        assert wr.split_group("  Nur Text.  ", ["A"]) == ["Nur Text."]

    def test_nach_den_ueberschriften_getrennt(self):
        roh = "## A\nText A\n\n## B\nText B"
        assert wr.split_group(roh, ["A", "B"]) == ["Text A", "Text B"]

    def test_eine_zwischenueberschrift_bleibt_beim_abschnitt(self):
        roh = "## A\nText A\n\n### Unterpunkt\nmehr\n\n## B\nText B"
        assert wr.split_group(roh, ["A", "B"])[0] == "Text A\n\n### Unterpunkt\nmehr"

    def test_ohne_ueberschriften_wird_nicht_geraten(self):
        assert wr.split_group("Text A Text B", ["A", "B"]) is None

    def test_eine_fehlende_ueberschrift_wird_nicht_geraten(self):
        assert wr.split_group("## A\nText A", ["A", "B"]) is None

    def test_bei_passender_anzahl_entscheidet_die_stellung(self):
        roh = "## Anders benannt\nText A\n\n## Auch anders\nText B"
        assert wr.split_group(roh, ["A", "B"]) == ["Text A", "Text B"]

    def test_ein_leerer_abschnitt_gilt_als_misslungen(self):
        assert wr.split_group("## A\n\n## B\nText B", ["A", "B"]) is None


class TestGruppeSchreiben:
    async def test_eine_gruppe_geht_in_einen_aufruf(self):
        caller = _caller(["## A\nText A\n\n## B\nText B"])
        texte = await wr.write_sections(
            caller, language="German", template_body="B",
            group=[Section(title="A", scope="a"), Section(title="B", scope="b")],
            others=[], written=[], facts=[_vorrat(1), _vorrat(2)], budget=10_000)
        assert texte == ["Text A", "Text B"]
        assert len(caller.client.gesendet) == 1
        system = caller.client.system_prompts()[0]
        assert "2 CONSECUTIVE sections" in system
        user = caller.client.user_prompts()[0]
        assert "=== SECTION 1 OF 2 ===" in user and "HEADING: B" in user

    async def test_die_fakten_stehen_am_ende_der_anweisung(self):
        caller = _caller(["## A\nText A\n\n## B\nText B"])
        await wr.write_sections(
            caller, language="German", template_body="B",
            group=[Section(title="A", scope="a"), Section(title="B", scope="b")],
            others=[], written=[], facts=[_vorrat(1), _vorrat(2)], budget=10_000)
        user = caller.client.user_prompts()[0]
        assert user.index("THE DOCUMENT SO FAR") < user.index("YOUR SECTIONS")

    async def test_ein_unteilbarer_gruppentext_gibt_none(self):
        caller = _caller(["Ein Klumpen ohne Ueberschriften."])
        texte = await wr.write_sections(
            caller, language="German", template_body="B",
            group=[Section(title="A", scope="a"), Section(title="B", scope="b")],
            others=[], written=[], facts=[_vorrat(1), _vorrat(1)], budget=10_000)
        assert texte is None


class TestZusammensetzen:
    def test_mit_ueberschriften(self):
        assert wr.assemble("Vorweg.", ["A", "B"], ["ta", "tb"], True) == \
            "Vorweg.\n\n## A\n\nta\n\n## B\n\ntb"

    def test_ohne_ueberschriften_laeuft_die_prosa_durch(self):
        assert wr.assemble("", ["A", "B"], ["ta", "tb"], False) == "ta\n\ntb"

    def test_leere_abschnitte_fallen_weg(self):
        assert wr.assemble("", ["A", "B"], ["", "tb"], True) == "## B\n\ntb"

    def test_der_titel_steht_ganz_oben(self):
        assert wr.assemble("Vorweg.", ["A"], ["ta"], True, title="Mein Thema") == \
            "# Mein Thema\n\nVorweg.\n\n## A\n\nta"

    def test_ein_durchlaufender_text_bekommt_keinen_titel(self):
        """Verbietet ein Bauplan Ueberschriften, dann auch die erste Ebene."""
        assert wr.assemble("", ["A"], ["ta"], False, title="Mein Thema") == "ta"


class TestTitelAbtrennen:
    def test_der_titel_wird_abgetrennt(self):
        assert wr.split_title("# Mein Thema\n\nVorweg.\n\n## A\n\nta") == \
            ("Mein Thema", "Vorweg.\n\n## A\n\nta")

    def test_ohne_titel_bleibt_der_text_wie_er_ist(self):
        assert wr.split_title("Vorweg.\n\n## A") == ("", "Vorweg.\n\n## A")

    def test_eine_abschnittsueberschrift_ist_kein_titel(self):
        assert wr.split_title("## A\n\nta") == ("", "## A\n\nta")

    def test_ein_leerer_text_bleibt_leer(self):
        assert wr.split_title("") == ("", "")
