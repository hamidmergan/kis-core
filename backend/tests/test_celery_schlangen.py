"""Which work lands in which queue so nothing else blocks.

Load test 26.09.: ten podcast renders waited for myLab and took all seats of the general queue, summaries stalled and the watchdog never got a turn.
"""

from src.celery_app import celery_app


def _schlange(task):
    return celery_app.conf.task_routes[task]["queue"]


def test_alles_mit_sprachausgabe_hat_eine_eigene_schlange():
    assert _schlange("tts.run") == "tts"
    assert _schlange("podcast.render") == "tts"


def test_kurze_dienste_bleiben_in_der_allgemeinen_schlange():
    for task in ("general.translate", "general.transcribe", "general.image_generate",
                 "general.image_edit", "general.image_analyze", "cleanup.expired_files"):
        assert _schlange(task) == "general"


def test_die_zusammenfassung_laeuft_bei_den_langen_diensten():
    """Run 15: under load it holds a process for 6 to 15 minutes, in the general queue it held up transcripts."""
    from src.tasks.summary_tasks import run_summary

    assert _schlange("summary.run") == "long"
    assert run_summary.queue == "long"


def test_lange_dienste_haben_eine_eigene_schlange():
    """Run 7: a transcript ran 10 s but waited 12 minutes behind outlines and podcast scripts."""
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
    """26.09.: after a restart six tools sat at the dispatcher as taken for an hour."""
    assert celery_app.conf.worker_soft_shutdown_timeout > 0
    assert celery_app.conf.worker_enable_soft_shutdown_on_idle is True


def test_jeder_arbeiter_gibt_beim_stoppen_zurueck_bevor_docker_ihn_toetet():
    """Docker sends TERM, otherwise Celery waits for it forever and is killed hard after 10 s."""
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
    """Otherwise hundreds of ticks pile up and all run at once later."""
    eintrag = celery_app.conf.beat_schedule["watchdog-stuck-jobs"]
    assert 0 < eintrag["options"]["expires"] <= 30


def test_jede_schlange_wird_vom_broker_blick_erfasst():
    from src.services.broker_state import QUEUES
    schlangen = {r["queue"] for r in celery_app.conf.task_routes.values()}
    assert schlangen <= set(QUEUES)


def test_ein_aufgeblaehter_arbeiterprozess_wird_nach_seinem_auftrag_ersetzt():
    """A process that keeps a lot of memory after a large document otherwise pushes others out."""
    grenze_kib = celery_app.conf.worker_max_memory_per_child
    assert grenze_kib and grenze_kib <= 500_000


def test_quellen_haben_eine_eigene_schlange():
    """Load test 26.09., run 6: sources queued behind 14 learning tools, Francis stayed silent."""
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
    """billiard 4.3.0 reports its own stop as a result, the running job vanished (celery/billiard#463)."""
    from importlib.metadata import version

    assert version("billiard") != "4.3.0"


def test_der_francis_arbeiter_hat_so_viele_prozesse_wie_plaetze():
    """More seats than processes leave released jobs standing in the Celery queue."""
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
    """Run 10: every used process copied about 50 MB from the main process that it only needed to share."""
    import gc

    from celery.signals import worker_before_create_process

    gc.unfreeze()
    try:
        worker_before_create_process.send(sender=None)
        assert gc.get_freeze_count() > 0
    finally:
        gc.unfreeze()


def test_gliederung_und_skript_ziehen_am_aufbau_vorbei():
    """The build runs in ten-minute stages, the outline takes 40 s and keeps the person waiting."""
    from kombu.transport.redis import Channel

    from src.tasks.podcast_tasks._script import run_podcast_script
    from src.tasks.praesentation_tasks._build import run_praesentation_build
    from src.tasks.praesentation_tasks._outline import run_praesentation_outline

    class _Kanal(Channel):
        def __init__(self):
            pass

    from src.tasks.summary_tasks import run_summary

    kanal = _Kanal()
    # Summary and build hold a process for minutes, outline and script pass them.
    for task in (run_praesentation_build, run_summary):
        assert kanal._q_for_pri("long", task.priority or 0) != "long"
    for task in (run_praesentation_outline, run_podcast_script):
        assert kanal._q_for_pri("long", task.priority or 0) == "long"


def test_das_backend_haelt_nicht_je_thread_einen_eigenen_speicherbereich():
    """Run 11: 63 to 69 thread arenas held 500 to 600 MB per backend process, the machine filled up."""
    import pathlib

    import pytest

    yaml = pytest.importorskip("yaml")
    datei = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"
    if not datei.exists():
        pytest.skip("docker-compose.yml liegt nicht im Container")
    umgebung = yaml.safe_load(datei.read_text())["services"]["backend"]["environment"]
    assert str(umgebung["MALLOC_ARENA_MAX"]) == "2"


def test_die_openai_bibliothek_springt_nicht_still_auf_eine_neue_version():
    """27.09.: a rebuild pulled openai 3.19.2, screencasts failed 6 times on a Pydantic error, prod with 3.11.0 never."""
    import pathlib
    import re

    anforderungen = (pathlib.Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    assert re.search(r"^openai==3\.11\.0$", anforderungen, re.M)
