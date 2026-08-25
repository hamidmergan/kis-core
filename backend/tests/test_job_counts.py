"""Der Zaehler fuer die Statistik: einmal je Auftrag, nie doppelt.

Warum das eigene Tests braucht: die Zaehlung ist die einzige Spur, die ein
Auftrag hinterlaesst, nachdem ihn die Aufbewahrung aus `jobs` entfernt hat.
Zaehlt sie zweimal, steht in der Statistik dauerhaft eine falsche Zahl, und
niemand kann sie nachtraeglich richtigstellen.
"""
import pytest

from src.features.jobs.repository._counts import (
    FINAL,
    GESTARTET,
    count_job,
    count_started,
    messpunkt,
)
from src.features.stats.tools import WERKZEUGE, ZUSAMMEN


class FakeCursor:
    """Merkt sich nur, ob und womit eingefuegt wurde."""

    def __init__(self):
        self.calls = []

    def execute(self, sql, args=None):
        self.calls.append((sql, args))


def _completed():
    from datetime import datetime, timezone
    return datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)


def _started():
    from datetime import datetime, timezone
    return datetime(2026, 8, 25, 9, 20, tzinfo=timezone.utc)


def test_ein_erfolg_wird_gezaehlt():
    cur = FakeCursor()
    count_job(cur, "translation", "success", _started(), _completed())
    assert len(cur.calls) == 1
    assert "job_counts" in cur.calls[0][0]


def test_die_dauer_ist_die_gemessene_spanne():
    cur = FakeCursor()
    count_job(cur, "translation", "success", _started(), _completed())
    # Reihenfolge der Parameter: completed, completed, tool, status, sekunden
    assert cur.calls[0][1][-1] == 600


def test_ein_fehlschlag_zaehlt_ohne_dauer():
    """Eine abgebrochene Dauer waere keine Rechenzeit, sondern Zufall."""
    cur = FakeCursor()
    count_job(cur, "translation", "failed", _started(), _completed())
    assert len(cur.calls) == 1
    assert cur.calls[0][1][-1] == 0


def test_ohne_startzeit_bleibt_die_dauer_null():
    cur = FakeCursor()
    count_job(cur, "translation", "success", None, _completed())
    assert cur.calls[0][1][-1] == 0


@pytest.mark.parametrize("status", ["running", "queued", "pending", "awaiting_user"])
def test_zwischenzustaende_zaehlen_nicht(status):
    cur = FakeCursor()
    count_job(cur, "translation", status, _started(), _completed())
    assert cur.calls == []


def test_ohne_abschlusszeit_zaehlt_nichts():
    cur = FakeCursor()
    count_job(cur, "translation", "success", _started(), None)
    assert cur.calls == []


def test_nur_erfolg_und_fehlschlag_sind_endzustaende():
    assert set(FINAL) == {"success", "failed"}


def test_screencast_misst_ab_dem_rendern():
    """Sonst stuende die Wartezeit auf den Nutzer in der Rechenzeit."""
    assert messpunkt("screencast_render", _started(), _completed()) == _completed()
    assert messpunkt("screencast_translate", _started(), _completed()) == _completed()


def test_ohne_renderstart_gilt_der_normale_start():
    assert messpunkt("screencast_render", _started(), None) == _started()


def test_andere_werkzeuge_messen_ab_dem_start():
    assert messpunkt("translation", _started(), _completed()) == _started()


def test_gemischte_zeitzonen_stuerzen_nicht_ab():
    """`jobs` speichert ohne Zone, der Aufrufer rechnet mit einer.

    Ohne Ausgleich scheitert schon das Abziehen der beiden Zeiten, und der
    Auftrag wuerde nie gezaehlt. Live aufgefallen, nicht im Kopf.
    """
    from datetime import datetime, timezone
    cur = FakeCursor()
    ohne_zone = datetime(2026, 8, 25, 9, 20)
    mit_zone = datetime(2026, 8, 25, 9, 30, tzinfo=timezone.utc)
    count_job(cur, "translation", "success", ohne_zone, mit_zone)
    assert cur.calls[0][1][-1] == 600


def test_das_anlegen_wird_gezaehlt():
    """Die Zeile beim Anlegen ist die, die einen geloeschten Auftrag ueberlebt."""
    cur = FakeCursor()
    count_started(cur, "screencast_render")
    assert len(cur.calls) == 1
    sql, args = cur.calls[0]
    assert "INSERT INTO job_counts" in sql
    assert args == ("screencast_render", GESTARTET)


def test_anlegen_und_abschluss_sind_zwei_zeilen():
    """Sonst zaehlte derselbe Auftrag zweimal in derselben Summe."""
    cur = FakeCursor()
    count_started(cur, "translation")
    count_job(cur, "translation", "success", _started(), _completed())
    zustaende = [c[1][-1] if c[1][-1] in ("success", GESTARTET) else c[1][3] for c in cur.calls]
    assert GESTARTET in zustaende and "success" in zustaende


def test_screencast_uebersetzung_gilt_als_screencast():
    assert ZUSAMMEN["screencast_translate"] == "screencast"
    assert ZUSAMMEN["screencast_render"] == "screencast"


def test_jedes_werkzeug_hat_einen_namen():
    """Sonst steht in den Balken ein leerer Schluessel statt eines Namens."""
    assert len(WERKZEUGE) == 8
    assert set(ZUSAMMEN.values()) <= set(WERKZEUGE)
