"""Chapters are pure structure, no file may disappear."""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.repository import chapters as repo
from src.features.ai_assistant.routes.sources import _chapters


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


# ─── Repository ──────────────────────────────────────────────────────────────

def test_anlegen_haengt_hinten_an(datenbank):
    """A new chapter goes at the bottom, not somewhere in the middle."""
    zustand = datenbank([[{"id": 1, "uuid": "k1", "name": "Neu", "position": 3}]])

    repo.create_aia_chapter(7, "k1", "Neu")

    sql = zustand["calls"][0][0]
    assert "MAX(position) + 1" in sql
    assert zustand["conn"].committed is True


def test_loeschen_nimmt_keine_quelle_mit(datenbank):
    """The statement only hits aia_chapters, the sources hang off it via SET NULL."""
    zustand = datenbank([[(7,)], []])

    repo.delete_aia_chapter("k1")

    anweisungen = [c[0] for c in zustand["calls"]]
    assert anweisungen[0].startswith("DELETE FROM aia_chapters")
    assert not any("aia_sources" in a for a in anweisungen)


def test_loeschen_rueckt_die_nummern_zurecht(datenbank):
    """Otherwise gaps would remain and the neighbour lookup when moving would miss."""
    zustand = datenbank([[(7,)], []])

    repo.delete_aia_chapter("k1")

    assert any("ROW_NUMBER()" in c[0] for c in zustand["calls"])


def test_loeschen_eines_unbekannten_kapitels_nummeriert_nicht_um(datenbank):
    zustand = datenbank([[]])

    repo.delete_aia_chapter("gibtsnicht")

    assert not any("ROW_NUMBER()" in c[0] for c in zustand["calls"])


def test_verschieben_tauscht_mit_dem_nachbarn(datenbank):
    # SELECT Kapitel, UPDATE Umnummerierung, SELECT Position, SELECT Nachbar, 2x UPDATE
    zustand = datenbank([[(5, 7, 2)], [], [(2,)], [(9,)], [], []])

    assert repo.move_aia_chapter("k1", "up") is True

    updates = [c for c in zustand["calls"] if c[0].startswith("UPDATE aia_chapters SET position = %s WHERE id")]
    assert [c[1] for c in updates] == [(2, 9), (1, 5)]


def test_verschieben_am_rand_macht_nichts(datenbank):
    """Without a neighbour everything stays, instead of writing a negative position."""
    zustand = datenbank([[(5, 7, 0)], [], [(0,)], []])

    assert repo.move_aia_chapter("k1", "up") is False

    assert not [c for c in zustand["calls"] if c[0].startswith("UPDATE aia_chapters SET position = %s WHERE id")]


def test_verschieben_mit_unsinniger_richtung_ruehrt_die_datenbank_nicht_an(datenbank):
    zustand = datenbank([])

    assert repo.move_aia_chapter("k1", "seitwaerts") is False

    assert zustand["calls"] == []


def test_zuordnen_ohne_kapitel_setzt_null(datenbank):
    zustand = datenbank([[]])

    repo.set_aia_source_chapter("q1", None)

    assert zustand["calls"][0][1] == (None, None, "q1")


def test_zuordnen_in_ein_neues_kapitel_setzt_die_quelle_nach_oben(datenbank):
    """A changed chapter drops the manual slot, so the file lands on top."""
    zustand = datenbank([[]])

    repo.set_aia_source_chapter("q1", 4)

    sql = zustand["calls"][0][0]
    assert "chapter_id IS DISTINCT FROM %s THEN NULL" in sql


def test_quelle_verschieben_nummeriert_die_ganze_gruppe(datenbank):
    # SELECT Quelle, SELECT Gruppe, UPDATE Positionen
    zustand = datenbank([[(5, 7, 3)], [(8,), (5,), (2,)], []])

    assert repo.move_aia_source("q1", "up") is True

    gruppe = zustand["calls"][1]
    assert "chapter_id IS NOT DISTINCT FROM %s" in gruppe[0]
    assert gruppe[1] == (7, 3)
    update = zustand["calls"][2]
    assert update[0].startswith("UPDATE aia_sources SET position")
    assert update[1] == ([5, 8, 2], [5, 8, 2])
    assert zustand["conn"].committed


def test_quelle_verschieben_am_rand_macht_nichts(datenbank):
    zustand = datenbank([[(5, 7, None)], [(8,), (5,)], []])

    assert repo.move_aia_source("q1", "down") is False

    assert not [c for c in zustand["calls"] if c[0].startswith("UPDATE")]


