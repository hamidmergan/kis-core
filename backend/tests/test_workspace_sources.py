"""Prüft den Weg aus einem Workspace in die drei Dienste: Zugang, Auswahl, Lesen."""

import pytest
from fastapi import HTTPException

from src.services import workspace_sources as ws
from src.services.sources import MAX_TOTAL_CHARS
from src.services.source_reading import NoReadableText, Source


# ── Die Auswahl aus dem Formular ─────────────────────────────────────────────

def test_ids_kommen_in_der_reihenfolge_der_person_an():
    assert ws.parse_uuids('["c", "a", "b"]') == ["c", "a", "b"]


def test_eine_doppelte_id_zaehlt_einmal():
    assert ws.parse_uuids('["a", "b", "a"]') == ["a", "b"]


@pytest.mark.parametrize("roh", ["", "kein json", "{}", '"a"', "[1, 2]", '[""]'])
def test_unbrauchbare_eingaben_ergeben_keine_auswahl(roh):
    assert ws.parse_uuids(roh) == []


# ── Wer heran darf ───────────────────────────────────────────────────────────

class _Db:
    """Die paar Datenbankfragen, die dieses Modul stellt."""

    def __init__(self, workspace=None, enrolled=False, tutor=False, sources=()):
        self.workspace = workspace
        self.enrolled = enrolled
        self.tutor = tutor
        self.sources = list(sources)

    def get_aia_workspace(self, uuid):
        return self.workspace

    def is_student_enrolled(self, workspace_id, user_id):
        return self.enrolled

    def is_workspace_tutor(self, workspace_id, user_id):
        return self.tutor

    def get_aia_sources_by_workspace(self, workspace_id):
        return self.sources


def _raum(**kwargs):
    return {"id": 1, "uuid": "w1", "user_id": 7, "is_active": True, **kwargs}


def test_ein_unbekannter_raum_ist_nicht_zu_finden(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=None))
    with pytest.raises(HTTPException) as fehler:
        ws._workspace_or_raise("w1", 7, "de")
    assert fehler.value.status_code == 404


def test_wem_der_raum_gehoert_darf_heran(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum()))
    assert ws._workspace_or_raise("w1", 7, "de")["id"] == 1


def test_wer_eingeschrieben_ist_darf_heran(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(user_id=9), enrolled=True))
    assert ws._workspace_or_raise("w1", 7, "de")["id"] == 1


def test_ein_fremder_kommt_nicht_heran(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(user_id=9)))
    with pytest.raises(HTTPException) as fehler:
        ws._workspace_or_raise("w1", 7, "de")
    assert fehler.value.status_code == 403


def test_ein_gesperrter_raum_antwortet_mit_423(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(user_id=9, is_active=False), enrolled=True))
    with pytest.raises(HTTPException) as fehler:
        ws._workspace_or_raise("w1", 7, "de")
    assert fehler.value.status_code == 423


def test_die_tutorin_kommt_auch_in_den_gesperrten_raum(monkeypatch):
    monkeypatch.setattr(ws, "db",
                        _Db(workspace=_raum(user_id=9, is_active=False), enrolled=True, tutor=True))
    assert ws._workspace_or_raise("w1", 7, "de")["id"] == 1


# ── Dokument oder Abschrift ──────────────────────────────────────────────────

def test_eine_bekannte_endung_wird_als_dokument_gelesen(monkeypatch):
    gerufen = {}
    monkeypatch.setattr(ws, "_document", lambda q, name: gerufen.setdefault("name", name))
    ws._read_one({"filename": "Skript.pdf", "uuid": "q1", "file_path": "p"})
    assert gerufen == {"name": "Skript.pdf"}


@pytest.mark.parametrize("name", ["Vorlesung.mp4", "Tonspur.mp3", "Ein Video ohne Endung"])
def test_alles_andere_braucht_eine_abschrift(monkeypatch, name):
    gerufen = {}
    monkeypatch.setattr(ws, "_transcript", lambda q, n: gerufen.setdefault("name", n))
    ws._read_one({"filename": name, "uuid": "q1", "file_path": "p"})
    assert gerufen == {"name": name}


# ── Der ganze Weg ────────────────────────────────────────────────────────────

def _quelle(uuid, name, status="ready"):
    return {"uuid": uuid, "filename": name, "status": status, "file_path": f"s/{uuid}.pdf"}


def _lies(monkeypatch, *, sources, auswahl, hoechstens=5, text="Ein Satz."):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(), sources=sources))
    monkeypatch.setattr(ws, "_read_one",
                        lambda q: Source(dateiname=q["filename"], fassung="f", text=text,
                                         stuecke=[], seiten=1))
    return ws.read_workspace("w1", auswahl, user_id=7, locale="de",
                             hoechstens=hoechstens, schluessel="podcast")


def test_die_quellen_kommen_in_der_reihenfolge_der_person(monkeypatch):
    gelesen = _lies(monkeypatch,
                    sources=[_quelle("a", "A.pdf"), _quelle("b", "B.pdf")],
                    auswahl=["b", "a"])
    assert [q.dateiname for q in gelesen] == ["B.pdf", "A.pdf"]


def test_ohne_auswahl_gibt_es_nichts_zu_tun(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum()))
    with pytest.raises(HTTPException) as fehler:
        ws.read_workspace("w1", [], user_id=7, locale="de", hoechstens=5, schluessel="podcast")
    assert fehler.value.status_code == 422


def test_mehr_als_erlaubt_wird_abgelehnt(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum()))
    with pytest.raises(HTTPException) as fehler:
        ws.read_workspace("w1", ["a", "b"], user_id=7, locale="de",
                          hoechstens=1, schluessel="podcast")
    assert fehler.value.status_code == 422


def test_eine_quelle_aus_einem_anderen_raum_gibt_es_hier_nicht(monkeypatch):
    with pytest.raises(HTTPException) as fehler:
        _lies(monkeypatch, sources=[_quelle("a", "A.pdf")], auswahl=["fremd"])
    assert fehler.value.status_code == 404


def test_eine_quelle_die_noch_arbeitet_haelt_den_start_an(monkeypatch):
    with pytest.raises(HTTPException) as fehler:
        _lies(monkeypatch, sources=[_quelle("a", "A.pdf", status="indexing")], auswahl=["a"])
    assert fehler.value.status_code == 409


def test_zu_viel_text_zusammen_wird_abgelehnt(monkeypatch):
    with pytest.raises(HTTPException) as fehler:
        _lies(monkeypatch, sources=[_quelle("a", "A.pdf"), _quelle("b", "B.pdf")],
              auswahl=["a", "b"], text="x" * (MAX_TOTAL_CHARS // 2 + 1))
    assert fehler.value.status_code == 422


def test_eine_quelle_ohne_text_wird_benannt(monkeypatch):
    monkeypatch.setattr(ws, "db", _Db(workspace=_raum(), sources=[_quelle("a", "A.pdf")]))

    def _leer(q):
        raise NoReadableText(q["filename"])

    monkeypatch.setattr(ws, "_read_one", _leer)
    with pytest.raises(HTTPException) as fehler:
        ws.read_workspace("w1", ["a"], user_id=7, locale="de", hoechstens=5,
                          schluessel="podcast")
    assert fehler.value.status_code == 422
    assert "A.pdf" in fehler.value.detail
