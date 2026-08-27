"""Mind map and data table take their title from their own result."""

from src.features.ai_assistant.tasks.studio._result_title import (
    mindmap_entries,
    table_entries,
)


def test_mindmap_nimmt_die_knoten_der_ersten_ebene():
    mindmap = {
        "topic": "Studieren in Luebeck",
        "children": [
            {"topic": "Anmeldung", "children": [{"topic": "Frist"}]},
            {"topic": "Pruefungen"},
        ],
    }
    assert mindmap_entries(mindmap) == ["Anmeldung", "Pruefungen"]


def test_mindmap_ohne_kinder_gibt_nichts():
    assert mindmap_entries({"topic": "Allein"}) == []


def test_mindmap_vertraegt_kaputte_knoten():
    mindmap = {"topic": "x", "children": [{"topic": ""}, "kein dict", {"topic": "Gut"}]}
    assert mindmap_entries(mindmap) == ["Gut"]


def test_tabelle_nimmt_spaltenkoepfe_und_erste_spalte():
    table = {
        "columns": ["Begriff", "Bedeutung"],
        "rows": [{"cells": ["Immatrikulation", "Einschreibung"]}, {"cells": ["Modul", "Baustein"]}],
    }
    assert table_entries(table) == ["Begriff", "Bedeutung", "Immatrikulation", "Modul"]


def test_tabelle_ohne_zeilen_gibt_nur_die_koepfe():
    assert table_entries({"columns": ["A"], "rows": []}) == ["A"]


def test_tabelle_vertraegt_leere_form():
    assert table_entries({}) == []


def test_tabelle_faellt_auf_den_modelltitel_zurueck_wenn_der_aufruf_scheitert():
    """A broken title call must not cost a finished table."""
    import types

    from src.features.ai_assistant.tasks._titles import resolve_title

    class _Kaputt:
        def __init__(self):
            def _create(**kwargs):
                raise RuntimeError("Anbieter weg")
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=_create))

    ergebnis = resolve_title(_Kaputt(), "m", [], "Titel aus dem Erzeugungs-Aufruf", ["Begriff"])
    assert ergebnis == "Titel aus dem Erzeugungs-Aufruf"
