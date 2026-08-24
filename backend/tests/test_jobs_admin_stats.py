"""Die Screencast-Zahlen gehen nur an Admins und auch bei fehlgeschlagenen Jobs mit."""

from datetime import datetime

from src.routes.jobs._shared import _format_job_rows
from src.services.screencast.statistik import notiere
from src.storage import save_result_meta


UID = 7
JOB = "b" * 32


def _zeile(status: str = "success", tool: str = "screencast_render") -> dict:
    return {
        "job_uuid": JOB,
        "user_id": UID,
        "tool": tool,
        "original_filename": "vortrag.pptx",
        "status": status,
        "error_message": None,
        "progress": None,
        "result_path": "",
        "result_filename": "vortrag.mp4",
        "created_at": datetime(2026, 8, 23, 14, 2, 11),
        "started_at": None,
        "completed_at": None,
        "render_started_at": None,
        "render_queued_at": None,
        "expires_at": None,
    }


def test_admin_sieht_die_zahlen(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 12})

    zeilen = _format_job_rows([_zeile()], "de", is_admin=True)

    assert zeilen[0]["meta"]["stats"]["vertonung"] == {"folien": 12}


def test_nutzer_sieht_die_zahlen_nicht(lokal):
    save_result_meta(UID, JOB, {"target_lang": "EN-US"})
    notiere(UID, JOB, "vertonung", {"folien": 12})

    zeilen = _format_job_rows([_zeile()], "de", is_admin=False)

    assert "stats" not in zeilen[0]["meta"]
    assert zeilen[0]["meta"]["target_lang"] == "EN-US"


def test_fehlgeschlagener_job_liefert_die_zahlen(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 12, "fehler": "kaputt"})

    zeilen = _format_job_rows([_zeile(status="failed")], "de", is_admin=True)

    assert zeilen[0]["meta"]["stats"]["vertonung"]["fehler"] == "kaputt"


def test_laufender_job_liefert_keine_zahlen(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 12})

    zeilen = _format_job_rows([_zeile(status="running")], "de", is_admin=True)

    assert zeilen[0]["meta"] is None
