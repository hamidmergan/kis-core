"""Renaming a source, the expensive part is the name copies in the generated material."""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.repository import source_rename as repo
from src.features.ai_assistant.routes.sources import _rename


def test_umschreiben_trifft_den_quellennamen_im_baum():
    baum = {
        "topic": "Wurzel",
        "children": [
            {"topic": "A", "source_label": "alt.pdf", "page_number": 3},
            {"topic": "B", "source_label": "andere.pdf", "page_number": 4},
        ],
    }

    neu = repo._relabel(baum, "alt.pdf", "neu.pdf")

    assert neu["children"][0]["source_label"] == "neu.pdf"
    assert neu["children"][1]["source_label"] == "andere.pdf"


def test_umschreiben_trifft_die_legende_einer_datentabelle():
    legende = [{"number": 1, "filename": "alt.pdf"}, {"number": 2, "filename": "b.pdf"}]

    neu = repo._relabel(legende, "alt.pdf", "neu.pdf")

    assert neu == [{"number": 1, "filename": "neu.pdf"}, {"number": 2, "filename": "b.pdf"}]


def test_umschreiben_laesst_fliesstext_in_ruhe():
    """Replacement happens only under the two name keys."""
    zeile = {"front": "Woher stammt alt.pdf?", "back": "Aus alt.pdf", "source_label": "alt.pdf"}

    neu = repo._relabel(zeile, "alt.pdf", "neu.pdf")

    assert neu["source_label"] == "neu.pdf"
    assert neu["front"] == "Woher stammt alt.pdf?"
    assert neu["back"] == "Aus alt.pdf"


def test_umschreiben_geht_durch_tief_verschachtelte_zeilen():
    tabelle = {"rows": [{"cells": ["x"], "sources": [{"source_label": "alt.pdf", "page": 2}]}]}

    neu = repo._relabel(tabelle, "alt.pdf", "neu.pdf")

    assert neu["rows"][0]["sources"][0]["source_label"] == "neu.pdf"


class _FakeCursor:
    """Cursor stub, records every statement and returns given rows."""

    def __init__(self, antworten, calls):
        self._antworten = list(antworten)
        self._calls = calls
        self._letzte = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        # Record untruncated, otherwise the tests would silently pass.
        self._calls.append((" ".join(sql.split()), params))
        self._letzte = self._antworten.pop(0) if self._antworten else []

    def fetchone(self):
        return self._letzte[0] if self._letzte else None

    def fetchall(self):
        return list(self._letzte)


class _FakeConn:
    def __init__(self, antworten, calls):
        self._cur = _FakeCursor(antworten, calls)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, *a, **k):
        return self._cur

    def commit(self):
        self.committed = True


@pytest.fixture
def datenbank(monkeypatch):
    """Replaces the connection with a stub and returns setter and reader helpers."""

    zustand = {"calls": [], "conn": None}

    def _vorbereiten(antworten):
        conn = _FakeConn(antworten, zustand["calls"])
        zustand["conn"] = conn

        class _Ctx:
            def __enter__(self):
                return conn

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(repo, "get_connection", lambda: _Ctx())
        return zustand

    return _vorbereiten


# The expected answer sequence of the rename.
def _antworten_ohne_material(source_id=5, workspace_id=7, alt="alt.pdf"):
    return [
        [(source_id, workspace_id, alt)],  # SELECT auf aia_sources
        [], [], [],                        # UPDATE sources, exercise_items, exercise_pool
        [], [], [], [], [],                # SELECT auf die fuenf JSON-Spalten
    ]


def test_umbenennen_setzt_den_namen_und_schliesst_ab(datenbank):
    zustand = datenbank(_antworten_ohne_material())

    repo.rename_aia_source("q1", "neu.pdf")

    anweisungen = [c[0] for c in zustand["calls"]]
    assert any("UPDATE aia_sources SET filename" in a for a in anweisungen)
    assert zustand["conn"].committed is True


def test_umbenennen_zieht_die_textspalten_mit(datenbank):
    zustand = datenbank(_antworten_ohne_material())

    repo.rename_aia_source("q1", "neu.pdf")

    anweisungen = [c[0] for c in zustand["calls"]]
    assert any("aia_exercise_items" in a and "source_label" in a for a in anweisungen)
    assert any("aia_exercise_pool" in a and "source_label" in a for a in anweisungen)


def test_umbenennen_grenzt_auf_den_eigenen_kursraum_ein(datenbank):
    """An equal name in another course room must not be dragged along."""
    zustand = datenbank(_antworten_ohne_material(workspace_id=7))

    repo.rename_aia_source("q1", "neu.pdf")

    fuer_material = [
        c for c in zustand["calls"]
        if "aia_mindmaps" in c[0] or "aia_data_tables" in c[0]
    ]
    assert fuer_material
    assert all(c[1] == (7,) for c in fuer_material)


