"""Folgefragen im Chat: eine kurze Nachfrage wird vor der Suche eigenstaendig gemacht.

Bis hierher stand jede Runde allein. "erklaere genauer" ging als Suchtext in die
Quellen, traf nichts und bekam den Satz "steht nicht in den Quellen"; "in 3
Stichpunkten" wurde als GENERIC gelesen und lieferte einen zweiten, unabhaengigen
Querschnitt derselben Datei. Die letzte Runde geht deshalb in den ohnehin
vorhandenen Vor-Call, der daraus eine eigenstaendige Frage baut.

Alles offline: hier stehen nur die reinen Stuecke (Filter, Verlaufsblock, Parser).
"""

import pytest

from src.features.ai_assistant.repository import chat as repo_chat
from src.features.ai_assistant.routes import _followup as fu


RUNDE = {
    "question": "Was ist die Pruefungsleistung?",
    "answer": "Die Pruefungsleistung besteht aus einer Hausarbeit und einer Praesentation.",
    "source_pages": [],
    "source_qmap": [],
}


# ── kommt eine Nachfrage ueberhaupt infrage ──────────────────────────────────

def test_kurze_frage_mit_vorheriger_runde_kommt_infrage():
    assert fu.ist_nachfrage_moeglich("erklaere genauer", RUNDE) is True


def test_ohne_vorherige_runde_gibt_es_nichts_aufzuloesen():
    assert fu.ist_nachfrage_moeglich("erklaere genauer", None) is False


def test_lange_frage_steht_fuer_sich():
    lang = " ".join(["wort"] * (fu.MAX_NACHFRAGE_WOERTER + 1))
    assert fu.ist_nachfrage_moeglich(lang, RUNDE) is False


def test_markierter_text_bringt_seinen_kontext_selbst_mit():
    assert fu.ist_nachfrage_moeglich("erklaere genauer", RUNDE, quelltext="markiert") is False


def test_runde_ohne_antwort_traegt_keinen_zusammenhang():
    assert fu.ist_nachfrage_moeglich("erklaere genauer", {**RUNDE, "answer": "  "}) is False


def test_eine_reine_absage_traegt_keinen_zusammenhang():
    # "Steht nicht in den Quellen" und sonst nichts nennt kein Thema. Eine
    # Nachfrage darauf eigenstaendig machen zu wollen, kann nur raten.
    from src.features.ai_assistant.prompts.refusal_prompts import RAG_NO_INFO_SENTINEL
    for absage in RAG_NO_INFO_SENTINEL.values():
        assert fu.ist_nachfrage_moeglich("erklaere genauer", {**RUNDE, "answer": absage}) is False


def test_absage_mit_hinweis_traegt_sehr_wohl_einen_zusammenhang():
    # Absage plus Hinweis auf etwas Verwandtes: der Hinweis IST ein Thema, auf
    # das sich "erklaere genauer" beziehen kann.
    from src.features.ai_assistant.prompts.refusal_prompts import RAG_NO_INFO_SENTINEL
    mit_hinweis = (RAG_NO_INFO_SENTINEL["de"]
                   + "\n\nDie Quellen nennen stattdessen eine Hausarbeit als Pruefungsleistung.")
    assert fu.ist_nachfrage_moeglich("erklaere genauer", {**RUNDE, "answer": mit_hinweis}) is True


# ── der Verlaufsblock fuer den Vor-Call ──────────────────────────────────────

def test_verlaufsblock_enthaelt_frage_und_antwort():
    block = fu.verlaufsblock(RUNDE)
    assert "Was ist die Pruefungsleistung?" in block
    assert "Hausarbeit" in block


def test_verlaufsblock_kuerzt_eine_lange_antwort():
    lang = {**RUNDE, "answer": "A" * 5000}
    block = fu.verlaufsblock(lang)
    assert len(block) < 2000


def test_verlaufsblock_wirft_quellenchips_raus():
    mit_chip = {**RUNDE, "answer": "Die Arbeit hat sechs Seiten [Q1 S. 3]."}
    assert "S. 3" not in fu.verlaufsblock(mit_chip)


# ── die Eingabe fuer den Vor-Call ────────────────────────────────────────────

def test_ohne_verlauf_bleibt_die_blanke_frage():
    # Der Vor-Call ist fein abgestimmt. Ohne Nachfrage-Fall bekommt er Zeichen
    # fuer Zeichen dieselbe Eingabe wie vorher.
    assert fu.vorcall_eingabe("Was ist Quellenkritik?", None) == "Was ist Quellenkritik?"


def test_mit_verlauf_steht_die_neue_zeile_hinter_dem_block():
    eingabe = fu.vorcall_eingabe("erklaere genauer", RUNDE)
    assert eingabe.rstrip().endswith("erklaere genauer")
    assert "Pruefungsleistung" in eingabe


