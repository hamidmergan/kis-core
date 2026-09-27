"""Die Etappen-Uhr misst die Arbeitszeit eines Laufs, nicht die des Auftrags."""

from src.tasks._stage import StageClock, continue_stage


class _FakeTask:
    def __init__(self):
        self.args = None

    def apply_async(self, args=None, **kwargs):
        self.args = args
        return type("R", (), {"id": "neu-1"})()


def test_eine_frische_uhr_ist_nicht_abgelaufen():
    assert not StageClock(seconds=60).over()


def test_eine_uhr_ohne_zeit_ist_sofort_abgelaufen():
    assert StageClock(seconds=0).over()


def test_die_verbrauchte_zeit_zaehlt_ab_null():
    assert StageClock(seconds=60).spent() < 1.0


def test_die_naechste_etappe_bekommt_dieselben_argumente(monkeypatch):
    from src.tasks import _stage

    gemerkt = []
    monkeypatch.setattr(_stage, "db", type("D", (), {
        "set_job_celery_task_id": staticmethod(lambda job, tid: gemerkt.append((job, tid))),
    }))
    task = _FakeTask()

    continue_stage(task, ["j", 7, "de", 2, 0], "j")

    assert task.args == ["j", 7, "de", 2, 0]
    assert gemerkt == [("j", "neu-1")]


def test_die_naechste_etappe_reiht_sich_hinter_neue_arbeit_ein(monkeypatch):
    """Lauf 14: Podcast-Skripte reichten jede Etappe mit Vorrang weiter und hielten die drei langen Plätze
    über eine Stunde, 20 Präsentationen und 17 Übersetzungen kamen nicht dran."""
    from src.tasks import _stage

    monkeypatch.setattr(_stage, "db", type("D", (), {"set_job_celery_task_id": staticmethod(lambda job, tid: None)}))
    gesendet = {}

    class _Task:
        def apply_async(self, args=None, **kwargs):
            gesendet.update(kwargs)
            return type("R", (), {"id": "neu-1"})()

    continue_stage(_Task(), ["j", 7, "de", 2, 0], "j")

    assert gesendet.get("priority") == 9
