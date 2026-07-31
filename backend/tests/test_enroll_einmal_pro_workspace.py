"""Wer schon in einem Workspace ist, schreibt sich ueber keinen Link erneut ein.

Ein Kurs verschickt im Laufe eines Semesters mehrere Einschreibelinks, etwa
weil der erste ablief oder weil eine zweite Gruppe dazukam. Die Pruefung hing
frueher am Link statt am Workspace, deshalb legte jeder neue Link eine zweite
Einschreibung an, und derselbe Kurs stand doppelt in der Liste.

Der zweite Link ist ab jetzt eine reine Weiterleitung: keine neue Einschreibung,
und das Ablaufdatum der bestehenden bleibt unberuehrt. Sonst waere ein
weitergeleiteter Link ein stiller Verlaengerer fuer Leute, deren Zugang enden
sollte.

Darunter liegt eine Regel in der Tabelle selbst, die hoechstens eine Zeile je
Person und Workspace zulaesst. Die alte Regel hing am Link und lief ins Leere,
sobald der Link geloescht wurde: dann steht dort nichts mehr, und nichts ist in
der Datenbank nie gleich nichts.
"""

import asyncio
import inspect

import pytest

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import workspaces as routes

MENTOR = 1
LERNENDER = 3

WORKSPACE = {"id": 7, "uuid": "w-1", "title": "Kurs", "user_id": MENTOR}
LINK_ALT = {"id": 11, "expires_at": None}
LINK_NEU = {"id": 22, "expires_at": None}
EINSCHREIBUNG = {"id": 99, "workspace_id": 7, "user_id": LERNENDER, "link_id": LINK_ALT["id"]}


@pytest.fixture
def beitritt(monkeypatch):
    """Klinkt die Datenbank aus und protokolliert jeden Schreibzugriff."""
    protokoll = {"eingeschrieben": [], "gesucht": []}

    def einrichten(bestehend):
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (WORKSPACE, LINK_NEU),
        )

        def get_enrollment(workspace_id, user_id, link_id=None):
            # Wie die echte Abfrage: nach Link gefragt, antwortet sie nur fuer
            # genau diesen Link. Genau daran ging die alte Pruefung vorbei.
            protokoll["gesucht"].append((workspace_id, user_id, link_id))
            if bestehend is None:
                return None
            if link_id is not None and link_id != bestehend["link_id"]:
                return None
            return bestehend

        def enroll_student(workspace_id, user_id, enrolled_until, link_id=None, role="student"):
            protokoll["eingeschrieben"].append(
                (workspace_id, user_id, enrolled_until, link_id, role)
            )
            return 123

        monkeypatch.setattr(routes.db, "get_enrollment", get_enrollment)
        monkeypatch.setattr(routes.db, "enroll_student", enroll_student)
        return protokoll

    return einrichten


def _beitreten(user_id=LERNENDER):
    return asyncio.run(
        routes.enroll(
            schemas.EnrollBody(enroll_code="neuer-link"),
            {"user_id": user_id},
            "de",
        )
    )


def test_zweiter_link_schreibt_nicht_erneut_ein(beitritt):
    protokoll = beitritt(bestehend=EINSCHREIBUNG)
    ergebnis = _beitreten()
    assert protokoll["eingeschrieben"] == []
    assert ergebnis["workspace_uuid"] == "w-1"
    assert ergebnis["enrollment_id"] == EINSCHREIBUNG["id"]


def test_gesucht_wird_nach_workspace_nicht_nach_link(beitritt):
    """Die Frage lautet 'schon in diesem Kurs', nicht 'schon ueber diesen Link'."""
    protokoll = beitritt(bestehend=EINSCHREIBUNG)
    _beitreten()
    assert protokoll["gesucht"] == [(WORKSPACE["id"], LERNENDER, None)]


def test_bestehendes_ablaufdatum_bleibt_unangetastet(beitritt):
    """Ein weitergeleiteter Link darf keinen auslaufenden Zugang verlaengern."""
    beitritt(bestehend=EINSCHREIBUNG)
    _beitreten()
    assert EINSCHREIBUNG["link_id"] == LINK_ALT["id"]
    assert not hasattr(routes.db, "extend_enrollment")


def test_erster_beitritt_schreibt_weiterhin_ein(beitritt):
    protokoll = beitritt(bestehend=None)
    ergebnis = _beitreten()
    assert protokoll["eingeschrieben"] == [
        (WORKSPACE["id"], LERNENDER, LINK_NEU["expires_at"], LINK_NEU["id"], "student")
    ]
    assert ergebnis["enrollment_id"] == 123


def test_eigentuemer_bleibt_eigentuemer(beitritt):
    """Der eigene Link fuehrt zurueck in den Kurs, ohne den Besitzer einzuschreiben."""
    protokoll = beitritt(bestehend=None)
    ergebnis = _beitreten(user_id=MENTOR)
    assert protokoll["eingeschrieben"] == []
    assert ergebnis["enrollment_id"] is None


# --- Die Regel in der Tabelle ---------------------------------------------

def _sql_von_enroll_student(monkeypatch):
    from src.features.ai_assistant.repository import enrollments

    gespeichert = {}

    class FakeCursor:
        def execute(self, sql, params):
            gespeichert["sql"] = " ".join(sql.split())
        def fetchone(self):
            return (1,)
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
    enrollments.enroll_student(7, LERNENDER, None, link_id=22)
    return gespeichert["sql"]


def test_einfuegen_weicht_der_person_aus_nicht_dem_link(monkeypatch):
    """Trifft das ON CONFLICT die falsche Regel, gibt es beim Rennen einen 500er.

    Zwei gleichzeitig angeklickte Links kommen beide an der Pruefung vorbei. Nur
    wenn das Einfuegen auf dieselbe Regel zeigt wie die Tabelle, wird daraus ein
    stilles Nichtstun statt eines Serverfehlers.
    """
    sql = _sql_von_enroll_student(monkeypatch)
    assert "ON CONFLICT (workspace_id, user_id) DO NOTHING" in sql


def test_tabelle_erlaubt_nur_eine_zeile_je_person():
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "UNIQUE (workspace_id, user_id)" in quelle
    assert "UNIQUE (workspace_id, user_id, link_id)" not in quelle


def test_alte_regel_wird_abgeraeumt():
    """Sonst bliebe die zahnlose Link-Regel als Index liegen."""
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "DROP CONSTRAINT IF EXISTS aia_enrollments_workspace_id_user_id_link_id_key" in quelle
    assert "aia_enrollments_workspace_id_user_id_key" in quelle


def test_bestehende_doppel_werden_vorher_zusammengefuehrt():
    """Ohne Aufraeumen liesse sich die Regel auf Bestandsdaten gar nicht setzen.

    Die aelteste Einschreibung bleibt, ihre Nachrichten behaelt sie, die
    Nachrichten der spaeteren wandern mit. Sonst haengen Chats an einer Zeile,
    die es gleich nicht mehr gibt.
    """
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "UPDATE aia_messages" in quelle
    assert "DELETE FROM aia_enrollments" in quelle