# ── die Antwort des Vor-Calls ────────────────────────────────────────────────

def test_liest_art_und_eigenstaendige_frage():
    roh = ('{"intent":"SPECIFIC","followup":"rewrite",'
           '"standalone":"Erklaere die Pruefungsleistung genauer"}')
    assert fu.nachfrage_lesen(roh, "erklaere genauer") == (
        fu.UMSCHREIBEN, "Erklaere die Pruefungsleistung genauer")


def test_liest_das_umformen_der_letzten_antwort():
    roh = '{"followup":"reformat","standalone":"In 3 Stichpunkten"}'
    art, _ = fu.nachfrage_lesen(roh, "in 3 stichpunkten")
    assert art == fu.UMFORMEN


def test_eigenstaendige_frage_ohne_inhalt_faellt_auf_das_original_zurueck():
    roh = '{"followup":"rewrite","standalone":"   "}'
    assert fu.nachfrage_lesen(roh, "erklaere genauer") == (fu.KEINE, "erklaere genauer")


def test_unbekannte_art_gilt_als_keine_nachfrage():
    roh = '{"followup":"vielleicht","standalone":"irgendwas"}'
    assert fu.nachfrage_lesen(roh, "erklaere genauer") == (fu.KEINE, "erklaere genauer")


def test_muell_aendert_die_frage_nicht():
    assert fu.nachfrage_lesen("kein json", "erklaere genauer") == (fu.KEINE, "erklaere genauer")
    assert fu.nachfrage_lesen("", "erklaere genauer") == (fu.KEINE, "erklaere genauer")


def test_denkblock_und_codezaun_stoeren_nicht():
    roh = '<think>hm</think>```json\n{"followup":"rewrite","standalone":"Erklaere X genauer"}\n```'
    assert fu.nachfrage_lesen(roh, "erklaere genauer") == (fu.UMSCHREIBEN, "Erklaere X genauer")


# ── lohnt sich der Blick in die Datenbank ────────────────────────────────────

def test_kurze_frage_lohnt_den_blick_in_den_verlauf():
    assert fu.lohnt_nachschlagen("erklaere genauer", None) is True


def test_markierter_text_lohnt_den_blick_nicht():
    assert fu.lohnt_nachschlagen("erklaere genauer", "markiert") is False


def test_lange_frage_lohnt_den_blick_nicht():
    lang = " ".join(["wort"] * (fu.MAX_NACHFRAGE_WOERTER + 1))
    assert fu.lohnt_nachschlagen(lang, None) is False


# ── die Quellen der letzten Runde weiterverwenden ────────────────────────────

UUID_ZU_ID = {"u1": 11, "u2": 22}


def test_quellennummern_kommen_aus_der_letzten_runde():
    runde = {
        "source_qmap": [{"qnum": 1, "uuid": "u1", "filename": "skript.pdf"}],
        "source_pages": [{"source_uuid": "u1", "page_number": 3}],
    }
    qmap, id_zu_qnum, _gesehen, _seiten = fu.letzte_quellen(runde, UUID_ZU_ID)
    assert qmap == runde["source_qmap"]
    assert id_zu_qnum == {11: 1}


def test_gesehene_seiten_stehen_pro_quelle():
    runde = {
        "source_qmap": [{"qnum": 1, "uuid": "u1"}, {"qnum": 2, "uuid": "u2"}],
        "source_pages": [
            {"source_uuid": "u1", "page_number": 3},
            {"source_uuid": "u1", "page_number": 4},
            {"source_uuid": "u2", "page_number": 1},
        ],
    }
    _qmap, _id, gesehen, _seiten = fu.letzte_quellen(runde, UUID_ZU_ID)
    assert gesehen == {11: {3, 4}, 22: {1}}


def test_bei_ton_und_video_bleibt_die_seitenmenge_leer():
    # Medien werden ueber die Quelle geprueft und ueber Zeitmarken angesprungen,
    # die Seitenzahl ist dort nur ein Abschnittszaehler.
    runde = {
        "source_qmap": [{"qnum": 1, "uuid": "u1"}],
        "source_pages": [{"source_uuid": "u1", "page_number": 7, "start_time": 12.5}],
    }
    _qmap, _id, gesehen, _seiten = fu.letzte_quellen(runde, UUID_ZU_ID)
    assert gesehen == {11: set()}


def test_geloeschte_quelle_faellt_ueberall_raus():
    runde = {
        "source_qmap": [{"qnum": 1, "uuid": "weg"}, {"qnum": 2, "uuid": "u1"}],
        "source_pages": [{"source_uuid": "weg", "page_number": 1},
                         {"source_uuid": "u1", "page_number": 2}],
    }
    qmap, id_zu_qnum, gesehen, seiten = fu.letzte_quellen(runde, UUID_ZU_ID)
    assert [q["uuid"] for q in qmap] == ["u1"]
    assert id_zu_qnum == {11: 2}
    assert gesehen == {11: {2}}
    assert [s["source_uuid"] for s in seiten] == ["u1"]


