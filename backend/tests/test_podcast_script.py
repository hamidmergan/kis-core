"""The model answer for a podcast: what counts as usable and what does not."""

import json

import pytest

from src.features.podcast.schemas import Line, Person, PodcastParams
from src.features.podcast.script import (
    ScriptUnusable,
    build_messages,
    clean_rephrased,
    parse_answer,
    refine_messages,
    rephrase_messages,
    source_excerpt,
)


def _params(n=2, sprache="de", **kw):
    rollen = ["host", "expert", "student", "critic"]
    personen = [Person(name=f"P{i + 1}", role=rollen[i], voice_id=f"v{i}") for i in range(n)]
    return PodcastParams(language=sprache, persons=personen, **kw)


def _antwort(paare):
    return json.dumps({"lines": [{"speaker": s, "text": t} for s, t in paare]})


class TestAntwortLesen:
    def test_nimmt_die_beitraege_mit_sprecher(self):
        zeilen = parse_answer(_antwort([(0, "Hallo."), (1, "Guten Tag.")]), 2)
        assert [z.speaker for z in zeilen] == [0, 1]
        assert zeilen[0].text == "Hallo."

    def test_findet_das_json_auch_zwischen_geschwaetz(self):
        roh = "Gerne! Hier das Skript:\n```json\n" + _antwort([(0, "Eins."), (1, "Zwei.")]) + "\n```\nViel Erfolg!"
        assert len(parse_answer(roh, 2)) == 2

    def test_holt_einen_sprecher_ausserhalb_der_besetzung_zurueck(self):
        # Ein verirrter Index darf das Gespraech nicht auf eine Stimme zusammenfallen lassen.
        zeilen = parse_answer(_antwort([(0, "Eins."), (9, "Zwei.")]), 2)
        assert zeilen[1].speaker == 1
        assert parse_answer(_antwort([(0, "Eins."), (5, "Zwei."), (2, "Drei.")]), 3)[1].speaker == 2

    def test_wirft_bei_kaputtem_json(self):
        with pytest.raises(ScriptUnusable):
            parse_answer("das ist kein json", 2)

    def test_wirft_ohne_beitraege(self):
        with pytest.raises(ScriptUnusable):
            parse_answer(json.dumps({"lines": []}), 2)

    def test_wirft_bei_nur_einem_brauchbaren_beitrag(self):
        with pytest.raises(ScriptUnusable):
            parse_answer(_antwort([(0, "Allein."), (1, "   ")]), 2)

    def test_wirft_wenn_bei_zwei_personen_nur_eine_spricht(self):
        with pytest.raises(ScriptUnusable, match="eine Person"):
            parse_answer(_antwort([(0, "Eins."), (0, "Zwei.")]), 2)

    def test_laesst_eine_person_allein_sprechen(self):
        zeilen = parse_answer(_antwort([(0, "Eins."), (0, "Zwei.")]), 1)
        assert len(zeilen) == 2

    def test_kuerzt_einen_masslosen_beitrag(self):
        from src.limits import PODCAST_MAX_LINE_CHARS

        zeilen = parse_answer(_antwort([(0, "a" * 5000), (1, "Kurz.")]), 2)
        assert len(zeilen[0].text) == PODCAST_MAX_LINE_CHARS

    def test_deckelt_die_zahl_der_beitraege(self):
        from src.limits import PODCAST_MAX_LINES

        viele = [(i % 2, f"Satz {i}.") for i in range(PODCAST_MAX_LINES + 20)]
        assert len(parse_answer(_antwort(viele), 2)) == PODCAST_MAX_LINES


