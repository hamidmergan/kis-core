"""Tutoren verwalten einen fremden Workspace wie sein Eigentuemer, ausser einladen.

Ein Mentor schickt allen denselben Einschreibelink. Aus der Teilnehmerliste
befoerdert er dann einzelne, namentlich bekannte Personen zu Tutoren. Es gibt
bewusst keinen Link, der Rechte verteilt: ein solcher Link waere ein Passwort,
das sich durch simples Weiterleiten vermehrt, ohne dass es jemand merkt.

Einladen bleibt deshalb allein beim Eigentuemer, sowohl das Anlegen von Links
als auch das Befoerdern. Der Systemrang (staff, admin, user) spielt nirgends
eine Rolle, weder zugunsten noch zulasten.

Geprueft wird die Trennung der beiden Zugriffspruefungen und der Ablageort
hochgeladener Dateien. Letzteres ist der stille Fallstrick: der Pfad enthaelt
eine Nutzer-ID, und waere das die des Hochladenden, zerfielen die Dateien eines
Workspace auf mehrere Ordner.
"""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _helpers

MENTOR = 1
TUTOR = 2
LERNENDER = 3
FREMDER = 4

WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": MENTOR}


@pytest.fixture
def workspace_mit(monkeypatch):
    """Klinkt Datenbankzugriffe aus und legt fest, wer Tutor ist."""
    def einrichten(tutoren: set[int], eingeschrieben: set[int] = frozenset()):
        monkeypatch.setattr(_helpers.db, "get_aia_workspace", lambda uuid: WORKSPACE)
        monkeypatch.setattr(
            _helpers.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )
        monkeypatch.setattr(
            _helpers.db, "is_student_enrolled", lambda ws_id, uid: uid in eingeschrieben
        )
    return einrichten


# --- Wer darf verwalten ---------------------------------------------------

def test_eigentuemer_darf_verwalten(workspace_mit):
    workspace_mit(tutoren=set())
    assert _helpers._require_workspace_manage("w-1", MENTOR) == WORKSPACE


def test_tutor_darf_verwalten(workspace_mit):
    workspace_mit(tutoren={TUTOR})
    assert _helpers._require_workspace_manage("w-1", TUTOR) == WORKSPACE


def test_lernender_darf_nicht_verwalten(workspace_mit):
    """Eingeschrieben sein reicht nicht, sonst duerfte jeder Kursteilnehmer loeschen."""
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_manage("w-1", LERNENDER)
    assert fehler.value.status_code == 403


def test_fremder_darf_nicht_verwalten(workspace_mit):
    workspace_mit(tutoren=set())
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_manage("w-1", FREMDER)
    assert fehler.value.status_code == 403


def test_unbekannter_workspace_ist_404(monkeypatch):
    monkeypatch.setattr(_helpers.db, "get_aia_workspace", lambda uuid: None)
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_manage("gibtsnicht", MENTOR)
    assert fehler.value.status_code == 404


def test_lernender_darf_weiterhin_lesen(workspace_mit):
    """Die Lesepruefung bleibt unberuehrt, sonst waere der Kurs fuer alle zu."""
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER})
    assert _helpers._require_workspace_access("w-1", LERNENDER) == WORKSPACE


def test_pruefung_kennt_den_rang_gar_nicht():
    """Die Pruefung nimmt nur eine Nutzer-ID entgegen, keine Rolle und keine Rechte.

    Damit kann kein staff- oder admin-Konto ueber seinen Rang in einen fremden
    Workspace hineinregieren. Waere hier je ein Rollenargument, faellt es auf.
    """
    import inspect
    parameter = set(inspect.signature(_helpers._require_workspace_manage).parameters)
    assert parameter == {"workspace_uuid", "user_id", "locale"}


