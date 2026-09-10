"""Demo access: the admin flag and the two routes on the start page."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": 1, "email": "admin@th-luebeck.de", "role": "admin"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@th-luebeck.de")

    from src.app import app
    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_der_haken_setzt_die_markierung(client):
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 7}), \
         patch("src.routes.admin.users.db.set_user_demo") as setzen:
        r = client.post("/admin/users/7/demo", json={"is_demo": True})
    assert r.status_code == 200
    assert r.json()["is_demo"] is True
    setzen.assert_called_once_with(7, True)


def test_ein_unbekanntes_konto_gibt_vierhundertvier(client):
    with patch("src.routes.admin.users.db.get_user_by_id", return_value=None), \
         patch("src.routes.admin.users.db.set_user_demo") as setzen:
        r = client.post("/admin/users/999/demo", json={"is_demo": True})
    assert r.status_code == 404
    setzen.assert_not_called()


def _kurs(ws_id, uuid, joined=False, owned=False, via_demo=None,
           titel="Sustainable Energy Systems"):
    return {
        "id": ws_id, "uuid": uuid, "title": titel,
        "description": "Modul B.Eng.", "source_count": 7, "joined": joined,
        "via_demo": joined if via_demo is None else via_demo, "owned": owned,
    }


def test_die_liste_reicht_nur_die_sichtbaren_felder_durch(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]):
        r = client.get("/ai-assistant/demo/workspaces")
    assert r.status_code == 200
    assert r.json() == [{
        "uuid": "w5", "title": "Sustainable Energy Systems",
        "description": "Modul B.Eng.", "source_count": 7, "joined": False,
        "via_demo": False, "owned": False,
    }]
    # The internal id must not leave the route.
    assert "id" not in r.json()[0]


def test_ohne_angabe_wird_in_alle_offenen_eingeschrieben(client):
    kurse = [_kurs(5, "w5"), _kurs(6, "w6", joined=True), _kurs(7, "w7")]
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces", return_value=kurse), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student",
               side_effect=[11, 12]) as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.status_code == 200
    assert r.json()["joined"] == ["w5", "w7"]
    assert einschreiben.call_count == 2
    einschreiben.assert_any_call(5, 1, None, via_demo=True)


def test_mit_angabe_wird_nur_dieser_eine_eingeschrieben(client):
    kurse = [_kurs(5, "w5"), _kurs(7, "w7")]
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces", return_value=kurse), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student", return_value=11) as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={"workspace_uuid": "w7"})
    assert r.json()["joined"] == ["w7"]
    einschreiben.assert_called_once_with(7, 1, None, via_demo=True)


def test_ein_fremder_kurs_gibt_vierhundertvier(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={"workspace_uuid": "fremd"})
    assert r.status_code == 404
    einschreiben.assert_not_called()


def test_zweimal_beitreten_legt_nichts_neues_an(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.json()["joined"] == []
    einschreiben.assert_not_called()


def test_verlassen_loescht_die_einschreibung(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=True) as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.status_code == 200
    assert r.json()["left"] is True
    loeschen.assert_called_once_with(5, 1)


def test_verlassen_geht_nur_bei_demo_kursen(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment") as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "fremd"})
    assert r.status_code == 404
    loeschen.assert_not_called()


def test_verlassen_ohne_einschreibung_bleibt_ruhig(client):
    """The owner has no enrollment, that is not an error."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=False):
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.status_code == 200
    assert r.json()["left"] is False


def test_der_haken_weg_raeumt_die_demo_einschreibungen_ab(client):
    """Whoever loses the flag loses their demo participants from the course."""
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 7}), \
         patch("src.routes.admin.users.db.set_user_demo", return_value=[7]), \
         patch("src.routes.admin.users.db.delete_demo_enrollments_of_owner",
               return_value=3) as abraeumen:
        r = client.post("/admin/users/7/demo", json={"is_demo": False})
    assert r.status_code == 200
    abraeumen.assert_called_once_with(7)


def test_das_vorige_demo_konto_wird_mit_abgeraeumt(client):
    """On switching, the old account loses the flag and with it its participants."""
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 9}), \
         patch("src.routes.admin.users.db.set_user_demo", return_value=[7]), \
         patch("src.routes.admin.users.db.delete_demo_enrollments_of_owner",
               return_value=2) as abraeumen:
        r = client.post("/admin/users/9/demo", json={"is_demo": True})
    assert r.status_code == 200
    abraeumen.assert_called_once_with(7)


