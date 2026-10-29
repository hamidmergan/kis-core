"""A worker dying mid-job restarts the job, but not endlessly (26.09.: an OOM kill marked a podcast script failed at once)."""

from src import celery_app as app_modul
from src.celery_app import celery_app


class _Redis:
    def __init__(self):
        self.werte = {}

    def incr(self, key):
        self.werte[key] = self.werte.get(key, 0) + 1
        return self.werte[key]

    def expire(self, key, sek):
        pass


def test_ein_abgeschossener_auftrag_geht_zurueck_in_die_schlange():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True


def test_die_ersten_starts_laufen():
    r = _Redis()
    assert [app_modul.start_allowed("t-1", 0, r=r) for _ in range(app_modul.MAX_STARTS)] == \
        [True] * app_modul.MAX_STARTS


def test_ein_auftrag_der_den_arbeiter_immer_wieder_abschiesst_gibt_auf():
    r = _Redis()
    for _ in range(app_modul.MAX_STARTS):
        app_modul.start_allowed("t-1", 0, r=r)
    assert app_modul.start_allowed("t-1", 0, r=r) is False


def test_ein_gewollter_neuer_versuch_zaehlt_eigenstaendig():
    """Celery retries carry the same id but a higher counter."""
    r = _Redis()
    for _ in range(app_modul.MAX_STARTS):
        app_modul.start_allowed("t-1", 0, r=r)
    assert app_modul.start_allowed("t-1", 1, r=r) is True


def test_ohne_redis_laeuft_der_auftrag():
    class _Kaputt:
        def incr(self, key):
            raise ConnectionError("weg")

    assert app_modul.start_allowed("t-1", 0, r=_Kaputt()) is True
