"""Ein abgeschalteter Workspace sagt den Lernenden, dass er zu ist.

Der Schalter im Kursraum verspricht "fuer Studierende gesperrt". Eingeloest hat
er das nie: er filterte nur zwei Listenabfragen. Der Kurs verschwand also
kommentarlos aus der Liste, waehrend ein Lesezeichen weiterhin voll
hineinfuehrte, samt Chat. Beides falsch herum.

Ab jetzt gilt in beide Richtungen dasselbe. Die Karte bleibt in der Liste
stehen und sagt, dass gerade zu ist. Der direkte Weg hinein wird abgelehnt, und
zwar mit 423 statt 403: mit den Rechten dieser Person ist alles in Ordnung, es
ist nur zu. Nur daran kann die Oberflaeche den Hinweis vom Rauswurf
unterscheiden.

Eigentuemer und Tutoren kommen weiter hinein. Sie fuehren den Raum, und
abgeschaltet ist er genau dann, wenn sie ihn herrichten.

Wer ueber einen Link auf einen abgeschalteten Workspace stoesst, darf beitreten
und bekommt den Hinweis. Ein abgelehnter Beitritt haette die Person spaeter
erneut auf Linksuche geschickt, so schaltet die Karte einfach frei.
"""

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import _helpers
from src.features.ai_assistant.routes import workspaces as routes
from src.i18n import t

MENTOR = 1
TUTOR = 2
LERNENDER = 3
FREMDER = 4

OFFEN = {"id": 7, "uuid": "w-1", "title": "Kurs", "user_id": MENTOR, "is_active": True}
ZU = {**OFFEN, "is_active": False}


@pytest.fixture
def workspace_mit(monkeypatch):
    """Klinkt die Datenbank aus: welcher Raum, wer Tutor, wer eingeschrieben."""
    def einrichten(workspace, tutoren=frozenset(), eingeschrieben=frozenset()):
        monkeypatch.setattr(_helpers.db, "get_aia_workspace", lambda uuid: workspace)
        monkeypatch.setattr(
            _helpers.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )
        monkeypatch.setattr(
            _helpers.db, "is_student_enrolled", lambda ws_id, uid: uid in eingeschrieben
        )
    return einrichten


# --- Der Weg hinein -------------------------------------------------------