def test_quelle_verschieben_mit_unsinniger_richtung_ruehrt_die_datenbank_nicht_an(datenbank):
    zustand = datenbank([])

    assert repo.move_aia_source("q1", "seitwaerts") is False

    assert zustand["calls"] == []


# ─── Routen ──────────────────────────────────────────────────────────────────

def _route_vorbereiten(monkeypatch, vorhandene=(), anzahl=0, fremd=False):
    """Stubs out the permission check and the database."""
    workspace = {"id": 7, "uuid": "w1", "user_id": 42}
    kapitel = [
        {"id": i, "uuid": f"k{i}", "name": n, "position": i, "workspace_id": 7}
        for i, n in enumerate(vorhandene)
    ]

    monkeypatch.setattr(_chapters, "_require_workspace_manage", lambda *a, **k: workspace)
    monkeypatch.setattr(
        _chapters, "_load_workspace_source",
        lambda *a, **k: {"uuid": "q1", "workspace_id": 7},
    )
    monkeypatch.setattr(_chapters.db, "get_aia_chapters_by_workspace", lambda ws_id: kapitel)
    monkeypatch.setattr(_chapters.db, "count_aia_chapters", lambda ws_id: anzahl)
    monkeypatch.setattr(
        _chapters.db, "get_aia_chapter",
        lambda u: {"id": 1, "uuid": u, "name": "K", "position": 0,
                   "workspace_id": 99 if fremd else 7},
    )
    gerufen = {"create": [], "rename": [], "delete": [], "move": [], "assign": [], "move_source": []}
    monkeypatch.setattr(
        _chapters.db, "create_aia_chapter",
        lambda ws_id, u, n: gerufen["create"].append((ws_id, n))
        or {"uuid": u, "name": n, "position": 0},
    )
    monkeypatch.setattr(_chapters.db, "rename_aia_chapter", lambda u, n: gerufen["rename"].append((u, n)))
    monkeypatch.setattr(_chapters.db, "delete_aia_chapter", lambda u: gerufen["delete"].append(u))
    monkeypatch.setattr(_chapters.db, "move_aia_chapter", lambda u, d: gerufen["move"].append((u, d)))
    monkeypatch.setattr(_chapters.db, "set_aia_source_chapter", lambda u, cid: gerufen["assign"].append((u, cid)))
    monkeypatch.setattr(_chapters.db, "move_aia_source", lambda u, d: gerufen["move_source"].append((u, d)))
    monkeypatch.setattr(
        _chapters.db, "get_aia_sources_by_workspace",
        lambda ws_id: [{"uuid": "q2"}, {"uuid": "q1"}],
    )
    return gerufen


def _anlegen(name: str):
    return _chapters.create_chapter(
        workspace_uuid="w1",
        body=_chapters.ChapterBody(name=name),
        current_user={"user_id": 42},
        locale="de",
    )