def test_umbenennen_schreibt_json_spalten_mit_altem_namen_neu(datenbank):
    baum = {"topic": "W", "children": [{"topic": "A", "source_label": "alt.pdf"}]}
    antworten = [
        [(5, 7, "alt.pdf")],
        [], [], [],
        [],                 # aia_exercise_items.sources
        [],                 # aia_exercise_pool.sources
        [(11, baum)],       # aia_mindmaps.mindmap
        [], [],
    ]
    zustand = datenbank(antworten)

    repo.rename_aia_source("q1", "neu.pdf")

    schreiber = [
        c for c in zustand["calls"]
        if c[0].startswith("UPDATE aia_mindmaps SET mindmap")
    ]
    assert len(schreiber) == 1
    geschrieben = schreiber[0][1][0]
    assert geschrieben.adapted["children"][0]["source_label"] == "neu.pdf"


def test_umbenennen_ruehrt_unveraenderte_json_zeilen_nicht_an(datenbank):
    """No write without a change, otherwise the table grows for no reason."""
    baum = {"topic": "W", "children": [{"topic": "A", "source_label": "andere.pdf"}]}
    antworten = [
        [(5, 7, "alt.pdf")],
        [], [], [],
        [], [],
        [(11, baum)],
        [], [],
    ]
    zustand = datenbank(antworten)

    repo.rename_aia_source("q1", "neu.pdf")

    assert not [
        c for c in zustand["calls"]
        if c[0].startswith("UPDATE aia_mindmaps SET mindmap")
    ]


def test_umbenennen_auf_denselben_namen_macht_nichts(datenbank):
    zustand = datenbank([[(5, 7, "alt.pdf")]])

    repo.rename_aia_source("q1", "alt.pdf")

    assert len(zustand["calls"]) == 1


def test_umbenennen_einer_unbekannten_quelle_macht_nichts(datenbank):
    zustand = datenbank([[]])

    repo.rename_aia_source("gibtsnicht", "neu.pdf")

    assert len(zustand["calls"]) == 1


def _route_vorbereiten(monkeypatch, quellen, eigene="alt.pdf"):
    """Stubs out permission check, source access, label and database."""
    workspace = {"id": 7, "uuid": "w1", "user_id": 42}
    source = {"uuid": "q1", "workspace_id": 7, "filename": eigene}
    andere = [{"uuid": f"x{i}", "filename": n} for i, n in enumerate(quellen)]

    monkeypatch.setattr(_rename, "_require_workspace_manage", lambda *a, **k: workspace)
    monkeypatch.setattr(_rename, "_load_workspace_source", lambda *a, **k: source)
    monkeypatch.setattr(_rename, "_workspace_label", lambda locale: "Kurs")
    monkeypatch.setattr(
        _rename.db, "get_aia_sources_by_workspace",
        lambda ws_id: andere + [{"uuid": "q1", "filename": eigene}],
    )
    gerufen = []
    monkeypatch.setattr(_rename, "rename_aia_source", lambda u, n: gerufen.append((u, n)))
    return gerufen


def _umbenennen(name: str):
    return _rename.rename_source(
        workspace_uuid="w1",
        source_uuid="q1",
        body=_rename.RenameSourceBody(name=name),
        current_user={"user_id": 42},
        locale="de",
    )


def test_route_haengt_die_alte_endung_wieder_an(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch, [])

    antwort = _umbenennen("Woche 1 Einführung")

    assert antwort == {"filename": "Woche 1 Einführung.pdf"}
    assert gerufen == [("q1", "Woche 1 Einführung.pdf")]


def test_route_verdoppelt_eine_mitgetippte_endung_nicht(monkeypatch):
    _route_vorbereiten(monkeypatch, [])

    assert _umbenennen("Woche 1.pdf") == {"filename": "Woche 1.pdf"}


def test_route_wirft_verbotene_zeichen_raus(monkeypatch):
    """Path separators and line breaks break header line and prompt."""
    _route_vorbereiten(monkeypatch, [])

    assert _umbenennen("a/b\\c\nd") == {"filename": "abcd.pdf"}


def test_route_lehnt_einen_leeren_namen_ab(monkeypatch):
    _route_vorbereiten(monkeypatch, [])

    with pytest.raises(HTTPException) as fehler:
        _umbenennen("   ")

    assert fehler.value.status_code == 400


def test_route_lehnt_einen_zu_langen_namen_ab(monkeypatch):
    _route_vorbereiten(monkeypatch, [])

    with pytest.raises(HTTPException) as fehler:
        _umbenennen("x" * 201)

    assert fehler.value.status_code == 400


def test_route_lehnt_einen_schon_vergebenen_namen_ab(monkeypatch):
    _route_vorbereiten(monkeypatch, ["Woche 1.pdf"])

    with pytest.raises(HTTPException) as fehler:
        _umbenennen("woche 1")

    assert fehler.value.status_code == 409


def test_route_stoert_sich_nicht_am_eigenen_namen(monkeypatch):
    """Whoever only changes the capitalisation must not fail on the duplicate check."""
    _route_vorbereiten(monkeypatch, [], eigene="alt.pdf")

    assert _umbenennen("Alt") == {"filename": "Alt.pdf"}


def test_route_laesst_eine_quelle_ohne_endung_zu(monkeypatch):
    """Older rows can carry a name without a period."""
    _route_vorbereiten(monkeypatch, [], eigene="ohnepunkt")

    assert _umbenennen("neu") == {"filename": "neu"}