def test_beitreten_merkt_sich_den_weg_ueber_die_demo(client):
    """Otherwise it would be impossible to say later which enrollment may be cleared."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student",
               return_value=11) as einschreiben:
        client.post("/ai-assistant/demo/enroll", json={})
    einschreiben.assert_called_once_with(5, 1, None, via_demo=True)


def test_der_eigentuemer_tritt_seinem_eigenen_kurs_nicht_bei(client):
    """They already own the course, an enrollment would be pointless."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", owned=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.json()["joined"] == []
    einschreiben.assert_not_called()


def test_verlassen_fasst_eine_echte_einschreibung_nicht_an(client):
    """Whoever is in through a real link stays in."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True, via_demo=False)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=False) as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.json()["left"] is False
    # The query itself protects: it only touches rows with via_demo.
    loeschen.assert_called_once_with(5, 1)


# ─── Inhalte fuer den Rundgang ────────────────────────────────────────────────

_QUELLEN = [
    {"id": 41, "uuid": "u-pdf", "filename": "DEMO_Skript_Kapitel_1_Grundlagen.pdf"},
    {"id": 42, "uuid": "u-video", "filename": "DEMO_Vorlesung_01_Grundlagen.mp4"},
    # A third file, neither the script nor the video: proves the schedule job
    # takes every material, not just the two the tour itself opens.
    {"id": 43, "uuid": "u-folien", "filename": "DEMO_Folien_01_Grundlagen.pdf"},
]


def test_rundgang_legt_eintrag_und_notiz_an(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace",
               return_value=_QUELLEN), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.bulk_create_glossary_entries",
               return_value=[{"id": 1, "term_de": "magische Dreieck"}]) as glossar, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_notes",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_aia_note") as notiz, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_schedule_entries",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_schedule_job",
               return_value={"id": 99}) as job, \
         patch("src.tasks.aia_tasks.run_generate_schedule.delay") as absetzen, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=True):
        r = client.post("/ai-assistant/demo/tour-content", json={"workspace_uuid": "w5"})

    assert r.json() == {"glossary": 1, "notes": 1, "tools": 0}
    assert glossar.call_args[0][0] == 41
    # Der Beleg zeigt auf das Video und traegt die Zeitmarke, sonst springt nichts zurueck.
    assert "[Q1:u-video, 01:04 |" in notiz.call_args[0][2]
    # Alle drei Quellen, nicht nur Skript und Video.
    assert job.call_args[0][2] == ["u-pdf", "u-video", "u-folien"]
    absetzen.assert_called_once_with(99, 5, 1, ["u-pdf", "u-video", "u-folien"])


def test_rundgang_legt_nichts_zweimal_an(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace",
               return_value=_QUELLEN), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.bulk_create_glossary_entries",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_notes",
               return_value=[{"title": "Was ein Projekt ausmacht"}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_aia_note") as notiz, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_schedule_entries",
               # Der Zeitplan steht schon, ein zweiter Lauf darf ihn nicht anfassen.
               return_value=[{"id": 1, "title": "Vorlesung"}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_schedule_job") as job, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=True):
        r = client.post("/ai-assistant/demo/tour-content", json={"workspace_uuid": "w5"})

    assert r.json() == {"glossary": 0, "notes": 0, "tools": 0}
    notiz.assert_not_called()
    job.assert_not_called()


# ─── Werkzeug-Beispiele kopieren ───────────────────────────────────────────────

from src.features.ai_assistant.routes._demo_tour_content import _lege_werkzeug_beispiele_an

_KARTEIKARTEN_VORLAGEN = [{"id": 71, "status": "ready"}, {"id": 72, "status": "ready"}]
_QUIZ_VORLAGEN = [{"id": 81, "status": "ready"}]


def _voller_set(id, mode="source"):
    return {
        "id": id, "title": f"Set {id}", "mode": mode, "source_uuid": "u-pdf",
        "items": [{"front": "F", "back": "B"}, {"front": "F2", "back": "B2"}],
    }


def _neuer_set(id):
    """What create_exercise_set hands back: the fresh set with its new item ids."""
    return {
        "id": id, "title": f"Set {id}", "tool": "karteikarten",
        "items": [{"id": id * 10 + 1}, {"id": id * 10 + 2}],
    }


def test_werkzeuge_kopiert_bis_zu_zwei_je_tool(client):
    neue_ids = iter([201, 202, 203])
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=False), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_workspace_by_id",
               return_value={"id": 5, "user_id": 15}), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_exercise_sets",
               side_effect=lambda ws, uid, tool=None: (
                   _KARTEIKARTEN_VORLAGEN if tool == "karteikarten" else _QUIZ_VORLAGEN
               )), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_exercise_set_with_items",
               side_effect=lambda sid: _voller_set(sid)) as voll, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_exercise_set",
               side_effect=lambda *a, **k: _neuer_set(next(neue_ids))) as erstellen, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_all_aia_mindmaps",
               return_value=[{"id": 1}, {"id": 2}, {"id": 3}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_mindmap",
               return_value={"id": 1, "title": "Mindmap", "mindmap": {"topic": "x"}, "source_ids": [1]}), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_aia_mindmap",
               return_value=501), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.update_aia_mindmap") as mm_update, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_data_tables_by_workspace",
               return_value=[{"id": 1}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_data_table",
               return_value={"id": 1, "title": "Tabelle", "table_data": {"rows": []}, "source_ids": [1]}), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_aia_data_table",
               return_value=601), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.update_aia_data_table") as dt_update, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_exercise_progress") as verlauf, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_streak") as streak, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.mark_demo_tools_seeded") as markieren:
        anzahl = _lege_werkzeug_beispiele_an(5, 4)

    # 2 Karteikarten + 1 Quiz (nur 1 Vorlage vorhanden) + 2 Mindmaps (Deckel bei 2, nicht 3) + 1 Datentabelle.
    assert anzahl == 6
    assert voll.call_count == 3  # 2 karteikarten + 1 quiz
    assert erstellen.call_count == 3
    assert mm_update.call_count == 2
    assert dt_update.call_count == 1
    markieren.assert_called_once_with(5, 4)

    # Jede der 3 kopierten Karteikarten/Quiz-Sets steuert ihre 2 Karten bei.
    verlauf.assert_called_once()
    zeilen = verlauf.call_args[0][0]
    assert len(zeilen) == 6
    assert {z["set_id"] for z in zeilen} == {201, 202, 203}
    assert all(z["user_id"] == 4 for z in zeilen)
    streak.assert_called_once()
    assert streak.call_args[0][:2] == (5, 4)


def test_werkzeuge_nur_einmal_kopiert(client):
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=True), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_workspace_by_id") as ws:
        anzahl = _lege_werkzeug_beispiele_an(5, 4)

    assert anzahl == 0
    ws.assert_not_called()


def test_werkzeuge_eigentuemer_bekommt_keine_kopie_von_sich_selbst(client):
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=False), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_workspace_by_id",
               return_value={"id": 5, "user_id": 4}), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_exercise_sets") as sets:
        anzahl = _lege_werkzeug_beispiele_an(5, 4)

    assert anzahl == 0
    sets.assert_not_called()


from src.features.ai_assistant.routes._demo_tour_content import _saet_uebungsverlauf


def test_uebungsverlauf_bleibt_pro_set_an_einem_tag(client):
    """One whole set per day, not cards scattered across days, otherwise the
    per-set ratio in the activity feed reads as noise instead of one attempt."""
    sets = [
        {"id": 1, "items": [{"id": 11}, {"id": 12}, {"id": 13}]},
        {"id": 2, "items": [{"id": 21}, {"id": 22}]},
    ]
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_exercise_progress") as verlauf, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_streak") as streak:
        _saet_uebungsverlauf(5, 4, sets)

    zeilen = verlauf.call_args[0][0]
    assert len(zeilen) == 5
    # Jedes Set hat genau einen Tag, alle seine Karten teilen ihn.
    tage_je_set = {}
    for z in zeilen:
        tage_je_set.setdefault(z["set_id"], set()).add(z["answered_at"].date())
    assert all(len(t) == 1 for t in tage_je_set.values())
    streak.assert_called_once()
    assert streak.call_args[0][0] == 5
    assert streak.call_args[0][1] == 4
    assert streak.call_args[0][2] == 3


def test_uebungsverlauf_deckt_immer_heute_ab(client):
    """Egal wie der Zufall die restlichen Tage verteilt, heute bekommt immer
    ein Set, sonst zeigt Statistik direkt nach dem Rundgang eine leere Seite."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    heute = datetime.now(ZoneInfo("Europe/Berlin")).date()
    # Nur ein einzelnes Set, genau der Fall in dem die alte Zip-Kuerzung
    # den heutigen Tag durch puren Zufall haette auslassen koennen.
    sets = [{"id": 1, "items": [{"id": 11}]}]
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_exercise_progress") as verlauf, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_streak"):
        _saet_uebungsverlauf(5, 4, sets)

    zeilen = verlauf.call_args[0][0]
    assert any(z["answered_at"].date() == heute for z in zeilen)


