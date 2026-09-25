"""The Celery body: reading whole files, window and pages, stages, naming, progress."""

import io
import json

import pytest
from docx import Document

from tests.summary_helpers import FakeClient

from src.tasks import summary_tasks as st
from src.tasks._stage import StageContinue

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a", "fact_ids": [1, 2]},
    {"title": "B", "description": "b", "fact_ids": []},
    {"title": "C", "description": "c", "fact_ids": []}]})
_PLAN_MIT_TITEL = json.dumps({"title": "Die neue Pruefungsordnung", "intro": "Vorweg.",
                              "sections": [
    {"title": "A", "description": "a", "fact_ids": [1, 2]},
    {"title": "B", "description": "b", "fact_ids": []},
    {"title": "C", "description": "c", "fact_ids": []}]})
_GRUPPE = "## A\nText A\n\n## B\nText B\n\n## C\nText C"
_ZUORDNUNG = json.dumps({"assignments": [{"fact_id": n, "section_index": n - 1}
                                         for n in (1, 2, 3)]})
_QUELLEN = [{"filename": "a.txt", "input_path": "p1"}]
# Die Sprache wird am Text gelesen, ein Test der sie prueft muss echten Text liefern.
_DEUTSCHER_TEXT = ("Die Lohnsteuer ist spaetestens am zehnten Tag nach Ablauf des "
                   "Anmeldungszeitraums abzufuehren. Wer eine gewerbliche Taetigkeit "
                   "aufnimmt, teilt dies der Gemeinde innerhalb eines Monats mit. ") * 3
_SPANISCHER_TEXT = ("El impuesto sobre la renta debe pagarse antes del decimo dia "
                    "siguiente al final del periodo de declaracion. Quien inicie una "
                    "actividad comercial debe informar al municipio en un mes. ") * 3


def _modell(monkeypatch, antworten):
    client = FakeClient(antworten)
    traeger = type("K", (), {"_async_client": client, "_model": "m"})()
    import src.tasks.general_tasks as gt
    monkeypatch.setattr(gt, "_get_llm_client", lambda pid=None: traeger)
    monkeypatch.setattr(st, "log_llm_response", lambda *a, **k: None)
    return client




class TestDateigrenzeAusDemAdminbereich:
    """Wie viel Text ein Lese-Aufruf traegt, entscheidet die Einstellung, nicht der Code."""


class TestFensterUndSeiten:
    """Was das Modell nicht am Stueck lesen kann, wird vor dem ersten Aufruf abgelehnt."""








class TestNamensgebung:
    """Der Titel kommt aus dem Gliederungsaufruf, ein eigener Aufruf dafuer gibt es nicht."""







class TestTitelSaeuberung:
    def test_was_in_keinen_dateinamen_darf_faellt_weg(self):
        assert st._clean_title('Recht: Paragraf 5/7 <neu>?') == "Recht Paragraf 5 7 neu"

    def test_ein_langer_titel_wird_am_wort_gekuerzt(self):
        titel = st._clean_title("Wort " * 40)
        assert len(titel) <= st._TITLE_MAX_CHARS
        assert titel.endswith("Wort")

    def test_ein_titel_aus_lauter_verbotenem_zaehlt_als_keiner(self):
        assert st._clean_title("///") == ""
        assert st._result_name(["a.txt"], "///") == "a.md"

    def test_eine_fuehrende_raute_und_leerraum_verschwinden(self):
        assert st._clean_title("#  Der   Titel  ") == "Der Titel"


class TestSpracheDerWortdatei:
    """Der Hinweis auf dem Deckblatt folgt dem Dokument, nicht der Oberflaeche des Nutzers."""

    def _gemerkte_sprache(self, monkeypatch) -> dict:
        gemerkt: dict = {}

        def _bauen(text, **k):
            gemerkt.update(k)
            return b"docx"

        monkeypatch.setattr(st, "markdown_to_docx", _bauen)
        return gemerkt




class TestMarkdownDatei:
    """Die Markdown-Datei traegt Titel, Datum und KI-Hinweis wie die Word-Datei."""

    def test_titel_datum_und_hinweis_stehen_vor_dem_text(self):
        from src.tasks.summary_tasks import _markdown_file

        md = _markdown_file("## Kapitel\n\nText.", "AMG74", "25.09.2026", "de")
        teile = md.split("\n\n")
        assert teile[0] == "# AMG74"
        assert teile[1] == "25.09.2026"
        assert teile[2].startswith("*Mit künstlicher Intelligenz erstellt.")
        assert teile[3] == "## Kapitel"

    def test_englisch_bekommt_den_englischen_hinweis(self):
        from src.tasks.summary_tasks import _markdown_file

        assert "*Created with artificial intelligence." in _markdown_file("Text.", "T", "1.1.2026", "en")
