"""Gleichzeitige Anfragen an den KI-Anbieter: feste gemessene Konstanten.

Ersetzt test_screencast_tts_parallelism.py und test_stt_chunk_parallelism.py.
Die prüften ein Admin-Feld, das es nicht mehr gibt, samt Deckelung gegen
Fehleingaben. Ohne Eingabefeld gibt es keine Fehleingabe.

Zwischenzeitlich stand hier eine Selbstregelung (halbieren bei Absage, langsam
zurück). Die ist bewusst wieder raus. Der Grund ist nicht, dass sie nicht
funktionierte, sondern dass sie das Problem gar nicht lösen kann: das Kontingent
teilen sich alle Projekte der Hochschule, und wie viel gerade frei ist, hängt an
den anderen. Eine eigene Zahl wäre in beide Richtungen falsch, zu hoch wenn
andere aktiv sind, zu niedrig wenn nicht.

Was bleibt, sind gemessene Werte plus die Wiederholung mit wachsender Wartezeit,
die es an beiden Stellen ohnehin schon gab.
"""

from src.limits import SCREENCAST_TTS_PARALLELISM, STT_CHUNK_PARALLELISM
from src.services.openai_compat_llm import _whisper_chunked
from src.services.screencast import generation


def test_vertonung_nimmt_den_gemessenen_wert():
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_PARALLELISM


def test_spracherkennung_nimmt_den_gemessenen_wert():
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_PARALLELISM


def test_keine_einstellung_kann_die_werte_mehr_verstellen(monkeypatch):
    """Auch ein Eintrag in der Datenbank ändert nichts mehr.

    Die alten Schlüssel können in bestehenden Installationen noch in der
    Tabelle stehen. Sie dürfen keine Wirkung mehr haben.
    """
    from src import database as db

    monkeypatch.setattr(db, "get_setting", lambda *a, **k: "99")
    assert generation.resolve_tts_parallelism() == SCREENCAST_TTS_PARALLELISM
    assert _whisper_chunked.chunk_concurrency() == STT_CHUNK_PARALLELISM


def test_vertonung_laeuft_nicht_einzeln():
    """Der alte Wert 1 machte eine 90-Minuten-Vorlesung unmöglich: 82 Minuten
    reine Vertonung gegen ein Zeitlimit, das darunter lag."""
    assert SCREENCAST_TTS_PARALLELISM > 1


def test_spracherkennung_bleibt_zurueckhaltend():
    """Der Wert bleibt in einem gemessenen, zurückhaltenden Rahmen."""
    assert 1 <= STT_CHUNK_PARALLELISM <= 4