def test_uebungsverlauf_ohne_sets_saet_nichts(client):
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_exercise_progress") as verlauf, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.seed_streak") as streak:
        _saet_uebungsverlauf(5, 4, [])

    verlauf.assert_not_called()
    streak.assert_not_called()


def test_werkzeuge_ohne_vorlage_markiert_nichts(client):
    """Der Eigentuemer hat noch nichts vorbereitet, dann darf der Merker nicht stehen."""
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.demo_tools_already_seeded",
               return_value=False), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_workspace_by_id",
               return_value={"id": 5, "user_id": 15}), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_exercise_sets",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_all_aia_mindmaps",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_data_tables_by_workspace",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.mark_demo_tools_seeded") as markieren:
        anzahl = _lege_werkzeug_beispiele_an(5, 4)

    assert anzahl == 0
    markieren.assert_not_called()


def test_rundgang_haelt_sich_aus_fremden_kursen_raus(client):
    """Another course carries other files, a wrong entry would be worse than none."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace",
               return_value=[{"id": 9, "uuid": "u-x", "filename": "Vorlesung.pdf"}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.bulk_create_glossary_entries") as glossar, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.create_aia_note") as notiz:
        r = client.post("/ai-assistant/demo/tour-content", json={"workspace_uuid": "w5"})

    assert r.json() == {"glossary": 0, "notes": 0}
    glossar.assert_not_called()
    notiz.assert_not_called()


# ─── Chat-Beispiel: nur beim Chat-Schritt, nicht vorher sichtbar ──────────────

from src.features.ai_assistant.routes._demo_tour_content import lege_chat_beispiel_an

_CHAT_QUELLEN = [
    {"id": 9, "uuid": "u-folien", "filename": "DEMO_Folien_01_Grundlagen.pdf"},
]


def test_chat_beispiel_legt_frage_und_antwort_an():
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_messages",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace",
               return_value=_CHAT_QUELLEN), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.save_aia_message") as speichern:
        ergebnis = lege_chat_beispiel_an(5, 4)

    assert ergebnis is True
    assert speichern.call_count == 2
    frage, antwort = speichern.call_args_list
    assert frage.args[:3] == (5, 4, "user")
    assert antwort.args[2] == "assistant"
    # Der Beleg zeigt auf die richtige Quelle, nicht auf eine erfundene UUID.
    assert "u-folien" in antwort.args[3]
    assert antwort.kwargs["source_qmap"] == [
        {"qnum": 1, "uuid": "u-folien", "filename": "DEMO_Folien_01_Grundlagen.pdf", "is_media": False},
    ]
    assert {p["page_number"] for p in antwort.kwargs["source_pages"]} == {16, 17}


def test_chat_beispiel_ueberschreibt_keine_bestehende_unterhaltung():
    """Egal ob echt oder schon einmal angelegt, ein zweites Mal fasst es nichts an."""
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_messages",
               return_value=[{"role": "user", "content": "Irgendwas"}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace") as quellen, \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.save_aia_message") as speichern:
        ergebnis = lege_chat_beispiel_an(5, 4)

    assert ergebnis is False
    quellen.assert_not_called()
    speichern.assert_not_called()


def test_chat_beispiel_ohne_passende_quelle_bleibt_stumm():
    with patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_messages",
               return_value=[]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.get_aia_sources_by_workspace",
               return_value=[{"id": 1, "uuid": "u-x", "filename": "Anderes.pdf"}]), \
         patch("src.features.ai_assistant.routes._demo_tour_content.db.save_aia_message") as speichern:
        ergebnis = lege_chat_beispiel_an(5, 4)

    assert ergebnis is False
    speichern.assert_not_called()


def test_route_chat_beispiel(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.lege_chat_beispiel_an",
               return_value=True) as anlegen:
        r = client.post("/ai-assistant/demo/tour-chat-example", json={"workspace_uuid": "w5"})

    assert r.status_code == 200
    assert r.json() == {"added": True}
    anlegen.assert_called_once_with(5, 1)


def test_route_chat_beispiel_fremder_kurs_gibt_vierhundertvier(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]):
        r = client.post("/ai-assistant/demo/tour-chat-example", json={"workspace_uuid": "fremd"})

    assert r.status_code == 404


# ─── Erstzuweisung: das erste Mal in KIS ──────────────────────────────────────

from unittest.mock import MagicMock

from src.features.accounts.demo_onboarding import demo_module_zuweisen

_DB = "src.features.accounts.demo_onboarding.database"


def test_das_erste_mal_tritt_allen_offenen_demo_modulen_bei():
    kurse = [_kurs(5, "w5"), _kurs(6, "w6", joined=True),
             _kurs(7, "w7", owned=True), _kurs(8, "w8")]
    with patch(f"{_DB}.demo_seeding_done", return_value=False), \
         patch(f"{_DB}.get_demo_workspaces", return_value=kurse), \
         patch(f"{_DB}.claim_demo_seeding", return_value=True), \
         patch(f"{_DB}.enroll_student", side_effect=[11, 12]) as einschreiben:
        beigetreten = demo_module_zuweisen(4)

    assert beigetreten == ["w5", "w8"]
    einschreiben.assert_any_call(5, 4, None, via_demo=True)
    einschreiben.assert_any_call(8, 4, None, via_demo=True)


def test_die_zuweisung_laeuft_nur_einmal():
    """Wer das Modul spaeter verlaesst, soll es nicht beim naechsten Login zurueckbekommen."""
    with patch(f"{_DB}.demo_seeding_done", return_value=True), \
         patch(f"{_DB}.get_demo_workspaces") as kurse, \
         patch(f"{_DB}.enroll_student") as einschreiben:
        beigetreten = demo_module_zuweisen(4)

    assert beigetreten == []
    kurse.assert_not_called()
    einschreiben.assert_not_called()


def test_ohne_demo_modul_bleibt_die_marke_leer():
    """Sonst geht die Zuweisung ins Leere und kommt nie wieder."""
    with patch(f"{_DB}.demo_seeding_done", return_value=False), \
         patch(f"{_DB}.get_demo_workspaces", return_value=[]), \
         patch(f"{_DB}.claim_demo_seeding") as merken, \
         patch(f"{_DB}.enroll_student") as einschreiben:
        beigetreten = demo_module_zuweisen(4)

    assert beigetreten == []
    merken.assert_not_called()
    einschreiben.assert_not_called()


def test_ein_zweiter_gleichzeitiger_lauf_schreibt_nicht_doppelt_ein():
    with patch(f"{_DB}.demo_seeding_done", return_value=False), \
         patch(f"{_DB}.get_demo_workspaces", return_value=[_kurs(5, "w5")]), \
         patch(f"{_DB}.claim_demo_seeding", return_value=False), \
         patch(f"{_DB}.enroll_student") as einschreiben:
        beigetreten = demo_module_zuweisen(4)

    assert beigetreten == []
    einschreiben.assert_not_called()


def test_ein_fehler_haelt_die_anmeldung_nicht_auf():
    with patch(f"{_DB}.demo_seeding_done", side_effect=RuntimeError("Datenbank weg")):
        assert demo_module_zuweisen(4) == []


def test_die_anmeldung_weist_das_demo_modul_zu(monkeypatch):
    """Egal ueber welchen Weg das Konto entstand, die erste Anmeldung holt es nach."""
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")

    from src.app import app
    from src.dependencies import get_settings
    from src.security.auth import verify_auth

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    try:
        with patch("src.routes.auth.authenticate",
                   return_value={"id": 42, "ldap_username": "max.mustermann",
                                 "display_name": "Max Mustermann",
                                 "email": "max.mustermann@demo.kis.local", "active": 1,
                                 "role": "staff", "custom_role_id": None,
                                 "access_expires_at": None}), \
             patch("src.routes.auth.database.get_setting", return_value="false"), \
             patch("src.routes.auth.demo_module_zuweisen") as zuweisen, \
             patch("src.routes.auth.get_session_store") as store:
            store.return_value = MagicMock()
            store.return_value.create.return_value = "tok"
            antwort = TestClient(app).post("/auth/login", json={
                "username": "max.mustermann", "password": "geheim123",
            })
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert antwort.status_code == 200
    zuweisen.assert_called_once_with(42)
