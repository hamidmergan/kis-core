"""Große Übersetzungen und lange Aufnahmen laufen in der Schlange für lange Dienste.

Lauf 13 (27.09.): drei Übersetzungen von 95.000 Zeichen belegten je 20 Minuten drei der vier
schnellen Plätze, Transkripte von 10 Sekunden warteten dahinter.
"""
import asyncio

from src.services.job_lanes import transcribe_route, translate_route

LANG = {"queue": "long", "priority": 9}
KURZ = {"queue": "general"}


def test_kurzer_text_bleibt_in_der_schnellen_schlange():
    assert translate_route(chars=5_000) == KURZ


def test_langer_text_geht_in_die_lange_schlange():
    assert translate_route(chars=95_000) == LANG


def test_eine_pdf_wird_ueber_ihre_seiten_geschaetzt():
    assert translate_route(pages=155) == LANG
    assert translate_route(pages=2) == KURZ


def test_unbekannter_umfang_bleibt_in_der_schnellen_schlange():
    assert translate_route() == KURZ


def test_eine_lange_aufnahme_geht_in_die_lange_schlange():
    assert transcribe_route(96 * 60) == LANG
    assert transcribe_route(5 * 60) == KURZ
    assert transcribe_route(None) == KURZ


class _Request:
    headers: dict = {}


def _uebersetzen(monkeypatch, text):
    from src.routes import translate as route
    import src.tasks.general_tasks as gt

    for name in ("create_job", "set_job_input_path", "set_job_celery_task_id"):
        monkeypatch.setattr(route.db, name, lambda *a, **k: None)
    monkeypatch.setattr(route, "save_queue_file_from_path", lambda *a, **k: "users/1/jobs/x/input")
    monkeypatch.setattr(route, "enforce_open_jobs", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(route, "is_admin_user", lambda u: False)
    gesendet = {}

    def apply_async(args=None, kwargs=None, queue=None, priority=None, **k):
        gesendet["queue"] = (queue, priority)
        return type("R", (), {"id": "t"})()

    monkeypatch.setattr(gt, "run_translate", type("T", (), {"apply_async": staticmethod(apply_async)})())
    asyncio.run(route.translate(
        request=_Request(), file=None, text=text, glossary="", provider_id=None,
        source_lang="", target_lang="", current_user={"user_id": 1}, locale="de",
    ))
    return gesendet["queue"]


def test_die_route_schickt_einen_langen_text_in_die_lange_schlange(monkeypatch):
    assert _uebersetzen(monkeypatch, "Ein langer Satz. " * 2_000) == ("long", 9)


def test_die_route_laesst_einen_kurzen_text_in_der_schnellen_schlange(monkeypatch):
    assert _uebersetzen(monkeypatch, "Ein kurzer Satz.") == ("general", None)