def test_runde_ohne_quellen_gibt_leere_zuordnung():
    assert fu.letzte_quellen({}, UUID_ZU_ID) == ([], {}, {}, [])


# ── der Vor-Call-Systemprompt ────────────────────────────────────────────────

def test_ohne_verlauf_ist_der_prompt_unveraendert():
    # Die Wegwahl des Vor-Calls ist fein abgestimmt. Ohne Nachfrage-Fall darf
    # sich an seinem Prompt kein Zeichen aendern.
    from src.features.ai_assistant.prompts.query_understanding_prompts import (
        AIA_QUERY_UNDERSTANDING_SYSTEM,
        aia_query_understanding_system,
    )
    assert aia_query_understanding_system(False) == AIA_QUERY_UNDERSTANDING_SYSTEM


def test_mit_verlauf_kommen_die_beiden_felder_dazu():
    from src.features.ai_assistant.prompts.query_understanding_prompts import (
        aia_query_understanding_system,
    )
    prompt = aia_query_understanding_system(True)
    assert '"followup"' in prompt
    assert '"standalone"' in prompt
    for art in ("none", "rewrite", "reformat"):
        assert f'"{art}"' in prompt


# ── der Vor-Call selbst ──────────────────────────────────────────────────────

class _MitschreibenderLLM:
    """Attrappe des Anbieters, die mitschreibt, was gesendet wurde."""

    def __init__(self, inhalt=""):
        self.gesendet: list[dict] = []
        aussen = self

        class _Completions:
            def create(self, **kw):
                aussen.gesendet.append(kw)
                return type("R", (), {"choices": [
                    type("C", (), {"message": type("M", (), {"content": inhalt})()})()]})()

        class _Client:
            def with_options(self, **kw):
                return self

            @property
            def chat(self):
                return type("Chat", (), {"completions": _Completions()})()

        self._client = _Client()
        self._model = "fake-model"
        self._extra_body = None


@pytest.mark.asyncio
async def test_ohne_letzte_runde_geht_nur_die_frage_raus():
    from src.features.ai_assistant.routes.chat import _understand_query
    from src.features.ai_assistant.prompts.query_understanding_prompts import (
        AIA_QUERY_UNDERSTANDING_SYSTEM,
    )
    llm = _MitschreibenderLLM('{"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]}}')
    _intent, _scope, _subs, art, frage = await _understand_query(llm, "Was ist Quellenkritik?")
    nachrichten = llm.gesendet[0]["messages"]
    assert nachrichten[0]["content"] == AIA_QUERY_UNDERSTANDING_SYSTEM
    assert nachrichten[1]["content"] == "Was ist Quellenkritik?"
    assert (art, frage) == (fu.KEINE, "Was ist Quellenkritik?")


@pytest.mark.asyncio
async def test_mit_letzter_runde_wird_die_frage_eigenstaendig():
    from src.features.ai_assistant.routes.chat import _understand_query
    llm = _MitschreibenderLLM(
        '{"intent":"SPECIFIC","scope":{"unit":null,"intervals":[]},'
        '"followup":"rewrite","standalone":"Erklaere die Pruefungsleistung genauer"}')
    _intent, _scope, _subs, art, frage = await _understand_query(
        llm, "erklaere genauer", letzte_runde=RUNDE)
    nachrichten = llm.gesendet[0]["messages"]
    assert "Pruefungsleistung" in nachrichten[1]["content"]
    assert nachrichten[1]["content"].rstrip().endswith("erklaere genauer")
    assert (art, frage) == (fu.UMSCHREIBEN, "Erklaere die Pruefungsleistung genauer")


@pytest.mark.asyncio
async def test_faellt_der_vorcall_aus_bleibt_die_frage_wie_sie_war():
    from src.features.ai_assistant.routes.chat import _understand_query

    class _Kaputt(_MitschreibenderLLM):
        @property
        def _client(self):
            raise RuntimeError("provider down")

        @_client.setter
        def _client(self, wert):
            pass

    _intent, _scope, _subs, art, frage = await _understand_query(
        _Kaputt(), "erklaere genauer", letzte_runde=RUNDE)
    assert (art, frage) == (fu.KEINE, "erklaere genauer")


# ── die Nachrichten fuers Umformen ───────────────────────────────────────────

def test_umformen_schickt_die_alte_antwort_und_die_anweisung():
    nachrichten = fu.umform_nachrichten(RUNDE, "In 3 Stichpunkten", "de", [], "")
    assert [n["role"] for n in nachrichten] == ["system", "user"]
    assert "Hausarbeit" in nachrichten[1]["content"]
    assert "In 3 Stichpunkten" in nachrichten[1]["content"]