class TestPrompt:
    def test_nennt_die_besetzung_mit_nummer_und_rolle(self):
        text = build_messages("Material", _params(3))[1]["content"]
        assert "0: P1" in text and "1: P2" in text and "2: P3" in text

    def test_verbietet_den_wechsel_nicht_wenn_nur_einer_spricht(self):
        allein = build_messages("Material", _params(1))[1]["content"]
        assert "speaker ist immer 0" in allein
        zwei = build_messages("Material", _params(2))[1]["content"]
        assert "wechseln sich ab" in zwei

    def test_folgt_der_sprache_des_podcasts(self):
        assert "English" in build_messages("Material", _params(2, sprache="en"))[1]["content"]

    def test_nimmt_die_anweisung_mit(self):
        text = build_messages("M", _params(2, instructions="Bleib bei den Grundlagen"))[1]["content"]
        assert "Bleib bei den Grundlagen" in text

    def test_nennt_eine_beitragszahl_statt_nur_einer_gesamtsumme(self):
        from src.features.podcast.schemas import LENGTH_PLAN

        for name, (anzahl, je) in LENGTH_PLAN.items():
            text = build_messages("M", _params(2, length=name))[1]["content"]
            assert f"{anzahl} Beitr" in text, name
            assert str(je) in text, name

    def test_zielumfang_haengt_an_der_laenge(self):
        kurz = build_messages("M", _params(2, length="short"))[1]["content"]
        lang = build_messages("M", _params(2, length="long"))[1]["content"]
        assert "700" in kurz and "2800" in lang

    def test_englischer_auftrag_nennt_die_beitragszahl_auch(self):
        from src.features.podcast.schemas import LENGTH_PLAN

        anzahl, je = LENGTH_PLAN["medium"]
        text = build_messages("M", _params(2, sprache="en", length="medium"))[1]["content"]
        assert f"{anzahl} contributions" in text and str(je) in text

    def test_keine_laenge_sprengt_den_deckel_der_beitraege(self):
        from src.features.podcast.schemas import LENGTH_PLAN
        from src.limits import PODCAST_MAX_LINES

        assert all(anzahl <= PODCAST_MAX_LINES for anzahl, _ in LENGTH_PLAN.values())


class TestUmformulieren:
    def test_zeigt_dem_modell_das_umfeld(self):
        text = rephrase_messages(Line(id="b1", speaker=0, text="Der Satz."),
                                 _params(2), ["Davor.", "Danach."])[1]["content"]
        assert "Davor." in text and "Danach." in text and "Der Satz." in text

    def test_schaelt_die_namensnennung_ab(self):
        assert clean_rephrased("Lena: Der neue Satz.", "alt") == "Der neue Satz."

    def test_laesst_einen_doppelpunkt_im_satz_stehen(self):
        satz = "Es gilt der Merksatz: Spannung ist Widerstand mal Strom."
        assert clean_rephrased(satz, "alt") == satz

    def test_faellt_bei_leerer_antwort_auf_den_alten_text_zurueck(self):
        assert clean_rephrased("   ", "der alte Satz") == "der alte Satz"

    def test_schaelt_die_json_huelle_ab(self):
        assert clean_rephrased('{"text": "Der neue Satz." }', "alt") == "Der neue Satz."

    def test_nimmt_auch_einen_codeblock_um_das_json(self):
        roh = '```json\n{"text": "Der neue Satz."}\n```'
        assert clean_rephrased(roh, "alt") == "Der neue Satz."

    def test_verlangt_die_json_huelle_im_auftrag(self):
        nachricht = rephrase_messages(Line(id="b1", speaker=0, text="Der Satz."), _params(2), [])
        assert '{"text"' in nachricht[0]["content"]


class TestQuellenAusschnitt:
    QUELLE = (
        "Kapitel eins: Einleitung in die Veranstaltung und ihre Ziele.\n\n"
        "Das ohmsche Gesetz verbindet Spannung, Widerstand und Stromstaerke.\n\n"
        "Zur Anmeldung nutzen Studierende das Portal der Hochschule.\n\n"
        "Die Spannung wird in Volt gemessen, der Widerstand in Ohm.\n"
    )

    def test_waehlt_den_absatz_mit_den_passenden_woertern(self):
        text = source_excerpt(self.QUELLE, ["Wie hoch ist die Spannung am Widerstand?"], 200)
        assert "Volt" in text or "ohmsche" in text
        assert "Portal der Hochschule" not in text

    def test_haelt_die_zeichengrenze_ein(self):
        text = source_excerpt(self.QUELLE, ["Spannung"], 80)
        assert len(text) <= 80

    def test_nimmt_den_anfang_wenn_nichts_passt(self):
        text = source_excerpt(self.QUELLE, ["Photosynthese"], 120)
        assert text.startswith("Kapitel eins")

    def test_behaelt_die_reihenfolge_der_absaetze(self):
        text = source_excerpt(self.QUELLE, ["Spannung Widerstand ohmsche Volt"], 400)
        assert text.index("ohmsche") < text.index("Volt")

    def test_bleibt_bei_leerem_material_leer(self):
        assert source_excerpt("", ["Spannung"], 200) == ""


