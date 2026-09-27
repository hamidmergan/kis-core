"""A second link is a redirect, not a second enrollment."""

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
    """Stubs out the database and logs every write."""
    protokoll = {"eingeschrieben": [], "gesucht": []}

    def einrichten(bestehend):
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (WORKSPACE, LINK_NEU),
        )

        def get_enrollment(workspace_id, user_id, link_id=None):
            # Like the real query: asked by link, it answers only for that link.
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
    return (
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
    """The question is 'already in this course', not 'already through this link'."""
    protokoll = beitritt(bestehend=EINSCHREIBUNG)
    _beitreten()
    assert protokoll["gesucht"] == [(WORKSPACE["id"], LERNENDER, None)]


def test_bestehendes_ablaufdatum_bleibt_unangetastet(beitritt):
    """A redirected link must not extend an expiring access."""
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
    """Your own link leads back into the course without enrolling the owner."""
    protokoll = beitritt(bestehend=None)
    ergebnis = _beitreten(user_id=MENTOR)
    assert protokoll["eingeschrieben"] == []
    assert ergebnis["enrollment_id"] is None


# --- the rule in the table ------------------------------------------------

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
    """The insert has to point at the same rule as the table."""
    sql = _sql_von_enroll_student(monkeypatch)
    assert "ON CONFLICT (workspace_id, user_id) DO NOTHING" in sql


def test_tabelle_erlaubt_nur_eine_zeile_je_person():
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "UNIQUE (workspace_id, user_id)" in quelle
    assert "UNIQUE (workspace_id, user_id, link_id)" not in quelle


def test_alte_regel_wird_abgeraeumt():
    """Otherwise the toothless link rule would stay behind as an index."""
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "DROP CONSTRAINT IF EXISTS aia_enrollments_workspace_id_user_id_link_id_key" in quelle
    assert "aia_enrollments_workspace_id_user_id_key" in quelle


def test_bestehende_doppel_werden_vorher_zusammengefuehrt():
    """The oldest enrollment stays, the messages move along."""
    from src.core.db import schema
    quelle = inspect.getsource(schema)
    assert "UPDATE aia_messages" in quelle
    assert "DELETE FROM aia_enrollments" in quelle