def test_umformen_schickt_die_alten_chips_nicht_mit():
    runde = {**RUNDE, "answer": "Die Arbeit hat sechs Seiten [Q1 S. 3]."}
    nachrichten = fu.umform_nachrichten(runde, "kuerzer", "de", [], "")
    assert "S. 3" not in nachrichten[1]["content"]


def test_umformen_haengt_den_zusatz_ganz_ans_ende():
    # Der Sprachtrainer-Zusatz traegt die Quellen-Sperre und muss zuletzt stehen.
    nachrichten = fu.umform_nachrichten(RUNDE, "kuerzer", "de", [], "\nZUSATZ")
    assert nachrichten[1]["content"].endswith("\nZUSATZ")


def test_umformen_kuerzt_die_alte_antwort_nicht():
    # Beim Umformen IST die alte Antwort der Stoff. Sie darf nicht auf die
    # Anhaltspunkt-Laenge des Vor-Calls gestutzt werden.
    lang = {**RUNDE, "answer": "A" * 5000}
    assert "A" * 5000 in fu.umform_nachrichten(lang, "kuerzer", "de", [], "")[1]["content"]


# ── die letzte Runde aus der Datenbank ───────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchall(self):
        return self._rows or []


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows):
        calls: list[tuple] = []
        monkeypatch.setattr(repo_chat, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


def _zeile(role, content, aborted=False, failed=False, source_pages=None, source_qmap=None):
    return {"role": role, "content": content, "aborted": aborted, "failed": failed,
            "source_pages": source_pages, "source_qmap": source_qmap}


def test_letzte_runde_ist_frage_und_zugehoerige_antwort(fake_db):
    # Neueste zuerst, wie die Abfrage liefert.
    fake_db([
        _zeile("assistant", "Sie besteht aus Hausarbeit und Praesentation."),
        _zeile("user", "Was ist die Pruefungsleistung?"),
        _zeile("assistant", "Aeltere Antwort"),
        _zeile("user", "Aeltere Frage"),
    ])
    runde = repo_chat.get_last_aia_round(1, 2)
    assert runde["question"] == "Was ist die Pruefungsleistung?"
    assert runde["answer"] == "Sie besteht aus Hausarbeit und Praesentation."


def test_abgebrochene_antwort_zaehlt_nicht(fake_db):
    fake_db([
        _zeile("assistant", "halbe Antw", aborted=True),
        _zeile("user", "Was ist die Pruefungsleistung?"),
        _zeile("assistant", "Vollstaendige Antwort"),
        _zeile("user", "Was ist Quellenkritik?"),
    ])
    runde = repo_chat.get_last_aia_round(1, 2)
    assert runde["answer"] == "Vollstaendige Antwort"
    assert runde["question"] == "Was ist Quellenkritik?"


def test_gescheiterte_antwort_zaehlt_nicht(fake_db):
    fake_db([
        _zeile("assistant", "", failed=True),
        _zeile("user", "Was ist die Pruefungsleistung?"),
        _zeile("assistant", "Vollstaendige Antwort"),
        _zeile("user", "Was ist Quellenkritik?"),
    ])
    assert repo_chat.get_last_aia_round(1, 2)["answer"] == "Vollstaendige Antwort"


def test_ohne_antwort_gibt_es_keine_runde(fake_db):
    fake_db([_zeile("user", "Erste Frage ueberhaupt")])
    assert repo_chat.get_last_aia_round(1, 2) is None


def test_leerer_verlauf_gibt_nichts(fake_db):
    fake_db([])
    assert repo_chat.get_last_aia_round(1, 2) is None


def test_quellen_der_letzten_antwort_kommen_mit(fake_db):
    seiten = [{"source_uuid": "u1", "page_number": 3}]
    qmap = [{"qnum": 1, "uuid": "u1", "filename": "skript.pdf"}]
    fake_db([
        _zeile("assistant", "Antwort", source_pages=seiten, source_qmap=qmap),
        _zeile("user", "Frage"),
    ])
    runde = repo_chat.get_last_aia_round(1, 2)
    assert runde["source_pages"] == seiten
    assert runde["source_qmap"] == qmap


def test_zugangslink_hat_seine_eigene_letzte_runde(fake_db):
    calls = fake_db([])
    repo_chat.get_last_aia_round(1, 2, enrollment_id=7)
    sql, params = calls[0]
    assert "enrollment_id = %s" in sql
    assert params[:3] == (1, 2, 7)

    calls = fake_db([])
    repo_chat.get_last_aia_round(1, 2)
    sql, params = calls[0]
    assert "enrollment_id IS NULL" in sql