def test_gleiche_person_gleiche_antwort_egal_welcher_rang(workspace_mit):
    """Zwei Konten, gleiche Beziehung zum Workspace, gleiches Ergebnis.

    Der Rang steckt weder im Aufruf noch in der Antwort, also muss ein staff-
    Konto ohne Tutor-Einschreibung genauso scheitern wie ein Studierendenkonto.
    """
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER, FREMDER})
    for konto in (LERNENDER, FREMDER):
        with pytest.raises(HTTPException) as fehler:
            _helpers._require_workspace_manage("w-1", konto)
        assert fehler.value.status_code == 403


# --- Was allein dem Eigentuemer bleibt ------------------------------------

def test_tutor_darf_verwalten_aber_nicht_das_unumkehrbare(workspace_mit):
    """Der Tutor verwaltet alles, ausser den Workspace loeschen und befoerdern.

    Loeschen ist nicht rueckholbar, und wer befoerdern kann, vergroessert den
    Kreis der Leute mit Vollrechten, ohne dass der Eigentuemer es merkt.
    Einladen dagegen ist gewoehnliche Tutorenarbeit und deshalb erlaubt.
    """
    workspace_mit(tutoren={TUTOR})
    assert _helpers._require_workspace_manage("w-1", TUTOR) == WORKSPACE
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_owner("w-1", TUTOR)
    assert fehler.value.status_code == 403


def test_eigentuemer_darf_auch_das_unumkehrbare(workspace_mit):
    workspace_mit(tutoren={TUTOR})
    assert _helpers._require_workspace_owner("w-1", MENTOR) == WORKSPACE


def test_loeschroute_haengt_an_der_eigentuemerpruefung():
    """Sonst koennte ein Tutor den Workspace samt allem wegwerfen."""
    import inspect
    from src.features.ai_assistant.routes import workspaces as routes
    quelle = inspect.getsource(routes.delete_workspace)
    assert "_require_workspace_owner" in quelle
    assert "_require_workspace_manage" not in quelle


def test_beitritt_immer_als_lernender(monkeypatch):
    """Jeder Link schreibt als Lernender ein, egal welcher.

    Damit es keinen Link geben kann, dessen Weiterleitung Rechte verschenkt.
    """
    from src.features.ai_assistant.repository import enrollments

    gespeichert = {}

    class FakeCursor:
        def execute(self, sql, params):
            gespeichert["sql"] = sql
            gespeichert["params"] = params
        def fetchone(self):
            return (99,)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self, *a, **k):
            return FakeCursor()
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(enrollments, "get_connection", lambda: FakeConn())

    enrollments.enroll_student(7, LERNENDER, None, link_id=6)
    assert gespeichert["params"][-1] == "student"


def test_befoerdern_erfasst_alle_einschreibungen(monkeypatch):
    """Wer ueber zwei Links drin ist, wird als Person befoerdert, nicht je Link."""
    from src.features.ai_assistant.repository import enrollments

    gespeichert = {}

    class FakeCursor:
        rowcount = 2
        def execute(self, sql, params):
            gespeichert["sql"] = " ".join(sql.split())
            gespeichert["params"] = params
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self, *a, **k):
            return FakeCursor()
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(enrollments, "get_connection", lambda: FakeConn())

    geaendert = enrollments.set_participant_role(7, TUTOR, "tutor")
    assert geaendert == 2
    assert "link_id" not in gespeichert["sql"]
    assert gespeichert["params"] == ("tutor", 7, TUTOR)


# --- Ablageort hochgeladener Dateien --------------------------------------

def test_datei_landet_beim_eigentuemer(lokal):
    """Laedt der Tutor hoch, liegt die Datei trotzdem im Ordner des Mentors."""
    from src import storage

    schluessel = storage.aia_source_key(MENTOR, "w-1", "q1", ".pdf")
    assert f"users/{MENTOR}/" in schluessel
    assert f"users/{TUTOR}/" not in schluessel

    # Gegenprobe: mit der ID des Hochladenden waere es ein zweiter Ordner,
    # und das Loeschen des Workspace wuerde ihn nicht mitnehmen.
    falsch = storage.aia_source_key(TUTOR, "w-1", "q1", ".pdf")
    assert falsch != schluessel
    assert storage.aia_workspace_prefix(MENTOR, "w-1") not in falsch