def test_lernender_kommt_nicht_in_den_abgeschalteten_raum(workspace_mit):
    """Das Lesezeichen lief frueher daran vorbei, der Chat antwortete weiter."""
    workspace_mit(ZU, eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_access("w-1", LERNENDER)
    assert fehler.value.status_code == 423


def test_die_absage_sagt_woran_es_liegt(workspace_mit):
    """Ohne eigenen Text stuende dort 'Kein Zugriff', und das stimmt hier nicht."""
    workspace_mit(ZU, eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_access("w-1", LERNENDER, locale="de")
    assert fehler.value.detail == t("workspace.inactive", "de")
    assert fehler.value.detail != t("workspace.accessDenied", "de")


def test_eigentuemer_kommt_auch_im_abgeschalteten_raum_hinein(workspace_mit):
    workspace_mit(ZU)
    assert _helpers._require_workspace_access("w-1", MENTOR) == ZU


def test_tutor_kommt_auch_im_abgeschalteten_raum_hinein(workspace_mit):
    """Abgeschaltet ist der Raum genau dann, wenn Tutoren ihn herrichten."""
    workspace_mit(ZU, tutoren={TUTOR}, eingeschrieben={TUTOR})
    assert _helpers._require_workspace_access("w-1", TUTOR) == ZU


def test_offener_raum_bleibt_offen(workspace_mit):
    workspace_mit(OFFEN, eingeschrieben={LERNENDER})
    assert _helpers._require_workspace_access("w-1", LERNENDER) == OFFEN


def test_fremder_erfaehrt_weiterhin_nur_kein_zugriff(workspace_mit):
    """423 wuerde einem Unbeteiligten verraten, dass es diesen Raum gibt."""
    workspace_mit(ZU)
    with pytest.raises(HTTPException) as fehler:
        _helpers._require_workspace_access("w-1", FREMDER)
    assert fehler.value.status_code == 403


# --- Wer den Raum offen sieht ---------------------------------------------

@pytest.fixture
def tutoren(monkeypatch):
    def einrichten(namen=frozenset()):
        monkeypatch.setattr(
            routes.db, "is_workspace_tutor", lambda ws_id, uid: uid in namen
        )
    return einrichten


def test_offenheit_haengt_an_der_person_nicht_nur_am_schalter(tutoren):
    tutoren({TUTOR})
    assert routes._is_open_for(ZU, LERNENDER) is False
    assert routes._is_open_for(ZU, MENTOR) is True
    assert routes._is_open_for(ZU, TUTOR) is True
    assert routes._is_open_for(OFFEN, LERNENDER) is True


# --- Der Weg ueber den Link -----------------------------------------------

@pytest.fixture
def beitritt(monkeypatch):
    """Beitritt ohne Datenbank, mit Protokoll ueber jede Einschreibung."""
    def einrichten(workspace, tutoren=frozenset()):
        protokoll = []
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (workspace, {"id": 22, "expires_at": None}),
        )
        monkeypatch.setattr(routes.db, "get_enrollment", lambda *a, **k: None)
        monkeypatch.setattr(
            routes.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )

        def enroll_student(workspace_id, user_id, enrolled_until, link_id=None, role="student"):
            protokoll.append((workspace_id, user_id))
            return 123

        monkeypatch.setattr(routes.db, "enroll_student", enroll_student)
        return protokoll
    return einrichten


def _beitreten(user_id=LERNENDER):
    return asyncio.run(
        routes.enroll(schemas.EnrollBody(enroll_code="ein-link"), {"user_id": user_id}, "de")
    )


def test_beitritt_in_den_abgeschalteten_raum_klappt_und_sagt_es(beitritt):
    """Ablehnen haette die Person spaeter erneut auf Linksuche geschickt."""
    protokoll = beitritt(ZU)
    ergebnis = _beitreten()
    assert protokoll == [(ZU["id"], LERNENDER)]
    assert ergebnis["enrollment_id"] == 123
    assert ergebnis["is_open"] is False


def test_beitritt_in_den_offenen_raum_meldet_offen(beitritt):
    beitritt(OFFEN)
    assert _beitreten()["is_open"] is True


def test_eigener_link_fuehrt_den_eigentuemer_auch_im_zu_raum_hinein(beitritt):
    beitritt(ZU)
    ergebnis = _beitreten(user_id=MENTOR)
    assert ergebnis["enrollment_id"] is None
    assert ergebnis["is_open"] is True


def test_vorschau_sagt_vorher_ob_der_raum_offen_ist(monkeypatch):
    """Sonst stuende dort nur ein Knopf, der ins Nichts fuehrt."""
    monkeypatch.setattr(
        routes.db, "get_workspace_by_access_link_code",
        lambda code: (ZU, {"id": 22, "expires_at": None}),
    )
    monkeypatch.setattr(routes.db, "is_workspace_tutor", lambda ws_id, uid: False)
    vorschau = asyncio.run(routes.preview_access_link("ein-link", {"user_id": LERNENDER}, "de"))
    assert vorschau["title"] == ZU["title"]
    assert vorschau["is_open"] is False


# --- Die Karte in der Liste -----------------------------------------------

def test_abgeschalteter_raum_faellt_nicht_mehr_aus_der_liste():
    """Verschwindet die Zeile, gibt es nichts, woran der Hinweis haengen koennte."""
    from src.features.ai_assistant.repository import workspaces as repo
    quelle = inspect.getsource(repo.get_aia_workspaces_for_member)
    assert "m.is_active = TRUE" not in quelle


def test_die_zeile_bringt_ihren_zustand_mit():
    """Die Liste baut den Hinweis aus is_active, das Feld muss also mitkommen."""
    from src.features.ai_assistant.routes import workspaces as routes_modul
    quelle = inspect.getsource(routes_modul.list_workspaces)
    assert '"is_active": m["is_active"]' in quelle
