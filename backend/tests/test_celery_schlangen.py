"""Welche Arbeit in welcher Schlange landet, damit nichts anderes blockiert.

Lasttest 26.09.: zehn Podcast-Vertonungen warteten auf myLab und belegten alle Plätze der
allgemeinen Schlange. Zusammenfassungen standen still, und der Aufseher kam nicht dran.
"""

from src.celery_app import celery_app


def _schlange(task):
    return celery_app.conf.task_routes[task]["queue"]


def test_alles_mit_sprachausgabe_hat_eine_eigene_schlange():
    assert _schlange("tts.run") == "tts"
    assert _schlange("podcast.render") == "tts"


def test_kurze_dienste_bleiben_in_der_allgemeinen_schlange():
    for task in ("summary.run", "general.translate", "general.transcribe", "general.image_generate",
                 "general.image_edit", "general.image_analyze", "cleanup.expired_files"):
        assert _schlange(task) == "general"


def test_lange_dienste_haben_eine_eigene_schlange():
    """Lauf 7: ein Transkript lief 10 s, wartete aber 12 Minuten hinter Gliederungen und Podcast-Skripten."""
    from src.tasks.backup_tasks import run_database_backup
    from src.tasks.podcast_tasks._script import run_podcast_script
    from src.tasks.praesentation_tasks._build import run_praesentation_build
    from src.tasks.praesentation_tasks._outline import run_praesentation_outline

    for task in ("podcast.script", "praesentation.outline", "praesentation.build", "backup.database"):
        assert _schlange(task) == "long"
    for task in (run_podcast_script, run_praesentation_outline, run_praesentation_build, run_database_backup):
        assert task.queue == "long"
    assert celery_app.conf.beat_schedule["backup-database"]["options"]["queue"] == "long"


def test_ein_neustart_gibt_laufende_auftraege_sofort_zurueck():
    """26.09.: nach einem Neustart lagen sechs Tools eine Stunde lang als übernommen beim Verteiler."""
    assert celery_app.conf.worker_soft_shutdown_timeout > 0
    assert celery_app.conf.worker_enable_soft_shutdown_on_idle is True


def test_jeder_arbeiter_gibt_beim_stoppen_zurueck_bevor_docker_ihn_toetet():
    """Docker schickt TERM, Celery wartet darauf sonst endlos und wird nach 10 s hart beendet."""
    import pathlib

    import pytest

    yaml = pytest.importorskip("yaml")
    datei = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if not datei.exists():
        pytest.skip("docker-compose.yml liegt nicht im Container")
    dienste = yaml.safe_load(datei.read_text())["services"]
    frist = celery_app.conf.worker_soft_shutdown_timeout
    arbeiter = [n for n, d in dienste.items() if " worker " in str(d.get("command", ""))]
    assert "celery-worker-long" in arbeiter
    for name in arbeiter:
        dienst = dienste[name]
        assert dienst["environment"]["REMAP_SIGTERM"] == "SIGQUIT", name
        sekunden = int(str(dienst["stop_grace_period"]).rstrip("s"))
        assert sekunden > frist + 10, name


def test_der_aufseher_hat_eine_schlange_fuer_sich():
    assert _schlange("watchdog.check") == "control"
    eintrag = celery_app.conf.beat_schedule["watchdog-stuck-jobs"]
    assert eintrag["options"]["queue"] == "control"


def test_liegengebliebene_aufseher_takte_verfallen():
    """Sonst stauen sich hunderte Takte und laufen später alle auf einmal."""
    eintrag = celery_app.conf.beat_schedule["watchdog-stuck-jobs"]
    assert 0 < eintrag["options"]["expires"] <= 30


def test_jede_schlange_wird_vom_broker_blick_erfasst():
    from src.services.broker_state import QUEUES
    schlangen = {r["queue"] for r in celery_app.conf.task_routes.values()}
    assert schlangen <= set(QUEUES)


def test_ein_aufgeblaehter_arbeiterprozess_wird_nach_seinem_auftrag_ersetzt():
    """Ein Prozess, der nach einem großen Dokument viel Speicher behält, drängt sonst andere hinaus."""
    grenze_kib = celery_app.conf.worker_max_memory_per_child
    assert grenze_kib and grenze_kib <= 500_000


def test_quellen_haben_eine_eigene_schlange():
    """Lasttest 26.09., Lauf 6: Quellen standen in der Schlange hinter 14 Lerntools, Francis blieb stumm."""
    from src.features.ai_assistant.tasks.ingestion import run_index_source, run_translate_transcript

    for task in ("aia.index_source", "aia.translate_transcript", "aia.reindex_all_sources"):
        assert _schlange(task) == "aia_ingest"
    assert run_index_source.queue == "aia_ingest"
    assert run_translate_transcript.queue == "aia_ingest"
    assert _schlange("aia.generate_exercise_set") == "aia"


