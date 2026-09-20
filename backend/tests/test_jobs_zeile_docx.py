"""The job row says whether a summary also has its Word file, the list only offers it then."""

from datetime import datetime

from src.routes.jobs._shared import _format_job_rows
from src.storage import save_result_file


UID = 7
JOB = "c" * 32


def _zeile(ergebnis: str, tool: str = "summary", status: str = "success") -> dict:
    return {
        "job_uuid": JOB,
        "user_id": UID,
        "tool": tool,
        "original_filename": "gesetz.pdf",
        "status": status,
        "error_message": None,
        "progress": None,
        "result_path": ergebnis,
        "result_filename": "gesetz.md",
        "created_at": datetime(2026, 9, 20, 9, 30, 0),
        "started_at": None,
        "completed_at": None,
        "render_started_at": None,
        "render_queued_at": None,
        "expires_at": None,
    }


def test_neben_dem_markdown_liegt_die_word_datei(lokal):
    pfad = save_result_file(UID, JOB, ".md", b"# Titel")
    save_result_file(UID, JOB, ".docx", b"PK")

    zeilen = _format_job_rows([_zeile(pfad)], "de")

    assert zeilen[0]["has_download"] is True
    assert zeilen[0]["has_docx"] is True


def test_ohne_word_datei_bleibt_es_beim_markdown(lokal):
    pfad = save_result_file(UID, JOB, ".md", b"# Titel")

    zeilen = _format_job_rows([_zeile(pfad)], "de")

    assert zeilen[0]["has_download"] is True
    assert zeilen[0]["has_docx"] is False


def test_andere_werkzeuge_bieten_keine_word_datei_an(lokal):
    pfad = save_result_file(UID, JOB, ".md", b"# Titel")
    save_result_file(UID, JOB, ".docx", b"PK")

    zeilen = _format_job_rows([_zeile(pfad, tool="translation")], "de")

    assert zeilen[0]["has_docx"] is False


def test_ein_laufender_auftrag_hat_noch_nichts(lokal):
    pfad = save_result_file(UID, JOB, ".md", b"# Titel")
    save_result_file(UID, JOB, ".docx", b"PK")

    zeilen = _format_job_rows([_zeile(pfad, status="running")], "de")

    assert zeilen[0]["has_download"] is False
    assert zeilen[0]["has_docx"] is False