def test_anlegen_gibt_uuid_name_und_position_zurueck(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    antwort = _anlegen("1 Einführung")

    assert set(antwort) == {"uuid", "name", "position"}
    assert gerufen["create"] == [(7, "1 Einführung")]


def test_anlegen_wirft_verbotene_zeichen_raus(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    _anlegen("a/b\\c\nd")

    assert gerufen["create"] == [(7, "abcd")]


def test_anlegen_lehnt_einen_leeren_namen_ab(monkeypatch):
    _route_vorbereiten(monkeypatch)

    with pytest.raises(HTTPException) as fehler:
        _anlegen("   ")

    assert fehler.value.status_code == 400


def test_anlegen_lehnt_einen_zu_langen_namen_ab(monkeypatch):
    _route_vorbereiten(monkeypatch)

    with pytest.raises(HTTPException) as fehler:
        _anlegen("x" * 101)

    assert fehler.value.status_code == 400


def test_anlegen_lehnt_einen_schon_vergebenen_namen_ab(monkeypatch):
    """Two chapters of the same name could not be told apart in the list."""
    _route_vorbereiten(monkeypatch, vorhandene=["1 Einführung"])

    with pytest.raises(HTTPException) as fehler:
        _anlegen("1 einführung")

    assert fehler.value.status_code == 409


def test_anlegen_hat_eine_obergrenze(monkeypatch):
    _route_vorbereiten(monkeypatch, anzahl=100)

    with pytest.raises(HTTPException) as fehler:
        _anlegen("noch eins")

    assert fehler.value.status_code == 400


def test_umbenennen_stoert_sich_nicht_am_eigenen_namen(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch, vorhandene=["Alt"])
    # k0 is exactly the chapter that gets renamed
    _chapters.rename_chapter(
        workspace_uuid="w1", chapter_uuid="k0",
        body=_chapters.ChapterBody(name="alt"),
        current_user={"user_id": 42}, locale="de",
    )

    assert gerufen["rename"] == [("k0", "alt")]


def test_umbenennen_lehnt_den_namen_eines_anderen_kapitels_ab(monkeypatch):
    _route_vorbereiten(monkeypatch, vorhandene=["Alt", "Neu"])

    with pytest.raises(HTTPException) as fehler:
        _chapters.rename_chapter(
            workspace_uuid="w1", chapter_uuid="k0",
            body=_chapters.ChapterBody(name="Neu"),
            current_user={"user_id": 42}, locale="de",
        )

    assert fehler.value.status_code == 409


def test_kapitel_aus_einem_fremden_kursraum_ist_nicht_zu_finden(monkeypatch):
    """404 instead of 403 so a foreign uuid is indistinguishable from an invented one."""
    _route_vorbereiten(monkeypatch, fremd=True)

    with pytest.raises(HTTPException) as fehler:
        _chapters.delete_chapter(
            workspace_uuid="w1", chapter_uuid="fremd",
            current_user={"user_id": 42}, locale="de",
        )

    assert fehler.value.status_code == 404


def test_verschieben_lehnt_eine_unsinnige_richtung_ab(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    with pytest.raises(HTTPException) as fehler:
        _chapters.move_chapter(
            workspace_uuid="w1", chapter_uuid="k1",
            body=_chapters.MoveChapterBody(direction="seitwaerts"),
            current_user={"user_id": 42}, locale="de",
        )

    assert fehler.value.status_code == 400
    assert gerufen["move"] == []


def test_zuordnen_setzt_die_interne_id_des_kapitels(monkeypatch):
    """The uuid goes outside, the column holds the id."""
    gerufen = _route_vorbereiten(monkeypatch)

    antwort = _chapters.set_source_chapter(
        workspace_uuid="w1", source_uuid="q1",
        body=_chapters.SetChapterBody(chapter_uuid="k1"),
        current_user={"user_id": 42}, locale="de",
    )

    assert gerufen["assign"] == [("q1", 1)]
    assert antwort == {"uuid": "q1", "chapter_uuid": "k1", "order": ["q2", "q1"]}


def test_zuordnen_ohne_kapitel_loest_die_zuordnung(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    antwort = _chapters.set_source_chapter(
        workspace_uuid="w1", source_uuid="q1",
        body=_chapters.SetChapterBody(chapter_uuid=None),
        current_user={"user_id": 42}, locale="de",
    )

    assert gerufen["assign"] == [("q1", None)]
    assert antwort["chapter_uuid"] is None


def test_zuordnen_in_ein_fremdes_kapitel_geht_nicht(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch, fremd=True)

    with pytest.raises(HTTPException) as fehler:
        _chapters.set_source_chapter(
            workspace_uuid="w1", source_uuid="q1",
            body=_chapters.SetChapterBody(chapter_uuid="fremd"),
            current_user={"user_id": 42}, locale="de",
        )

    assert fehler.value.status_code == 404
    assert gerufen["assign"] == []


def test_quelle_verschieben_gibt_die_neue_reihenfolge_zurueck(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    antwort = _chapters.move_source(
        workspace_uuid="w1", source_uuid="q1",
        body=_chapters.MoveChapterBody(direction="up"),
        current_user={"user_id": 42}, locale="de",
    )

    assert gerufen["move_source"] == [("q1", "up")]
    assert antwort == {"order": ["q2", "q1"]}


def test_quelle_verschieben_lehnt_eine_unsinnige_richtung_ab(monkeypatch):
    gerufen = _route_vorbereiten(monkeypatch)

    with pytest.raises(HTTPException) as fehler:
        _chapters.move_source(
            workspace_uuid="w1", source_uuid="q1",
            body=_chapters.MoveChapterBody(direction="seitwaerts"),
            current_user={"user_id": 42}, locale="de",
        )

    assert fehler.value.status_code == 400
    assert gerufen["move_source"] == []