def test_der_platzverteiler_schickt_quellen_in_ihre_schlange(monkeypatch):
    from src.features.ai_assistant.scheduling import service
    from src.features.ai_assistant.scheduling.dispatch_service import Job

    gesendet = []

    class _Ergebnis:
        id = "t1"

    def senden(name, args=None, kwargs=None, queue=None):
        gesendet.append((name, queue))
        return _Ergebnis()

    monkeypatch.setattr(celery_app, "send_task", senden)
    for name in ("aia.index_source", "aia.generate_mindmap"):
        service._launch(Job(job_uuid="j", user_id=1, area="x", task_name=name, payload={}, created_at=0.0))

    assert gesendet == [("aia.index_source", "aia_ingest"), ("aia.generate_mindmap", "aia")]


def test_ein_abgebrochener_auftrag_wird_nicht_als_erledigt_quittiert():
    """billiard 4.3.0 meldet den eigenen Stopp als Ergebnis, der laufende Auftrag verschwand (celery/billiard#463)."""
    from importlib.metadata import version

    assert version("billiard") != "4.3.0"


def test_der_francis_arbeiter_hat_so_viele_prozesse_wie_plaetze():
    """Mehr Plätze als Prozesse lassen freigegebene Aufträge in der Celery-Schlange stehen."""
    import pathlib
    import re

    import pytest

    from src.limits import AIA_PARALLEL_SLOTS

    yaml = pytest.importorskip("yaml")
    datei = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if not datei.exists():
        pytest.skip("docker-compose.yml liegt nicht im Container")
    befehl = str(yaml.safe_load(datei.read_text())["services"]["celery-worker-aia"]["command"])
    assert int(re.search(r"--autoscale=(\d+),", befehl).group(1)) == AIA_PARALLEL_SLOTS


def test_der_hauptprozess_friert_seine_objekte_vor_jedem_prozessstart_ein():
    """Lauf 10: jeder benutzte Prozess kopierte rund 50 MB vom Hauptprozess, die er nur teilen müsste."""
    import gc

    from celery.signals import worker_before_create_process

    gc.unfreeze()
    try:
        worker_before_create_process.send(sender=None)
        assert gc.get_freeze_count() > 0
    finally:
        gc.unfreeze()


def test_kurze_dienste_ziehen_an_der_zusammenfassung_vorbei():
    """Lauf 10: ein Transkript von 10 s wartete bis zu 23 Minuten hinter Zusammenfassungen von 2,5 Minuten."""
    from kombu.transport.redis import Channel

    from src.tasks.general_tasks import run_image_edit, run_image_generate, run_transcribe, run_translate
    from src.tasks.summary_tasks import run_summary

    class _Kanal(Channel):
        def __init__(self):
            pass

    kanal = _Kanal()
    schluessel = {t.name: kanal._q_for_pri("general", t.priority or 0)
                  for t in (run_summary, run_transcribe, run_translate, run_image_generate, run_image_edit)}
    assert schluessel["summary.run"] != "general"
    for name in ("general.transcribe", "general.translate", "general.image_generate", "general.image_edit"):
        assert schluessel[name] == "general"


def test_gliederung_und_skript_ziehen_am_aufbau_vorbei():
    """Der Aufbau läuft in Etappen von zehn Minuten, die Gliederung braucht 40 s und hält die Person auf."""
    from kombu.transport.redis import Channel

    from src.tasks.podcast_tasks._script import run_podcast_script
    from src.tasks.praesentation_tasks._build import run_praesentation_build
    from src.tasks.praesentation_tasks._outline import run_praesentation_outline

    class _Kanal(Channel):
        def __init__(self):
            pass

    kanal = _Kanal()
    assert kanal._q_for_pri("long", run_praesentation_build.priority or 0) != "long"
    for task in (run_praesentation_outline, run_podcast_script):
        assert kanal._q_for_pri("long", task.priority or 0) == "long"


def test_das_backend_haelt_nicht_je_thread_einen_eigenen_speicherbereich():
    """Lauf 11: 63 bis 69 Thread-Bereiche hielten je Backend-Prozess 500 bis 600 MB, der Rechner lief voll."""
    import pathlib

    import pytest

    yaml = pytest.importorskip("yaml")
    datei = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if not datei.exists():
        pytest.skip("docker-compose.yml liegt nicht im Container")
    umgebung = yaml.safe_load(datei.read_text())["services"]["backend"]["environment"]
    assert str(umgebung["MALLOC_ARENA_MAX"]) == "2"


def test_die_openai_bibliothek_springt_nicht_still_auf_eine_neue_version():
    """27.09.: ein Neubau holte openai 3.19.2, Screencasts scheiterten 6-mal an einem Pydantic-Fehler, Prod mit 3.11.0 nie."""
    import pathlib
    import re

    anforderungen = (pathlib.Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    assert re.search(r"^openai==3\.11\.0$", anforderungen, re.M)
