"""Das Podcast-Skript wartet, wenn die KI überlastet ist, statt endgültig zu scheitern.

Lasttest mit großen Dateien am 26.09.: Planungsaufrufe über 200 Seiten dauerten länger, als KIS
wartete, und der Auftrag endete sofort auf failed.
"""

import pytest

from src.tasks.podcast_tasks import _script


@pytest.fixture
def gemeldet(monkeypatch):
    liste = []
    monkeypatch.setattr(_script, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_script, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(_script, "attempt_failed", lambda job, msg, busy=False: liste.append(busy))
    return liste


def _mit_fehler(monkeypatch, fehler):
    def werfen(*a, **k):
        raise fehler
    monkeypatch.setattr(_script.quellen, "load_sources", werfen)


def test_eine_ueberlastete_ki_laesst_das_skript_warten(monkeypatch, gemeldet):
    _mit_fehler(monkeypatch, RuntimeError("Request timed out."))
    with pytest.raises(RuntimeError):
        _script.run_podcast_script.run("j" * 32, 7, "de")
    assert gemeldet == [True]


def test_ein_echter_fehler_bleibt_ein_fehler(monkeypatch, gemeldet):
    _mit_fehler(monkeypatch, KeyError("script"))
    with pytest.raises(KeyError):
        _script.run_podcast_script.run("j" * 32, 7, "de")
    assert gemeldet == [False]


def test_beim_warten_steht_kein_rat_zu_weniger_material(monkeypatch):
    """Lauf 14: wartende Skripte zeigten "Versuch es mit weniger Material", dabei lief alles von selbst weiter."""
    from src.i18n import t

    texte = []
    monkeypatch.setattr(_script, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_script, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(_script, "attempt_failed", lambda job, msg, busy=False: texte.append((busy, msg)))
    _mit_fehler(monkeypatch, RuntimeError("Request timed out."))
    with pytest.raises(RuntimeError):
        _script.run_podcast_script.run("j" * 32, 7, "de")
    assert texte == [(True, t("job.upstreamBusy", "de"))]
