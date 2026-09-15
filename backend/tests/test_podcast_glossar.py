"""The glossary a podcast keeps fixed: what survives the sifting and what reaches the prompt."""

from src.features.podcast import glossary as glossar
from src.features.podcast.schemas import Line, Person, PodcastParams
from src.features.podcast.script import build_messages, rephrase_messages


def _params(**kw):
    personen = [Person(name="A", role="host", voice_id="v0", provider_id=1)]
    return PodcastParams(persons=personen, **kw)


class TestAussieben:
    def test_behaelt_nur_was_im_material_steht(self):
        eintraege = {"Aufwandsschätzung": "effort estimation",
                     "Lastenheft": "requirements document"}
        material = "Die Aufwandsschätzung steht ganz am Anfang."
        assert glossar.sift(eintraege, material) == {"Aufwandsschätzung": "effort estimation"}

    def test_achtet_auf_wortgrenzen(self):
        assert glossar.sift({"Kurs": "course"}, "Der Text ist in Kursivschrift.") == {}

    def test_deckelt_die_zahl_der_begriffe(self):
        eintraege = {f"Begriff{i}": f"term{i}" for i in range(glossar.MAX_TERMS + 20)}
        assert len(glossar.sift(eintraege, " ".join(eintraege))) == glossar.MAX_TERMS

    def test_ohne_eintraege_oder_ohne_material_bleibt_nichts(self):
        assert glossar.sift({}, "Ein Text mit Inhalt.") == {}
        assert glossar.sift({"Modul": "module"}, "   ") == {}

    def test_ein_paar_ohne_zielwort_faellt_raus(self):
        assert glossar.sift({"Modul": ""}, "Das Modul ist offen.") == {}


class TestBlock:
    def test_nennt_jedes_paar(self):
        text = glossar.block({"Modul": "module", "Beleg": "credit"}, "de")
        assert "Modul = module" in text
        assert "Beleg = credit" in text

    def test_deutsch_und_englisch_bekommen_ihre_ueberschrift(self):
        assert glossar.LABEL_DE in glossar.block({"Modul": "module"}, "de")
        assert glossar.LABEL_EN in glossar.block({"Modul": "module"}, "en")

    def test_leere_liste_gibt_nichts(self):
        assert glossar.block({}, "de") == ""


class TestImPrompt:
    def test_steht_im_auftrag_fuer_das_skript(self):
        nachrichten = build_messages("Material", _params(glossary={"Modul": "module"}))
        assert "Modul = module" in nachrichten[1]["content"]

    def test_steht_auch_beim_umformulieren(self):
        nachrichten = rephrase_messages(
            Line(speaker=0, text="Hallo."), _params(glossary={"Modul": "module"}), [])
        assert "Modul = module" in nachrichten[1]["content"]

    def test_fehlt_ganz_ohne_glossar(self):
        auftrag = build_messages("Material", _params())[1]["content"]
        assert glossar.LABEL_DE not in auftrag
        assert glossar.LABEL_EN not in auftrag

    def test_steht_vor_der_zusaetzlichen_anweisung(self):
        auftrag = build_messages(
            "Material",
            _params(glossary={"Modul": "module"}, instructions="sprich langsam"),
        )[1]["content"]
        assert auftrag.index("Modul = module") < auftrag.index("sprich langsam")
