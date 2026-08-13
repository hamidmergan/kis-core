"""Die geteilte Titel-Logik, losgeloest von den Uebungs-Saetzen.

Sie liegt jetzt unter ``tasks/_titles.py``, weil Mindmap und Datentabelle sie
mitbenutzen. Der Unterschied zur alten Fassung: die Liste der schon vergebenen
Titel kommt herein, statt dass das Modul selbst ``aia_exercise_sets`` liest.

Kein Netz und keine Datenbank, das Modell ist gefaelscht.
"""

import types

from src.features.ai_assistant.tasks._titles import (
    MAX_TITLE_LEN,
    is_title_taken,
    next_free_counter,
    resolve_title,
    title_from_entries,
)


class _FakeClient:
    """Liefert der Reihe nach die vorgegebenen Antworten und merkt sich die Aufrufe."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.aufrufe.append(kwargs)
        inhalt = self._antworten.pop(0) if self._antworten else ""
        nachricht = types.SimpleNamespace(content=inhalt)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=nachricht)])


def test_title_from_entries_nimmt_die_erste_zeile():
    client = _FakeClient(['"Passiv im Labor"\nnoch eine Zeile'])
    assert title_from_entries(client, "m", ["a", "b"], "Rueckfall") == "Passiv im Labor"


def test_title_from_entries_ohne_eintraege_ruft_das_modell_nicht():
    client = _FakeClient(["egal"])
    assert title_from_entries(client, "m", [], "Rueckfall") == "Rueckfall"
    assert client.aufrufe == []


def test_title_from_entries_faellt_bei_leerer_antwort_zurueck():
    client = _FakeClient([""])
    assert title_from_entries(client, "m", ["a"], "Rueckfall") == "Rueckfall"


def test_title_from_entries_faellt_bei_fehler_zurueck():
    class _Kaputt(_FakeClient):
        def _create(self, **kwargs):
            raise RuntimeError("Anbieter weg")

    assert title_from_entries(_Kaputt([]), "m", ["a"], "Rueckfall") == "Rueckfall"


def test_title_from_entries_reicht_die_verbotenen_titel_durch():
    client = _FakeClient(["Neuer Titel"])
    title_from_entries(client, "m", ["a"], "Rueckfall", avoid=["Alter Titel"])
    system = client.aufrufe[0]["messages"][0]["content"]
    assert "Alter Titel" in system


def test_resolve_title_nimmt_den_vorschlag_wenn_er_frei_ist():
    client = _FakeClient(["Passiv im Labor"])
    assert resolve_title(client, "m", ["Ganz anderes"], "Rueckfall", ["a"]) == "Passiv im Labor"


def test_resolve_title_versucht_es_bei_dopplung_ein_zweites_mal():
    client = _FakeClient(["Belegt", "Frei und neu"])
    assert resolve_title(client, "m", ["Belegt"], "Rueckfall", ["a"]) == "Frei und neu"
    assert len(client.aufrufe) == 2


def test_resolve_title_haengt_am_ende_einen_zaehler_an():
    client = _FakeClient(["Belegt", "Belegt"])
    assert resolve_title(client, "m", ["Belegt"], "Rueckfall", ["a"]) == "Belegt (2)"


def test_resolve_title_ohne_eintraege_gibt_den_rueckfall():
    client = _FakeClient(["egal"])
    assert resolve_title(client, "m", [], "Rueckfall", []) == "Rueckfall"
    assert client.aufrufe == []


def test_is_title_taken_erkennt_den_einen_buchstaben_unterschied():
    assert is_title_taken("Wissenschaftliches Arbeiten", ["Wissenschaftliche Arbeiten"])


def test_next_free_counter_zaehlt_ueber_die_ganze_familie():
    assert next_free_counter("Titel", ["Titel", "Titel (2)"]) == "Titel (3)"


def test_max_title_len_ist_die_eine_obergrenze():
    assert MAX_TITLE_LEN == 120