class TestChatUmformulieren:
    def _nachricht(self, **kw):
        daten = dict(
            line=Line(id="b1", speaker=0, text="Der Satz."),
            params=_params(2),
            nachbarn=["Davor.", "Danach."],
            quelle="Die Spannung wird in Volt gemessen.",
            verlauf=[{"role": "user", "content": "Mach ihn kuerzer"}],
        )
        daten.update(kw)
        return refine_messages(**daten)

    def test_nennt_den_wunsch_und_das_material(self):
        text = self._nachricht()[1]["content"]
        assert "Mach ihn kuerzer" in text
        assert "Volt" in text

    def test_bindet_die_fakten_an_das_material(self):
        system = self._nachricht()[0]["content"]
        assert "Material" in system and "erfindest nichts" in system

    def test_nennt_die_markierte_stelle(self):
        text = self._nachricht(markiert="in Volt")[1]["content"]
        assert "in Volt" in text

    def test_traegt_den_bisherigen_austausch_mit(self):
        verlauf = [
            {"role": "user", "content": "Mach ihn kuerzer"},
            {"role": "assistant", "content": "Der kurze Satz."},
            {"role": "user", "content": "Jetzt freundlicher"},
        ]
        text = self._nachricht(verlauf=verlauf)[1]["content"]
        assert "Der kurze Satz." in text and "Jetzt freundlicher" in text

    def test_verlangt_die_json_huelle(self):
        assert '{"text"' in self._nachricht()[0]["content"]

    def test_folgt_der_sprache_des_podcasts(self):
        system = self._nachricht(params=_params(2, sprache="en"))[0]["content"]
        assert "material" in system.lower() and "invent" in system.lower()


class TestLeererBeitrag:
    """Ein Beitrag ohne Text muss geschrieben werden, nicht überarbeitet."""

    def _nachricht(self, text="", **kw):
        daten = dict(
            line=Line(id="b1", speaker=0, text=text),
            params=_params(2),
            nachbarn=["P2: Danke, dass ich da sein darf."],
            quelle="Die Spannung wird in Volt gemessen.",
            verlauf=[{"role": "user", "content": "Begruess kurz und sag worum es geht"}],
        )
        daten.update(kw)
        return refine_messages(**daten)

    def test_sagt_dass_der_beitrag_noch_leer_ist(self):
        text = self._nachricht()[1]["content"]
        assert "noch leer" in text
        assert "steht zur Überarbeitung" not in text

    def test_verlangt_nur_diesen_einen_beitrag(self):
        text = self._nachricht()[1]["content"]
        assert "nicht die Antwort darauf" in text

    def test_nennt_die_stelle_im_gespraech(self):
        text = self._nachricht(position=(1, 20))[1]["content"]
        assert "Beitrag 1 von 20" in text

    def test_weist_den_ersten_beitrag_auf_die_begruessung_hin(self):
        assert "begrüßt" in self._nachricht(position=(1, 20))[1]["content"]

    def test_weist_den_letzten_beitrag_auf_den_abschied_hin(self):
        assert "verabschiedet" in self._nachricht(position=(20, 20))[1]["content"]

    def test_laesst_die_mitte_ohne_zusatzregel(self):
        text = self._nachricht(position=(10, 20))[1]["content"]
        assert "begrüßt" not in text and "verabschiedet" not in text

    def test_behaelt_den_gefuellten_beitrag_beim_ueberarbeiten(self):
        text = self._nachricht(text="Der Satz.")[1]["content"]
        assert "steht zur Überarbeitung" in text and "noch leer" not in text

    def test_englisch_sagt_es_genauso(self):
        text = self._nachricht(params=_params(2, sprache="en"), position=(1, 20))[1]["content"]
        assert "still empty" in text and "contribution 1 of 20" in text.lower()


