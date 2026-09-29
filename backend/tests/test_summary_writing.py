"""Planning follows the material, writing follows the plan, both follow the build plan."""

import json

import pytest
from tests.summary_helpers import FakeClient

from src.features.summary import writing as wr
from src.features.summary.models import Caller, Section
from src.limits import SUMMARY_MAX_SECTIONS, SUMMARY_MIN_SECTIONS

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a"},
    {"title": "B", "description": "b"},
    {"title": "C", "description": "c"}]})



def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


async def _plane(caller, **kwargs):
    return await wr.plan_outline(caller, **{
        "language": "German", "template_body": "BAUPLAN", "sources": ["a.pdf"],
        "material": "#1 A", "target": 12, **kwargs})


async def _schreibe(caller, **kwargs):
    """Ein einzelner Abschnitt, also eine Gruppe von einem, wie der Aufrufer sie schickt."""
    abschnitt = kwargs.pop("section", Section(title="B", scope="b"))
    stoff = kwargs.pop("material", "Aussage 1")
    texte = await wr.write_sections(caller, **{
        "language": "German", "template_body": "B", "group": [abschnitt],
        "others": [], "written": [], "material": [stoff], "budget": 10_000, **kwargs})
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
    async def test_der_planer_bekommt_vorlage_richtwert_und_das_feste_schema(self):
        caller = _caller([_PLAN])
        plan = await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "BAUPLAN" in system and "around 12 sections" in system
        assert caller.client.optionen[0]["response_format"] is wr.OUTLINE_SCHEMA
        assert len(plan.sections) == 3

    async def test_die_gliederung_hat_eine_laengengrenze(self):
        """Lasttests 29.09.: 2 bis 3 von 20 Gliederungen liefen bis zur Zeitgrenze von 270 s, normale brauchen 12 bis 30 s."""
        from src.limits import SUMMARY_OUTLINE_MAX_TOKENS

        caller = _caller([_PLAN])
        await _plane(caller)
        assert caller.client.optionen[0]["max_tokens"] == SUMMARY_OUTLINE_MAX_TOKENS

    async def test_der_planer_plant_ueberschriften_und_teilt_die_stellen_zu(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "headings AND which numbers go" in system
        assert "names the numbers it rests on under refs" in system

    def _plan_mit(self, *nummern_je_abschnitt):
        import json
        return json.dumps({"title": "T", "intro": "I", "sections": [
            {"section_index": i, "title": f"A{i}", "description": "a", "refs": n}
            for i, n in enumerate(nummern_je_abschnitt)]})

    async def test_die_gliederung_bringt_ihre_stellen_mit(self):
        from src.services.text_map import _nummern
        ergebnis = await _plane(_caller([self._plan_mit(["1", "3"], ["2"], ["4-5"])]),
                                stellen=lambda refs: _nummern(refs, 10))
        assert [a.stellen for a in ergebnis.sections] == [[1, 3], [2], [4, 5]]

    async def test_eine_nummer_die_keine_ist_faellt_weg(self):
        from src.services.text_map import _nummern
        ergebnis = await _plane(_caller([self._plan_mit(["1", "x", "1"], ["2"], ["3"])]),
                                stellen=lambda refs: _nummern(refs, 10))
        assert ergebnis.sections[0].stellen == [1]

    async def test_die_abschnitte_folgen_dem_thema_nicht_der_datei(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        assert "never the file the material came from" in caller.client.system_prompts()[0]

    async def test_jede_quelle_muss_vorkommen(self):
        caller = _caller([_PLAN])
        await _plane(caller, sources=["a.pdf", "b.pdf"])
        system = caller.client.system_prompts()[0]
        assert "2 file(s)" in system and "EVERY one of them must be covered" in system

    async def test_die_einleitung_ordnet_ein_und_nennt_dann_die_zahlen(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        system = caller.client.system_prompts()[0]
        assert "first sentence says what the material covers" in system
        assert "never say what the reader will receive" in system.casefold()

    async def test_der_planer_benennt_das_dokument(self):
        caller = _caller([json.dumps({"title": "Pflichten im Arzneimittelrecht",
                                      "intro": "Vorweg.",
                                      "sections": [{"title": "A", "description": "a"},
                                                   {"title": "B", "description": "b"},
                                                   {"title": "C", "description": "c"}]})])
        plan = await _plane(caller)
        assert plan.title == "Pflichten im Arzneimittelrecht"
        assert "The title names what the material is about" in caller.client.system_prompts()[0]

    async def test_eine_unlesbare_gliederung_wird_einmal_wiederholt(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", _PLAN])
        plan = await _plane(caller)
        assert len(plan.sections) == 3
        assert [o.get("name") for o in caller.client.optionen][:2] == ["outline:1", "outline:2"]

    async def test_eine_lesbare_gliederung_wird_nicht_wiederholt(self):
        caller = _caller([_PLAN])
        await _plane(caller)
        assert [o.get("name") for o in caller.client.optionen].count("outline:2") == 0

    async def test_zwei_unlesbare_antworten_geben_eine_leere_gliederung(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller(["nix", "wieder nix"])
        plan = await _plane(caller)
        assert plan.sections == []
        assert len(caller.client.gesendet) == 2


class TestPlanOhneStellen:
    """Ein Plan, der keine einzige Stelle nennt, liesse die Schreiber aus dem Nichts schreiben."""

    _OHNE = json.dumps({"title": "T", "intro": "I", "sections": [
        {"title": t, "description": "d", "refs": []} for t in "ABC"]})
    _MIT = json.dumps({"title": "T", "intro": "I", "sections": [
        {"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})

    async def test_ein_plan_ohne_stellen_wird_wiederholt(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([self._OHNE, self._MIT])
        plan = await _plane(caller, stellen=lambda refs: [int(r) for r in refs])
        assert [a.stellen for a in plan.sections] == [[1], [1], [1]]

    async def test_bleibt_er_ohne_stellen_gibt_es_keine_gliederung(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([self._OHNE, self._OHNE])
        plan = await _plane(caller, stellen=lambda refs: [int(r) for r in refs])
        assert plan.sections == []


class TestSchreiben:
    async def test_ein_abschnitt_sieht_die_vorigen_und_meidet_die_kommenden(self):
        caller = _caller(["Text B"])
        text = await _schreibe(caller, others=[Section(title="C", scope="c")],
                               written=[("A", "Text A")])
        user = caller.client.user_prompts()[0]
        assert text == "Text B"
        assert "YOUR HEADING: B" in user and "## A\nText A" in user and "- C: c" in user

    async def test_der_dateiname_kommt_im_text_nicht_vor(self):
        """NotebookLM zeigt im Briefing keine Quellen, und je Zeile eine Datei liest schlechter."""
        caller = _caller(["Text B"])
        await _schreibe(caller, material="Aussage aus AMG74")
        system = caller.client.system_prompts()[0]
        assert "AMG74.pdf" not in system and "AMG74.pdf" not in caller.client.user_prompts()[0]
        assert "never write a file name into your text" in system

    async def test_doppelte_aussagen_werden_zu_einer(self):
        caller = _caller(["Text B"])
        await _schreibe(caller)
        system = caller.client.system_prompts()[0]
        assert "become ONE statement" in system
        assert "Use everything that belongs under your heading" in system

    async def test_schreibaufrufe_sind_gedeckelt_und_verlieren_nur_die_halbe_zeile(self):
        from src.limits import SUMMARY_WRITE_MAX_TOKENS
        caller = _caller([("Zeile eins.\nZeile zwei.\nZeile dr", "length")])
        text = await _schreibe(caller)
        assert text == "Zeile eins.\nZeile zwei."
        assert caller.client.optionen[0]["max_tokens"] == SUMMARY_WRITE_MAX_TOKENS

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
            others=[], written=[], material=["A"], budget=10_000) is None

    async def test_der_einzelaufruf_schreibt_alles_auf_einmal(self):
        caller = _caller(["Alles."])
        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["a.pdf", "b.pdf"], material="#1 A")
        assert text == "Alles."
        assert "ONE document covering all sources" in caller.client.system_prompts()[0]

    async def test_der_einzelaufruf_wird_nach_einem_fehlschlag_wiederholt(self, monkeypatch):
        """Die Fakten stehen schon auf der Platte, ein einzelner Aussetzer darf sie nicht kosten."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([RuntimeError("Zeitgrenze"), "Alles."])

        text = await wr.compose_single(caller, language="German", template_body="B",
                                       sources=["a.pdf"], material="#1 A")

        assert text == "Alles."
        assert len(caller.client.gesendet) == 2

    async def test_der_einzelaufruf_gibt_den_fehler_weiter_wenn_auch_der_zweite_scheitert(
            self, monkeypatch):
        """Nach dem letzten Versuch scheitert die Etappe sichtbar, der Wiederanlauf holt sie."""
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        caller = _caller([RuntimeError("Zeitgrenze"), RuntimeError("Zeitgrenze")])

        with pytest.raises(RuntimeError):
            await wr.compose_single(caller, language="German", template_body="B",
                                    sources=["a.pdf"], material="#1 A")

        assert len(caller.client.gesendet) == 2

    async def test_wenn_die_ueberschriften_allein_die_reserve_sprengen_bleibt_keine_prosa(self, monkeypatch):
        monkeypatch.setattr(wr, "SUMMARY_PROMPT_RESERVE_CHARS", 200)
        caller = _caller(["Text Z"])
        written = [(f"Kapitel{i:02d}", "y" * 50) for i in range(20)]
        await _schreibe(caller, section=Section(title="Z", scope="z"), written=written)
        user = caller.client.user_prompts()[0]
        praefix, suffix = "THE DOCUMENT SO FAR:\n", "\n\nYOUR MATERIAL:\n\n"
        anfang = user.index(praefix) + len(praefix)
        bisher = user[anfang:user.index(suffix, anfang)]
        koepfe = "\n".join(f"## {titel}" for titel, _ in written)
        assert len(koepfe) > 200
        assert bisher == f"{koepfe}\n\n[...]\n"


class TestGruppieren:
    """Kleine Abschnitte kosten je einen Aufruf und nutzen davon einen Bruchteil."""

    def _abschnitte(self, *groessen: int) -> tuple[list[Section], list[int]]:
        """Abschnitte und was ihr Text kosten soll, so wie der Aufrufer es rechnet."""
        return ([Section(title=f"S{i}") for i, _ in enumerate(groessen)],
                [600 + n * 160 for n in groessen])

    def test_kleine_abschnitte_teilen_einen_aufruf(self):
        assert wr.group_sections(*self._abschnitte(1, 1, 1, 1), budget=9_000) == [[0, 1, 2, 3]]

    def test_grosse_abschnitte_gehen_allein(self):
        assert wr.group_sections(*self._abschnitte(30, 30), budget=9_000) == [[0], [1]]

    def test_gruppen_bleiben_benachbart_und_in_reihenfolge(self):
        gruppen = wr.group_sections(*self._abschnitte(1, 1, 50, 1, 1), budget=9_000)
        assert gruppen == [[0, 1], [2], [3, 4]]
        assert [i for g in gruppen for i in g] == [0, 1, 2, 3, 4]

    def test_ein_zu_grosser_abschnitt_bekommt_trotzdem_seinen_aufruf(self):
        assert wr.group_sections(*self._abschnitte(500), budget=9_000) == [[0]]

    def test_ohne_abschnitte_gibt_es_keine_gruppe(self):
        assert wr.group_sections([], []) == []


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
            others=[], written=[], material=["A", "B"], budget=10_000)
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
            others=[], written=[], material=["A", "B"], budget=10_000)
        user = caller.client.user_prompts()[0]
        assert user.index("THE DOCUMENT SO FAR") < user.index("YOUR SECTIONS")

    async def test_ein_unteilbarer_gruppentext_gibt_none(self):
        caller = _caller(["Ein Klumpen ohne Ueberschriften."])
        texte = await wr.write_sections(
            caller, language="German", template_body="B",
            group=[Section(title="A", scope="a"), Section(title="B", scope="b")],
            others=[], written=[], material=["A", "B"], budget=10_000)
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


class TestKurznamen:
    """Jedes Dokument bekommt einen Kurznamen, den alle Schreiber benutzen, nie den Dateinamen."""

    def test_der_plan_liefert_die_kurznamen_der_dokumente(self):
        roh = json.dumps({"title": "T", "intro": "I", "documents": [
            {"file": "HwO79.pdf", "short_name": "HwO"}, {"file": "fremd.pdf", "short_name": "X"}],
            "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
        plan = wr.parse_outline(roh, dateien=["HwO79.pdf", "AGG13.pdf"])
        assert plan.names == {"HwO79.pdf": "HwO"}

    def test_ein_kurzname_der_wie_die_datei_heisst_zaehlt_nicht(self):
        roh = json.dumps({"title": "T", "intro": "I", "documents": [
            {"file": "HwO79.pdf", "short_name": "HwO79.pdf"}],
            "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
        assert wr.parse_outline(roh, dateien=["HwO79.pdf"]).names == {}

    def test_die_datei_wird_auch_ohne_endung_und_gross_klein_erkannt(self):
        roh = json.dumps({"title": "T", "intro": "I", "documents": [
            {"file": "hwo79", "short_name": "HwO"}],
            "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
        assert wr.parse_outline(roh, dateien=["HwO79.pdf"]).names == {"HwO79.pdf": "HwO"}

    def test_ohne_erkennbare_datei_gilt_die_reihenfolge(self):
        roh = json.dumps({"title": "T", "intro": "I", "documents": [
            {"file": "HwO", "short_name": "HwO"}, {"file": "AGG", "short_name": "AGG"}],
            "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
        plan = wr.parse_outline(roh, dateien=["HwO79.pdf", "AGG13.pdf"])
        assert plan.names == {"HwO79.pdf": "HwO", "AGG13.pdf": "AGG"}

    def test_ein_kurzname_wie_der_dateistamm_zaehlt_nicht(self):
        roh = json.dumps({"title": "T", "intro": "I", "documents": [
            {"file": "HwO79.pdf", "short_name": "HwO79"}],
            "sections": [{"title": t, "description": "d", "refs": ["1"]} for t in "ABC"]})
        assert wr.parse_outline(roh, dateien=["HwO79.pdf"]).names == {}

    def test_der_planer_sieht_den_anfang_jeder_datei(self):
        user = wr._outline_user(["a.pdf"], "MAT", anfaenge=["Gesetz zur Ordnung des Handwerks"])
        assert "Gesetz zur Ordnung des Handwerks" in user.split("MATERIAL:")[0]

    def test_der_schreiber_bekommt_die_kurznamen(self):
        user = wr._section_user([Section(title="A", scope="a")], [], None, ["x"],
                                names={"HwO79.pdf": "HwO"})
        assert "HwO79.pdf = HwO" in user


def test_der_schreiber_liest_die_seite_nie_als_paragraf():
    system = wr._section_system("German", "Plan", 2)
    assert "page number is never the number of a paragraph" in system
