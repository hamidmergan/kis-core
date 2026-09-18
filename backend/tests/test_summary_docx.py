"""The Word converter turns the summary's markdown into real Word structures."""

import io

from docx import Document

from src.features.summary.docx_export import markdown_to_docx


def _open(data: bytes) -> Document:
    return Document(io.BytesIO(data))


class TestUeberschriften:
    def test_zwei_kreuz_wird_heading_2(self):
        doc = _open(markdown_to_docx("## Ein Titel"))
        assert doc.paragraphs[0].style.name == "Heading 2"
        assert doc.paragraphs[0].text == "Ein Titel"

    def test_alle_stufen_von_eins_bis_sechs(self):
        markdown = "\n".join(f"{'#' * n} Stufe {n}" for n in range(1, 7))
        doc = _open(markdown_to_docx(markdown))
        for absatz, n in zip(doc.paragraphs, range(1, 7)):
            assert absatz.style.name == f"Heading {n}"
            assert absatz.text == f"Stufe {n}"


class TestStichpunkte:
    def test_einfache_stichpunkte_mit_stern_und_strich(self):
        doc = _open(markdown_to_docx("* Erstens\n- Zweitens"))
        assert [a.style.name for a in doc.paragraphs] == ["List Bullet", "List Bullet"]
        assert [a.text for a in doc.paragraphs] == ["Erstens", "Zweitens"]

    def test_verschachtelte_stichpunkte_zwei_stufen(self):
        markdown = "- Oben\n    - Erste Stufe\n        - Zweite Stufe"
        doc = _open(markdown_to_docx(markdown))
        assert [a.style.name for a in doc.paragraphs] == [
            "List Bullet", "List Bullet 2", "List Bullet 3",
        ]
        assert [a.text for a in doc.paragraphs] == ["Oben", "Erste Stufe", "Zweite Stufe"]

    def test_nummerierte_liste_wird_list_number(self):
        doc = _open(markdown_to_docx("1. Erstens\n2. Zweitens"))
        assert [a.style.name for a in doc.paragraphs] == ["List Number", "List Number"]
        assert [a.text for a in doc.paragraphs] == ["Erstens", "Zweitens"]


class TestTabellen:
    def test_eine_tabelle_wird_eine_echte_word_tabelle(self):
        markdown = "| Name | Wert |\n| --- | --- |\n| A | 1 |\n| B | 2 |"
        doc = _open(markdown_to_docx(markdown))
        assert len(doc.tables) == 1
        table = doc.tables[0]
        assert len(table.rows) == 3
        assert [c.text for c in table.rows[0].cells] == ["Name", "Wert"]
        assert [c.text for c in table.rows[1].cells] == ["A", "1"]
        assert [c.text for c in table.rows[2].cells] == ["B", "2"]

    def test_die_kopfzeile_ist_fett(self):
        markdown = "| Name | Wert |\n| --- | --- |\n| A | 1 |"
        doc = _open(markdown_to_docx(markdown))
        header_cell = doc.tables[0].rows[0].cells[0]
        assert all(run.bold for run in header_cell.paragraphs[0].runs)
        data_cell = doc.tables[0].rows[1].cells[0]
        assert not any(run.bold for run in data_cell.paragraphs[0].runs)


class TestFettschrift:
    def test_fett_mitten_im_satz(self):
        doc = _open(markdown_to_docx("Das ist **wichtig** und **noch etwas** dabei."))
        runs = doc.paragraphs[0].runs
        fett = [r.text for r in runs if r.bold]
        nicht_fett = [r.text for r in runs if not r.bold]
        assert fett == ["wichtig", "noch etwas"]
        assert "".join(runs_text for runs_text in [r.text for r in runs]) == (
            "Das ist wichtig und noch etwas dabei."
        )
        assert nicht_fett


class TestAbsaetze:
    def test_ein_gewoehnlicher_satz_wird_ein_absatz(self):
        doc = _open(markdown_to_docx("Ein ganz normaler Satz."))
        assert len(doc.paragraphs) == 1
        assert doc.paragraphs[0].text == "Ein ganz normaler Satz."
        assert doc.paragraphs[0].style.name in ("Normal", "Default Paragraph Style")

    def test_leerzeilen_erzeugen_keinen_leeren_absatz(self):
        doc = _open(markdown_to_docx("Erster Satz.\n\n\nZweiter Satz."))
        assert [a.text for a in doc.paragraphs] == ["Erster Satz.", "Zweiter Satz."]


class TestGemischtesDokument:
    def test_ueberschrift_liste_und_absatz_zusammen(self):
        markdown = "## Abschnitt\n\nEin Absatz davor.\n\n* Punkt eins\n* Punkt zwei\n\nEin Absatz danach."
        doc = _open(markdown_to_docx(markdown))
        texte = [(a.style.name, a.text) for a in doc.paragraphs]
        assert texte == [
            ("Heading 2", "Abschnitt"),
            ("Normal", "Ein Absatz davor."),
            ("List Bullet", "Punkt eins"),
            ("List Bullet", "Punkt zwei"),
            ("Normal", "Ein Absatz danach."),
        ]