# ── Eine lange Folge in Teilen ───────────────────────────────────────────────

class TestTeile:
    def test_die_beitraege_werden_gleichmaessig_verteilt(self):
        from src.features.podcast.script import teil_laengen
        assert teil_laengen(40, 3) == [14, 13, 13]
        assert teil_laengen(20, 2) == [10, 10]
        assert teil_laengen(10, 1) == [10]

    def test_nie_mehr_teile_als_beitraege(self):
        from src.features.podcast.script import teil_laengen
        assert teil_laengen(2, 5) == [1, 1]

    def test_nur_der_erste_teil_begruesst_und_nur_der_letzte_verabschiedet(self):
        erster = build_messages("M", _params(), anzahl=14, teil=1, teile=3, plan="1. A")
        mitte = build_messages("M", _params(), anzahl=13, teil=2, teile=3, plan="1. A")
        letzter = build_messages("M", _params(), anzahl=13, teil=3, teile=3, plan="1. A")
        assert "begrüßt" in erster[1]["content"] and "keine Verabschiedung" in erster[1]["content"]
        assert "keine Begrüßung und keine Verabschiedung" in mitte[1]["content"]
        assert "Der letzte Beitrag verabschiedet" in letzter[1]["content"]

    def test_ein_teil_kennt_den_plan_und_das_zuletzt_gesagte(self):
        bisher = [Line(speaker=0, text="Willkommen zur Folge."), Line(speaker=1, text="Danke.")]
        user = build_messages("M", _params(), anzahl=13, teil=2, teile=3,
                              plan="1. Zulassung\n2. Haftung", bisher=bisher)[1]["content"]
        assert "Teil 2 von 3" in user and "2. Haftung" in user
        assert "P1: Willkommen zur Folge." in user and "P2: Danke." in user
        assert "genau 13 Beiträge" in user

    def test_eine_folge_in_einem_teil_bleibt_wie_bisher(self):
        user = build_messages("M", _params(length="short"))[1]["content"]
        assert "Teil 1 von" not in user
        assert "genau 10 Beiträge" in user


class TestPlan:
    def _antwort(self, *teile):
        return json.dumps({"parts": [{"title": t, "gist": "g", "refs": r} for t, r in teile]})

    def test_teile_mit_ihren_stellen(self):
        from src.features.podcast.script import parse_plan
        plan = parse_plan(self._antwort(("A", [1, 2]), ("B", [5])),
                          lambda refs: [int(r) for r in refs], 2)
        assert [(p["title"], p["stellen"]) for p in plan] == [("A", [1, 2]), ("B", [5])]

    def test_zu_viele_teile_gehen_im_letzten_auf(self):
        from src.features.podcast.script import parse_plan
        plan = parse_plan(self._antwort(("A", [1]), ("B", [2]), ("C", [3, 2])),
                          lambda refs: [int(r) for r in refs], 2)
        assert [p["stellen"] for p in plan] == [[1], [2, 3]]

    def test_ein_teil_ohne_stellen_faellt_weg(self):
        from src.features.podcast.script import parse_plan
        plan = parse_plan(self._antwort(("A", []), ("B", [4])), lambda refs: list(refs), 2)
        assert [p["title"] for p in plan] == ["B"]

    def test_ein_plan_ohne_teile_ist_unbrauchbar(self):
        from src.features.podcast.script import parse_plan
        with pytest.raises(ScriptUnusable):
            parse_plan("kein json", lambda refs: [], 2)

    def test_der_planauftrag_nennt_die_zahl_der_teile_und_die_nummern(self):
        from src.features.podcast.script import plan_messages
        system = plan_messages("[1] Text", "stellen", _params(), 3)[0]["content"]
        assert "exactly 3 consecutive parts" in system and "numbered passages" in system
