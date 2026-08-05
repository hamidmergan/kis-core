"""Maschinenerkennung: die Zahlen, die früher im Admin-Bereich standen.

Der wichtigste Test ist ``test_produktionsmaschine_ergibt_die_alten_handwerte``.
Er hält fest, dass die Automatik auf der echten Maschine genau das liefert, was
vorher mühsam von Hand eingestellt war. Ohne diesen Beleg wäre die Umstellung
eine Wette.

Der zweitwichtigste ist ``test_container_grenze_schlaegt_wirtssystem``. Das ist
der Fehler, den JVM, Go und Node alle einmal gemacht haben: im Container die
Kerne des Wirts lesen und sich damit selbst erwürgen.
"""

import pytest

from src.services import system_capacity as sc

GB = 1024 ** 3


def _capacity(cores: float, gb: float) -> sc.Capacity:
    return sc.Capacity(
        cores=cores,
        memory_bytes=int(gb * GB),
        cores_source="Test",
        memory_source="Test",
    )


# --- Die Formeln ------------------------------------------------------------

def test_produktionsmaschine_ergibt_die_alten_handwerte():
    """4 Kerne, 8 GB (Hetzner cpx32) muss genau die bisherigen Werte liefern.

    Vorher von Hand im Admin: Uploads 3, Umwandlung 2. Die Hintergrund-Plätze
    stehen absichtlich NICHT hier, siehe Modul-Kommentar.
    """
    c = _capacity(4, 8)
    assert c.max_concurrent_uploads == 3
    assert c.render_workers == 2


def test_grosse_maschine_waechst_mit():
    """Der eigentliche Gewinn: beim Server-Umzug passiert das von selbst."""
    c = _capacity(16, 64)
    assert c.max_concurrent_uploads > 3
    assert c.render_workers > 2


def test_wenig_speicher_bremst_trotz_vieler_kerne():
    """Kerne allein täuschen. 16 Kerne mit 2 GB dürfen keine 12 Uploads
    gleichzeitig umwandeln, LibreOffice und ffmpeg brauchen den Speicher."""
    viel_ram = _capacity(16, 64)
    wenig_ram = _capacity(16, 2)
    assert wenig_ram.max_concurrent_uploads < viel_ram.max_concurrent_uploads


def test_winzige_maschine_bekommt_trotzdem_einen_platz():
    """Null Plätze hieße: nichts läuft mehr. Lieber langsam als tot."""
    c = _capacity(1, 0.5)
    assert c.max_concurrent_uploads >= 1
    assert c.render_workers >= 1


def test_riesige_maschine_wird_gedeckelt():
    """Ab einer gewissen Größe liegt der Engpass nicht mehr bei uns, sondern
    beim Anbieter oder der Datenbank. Unbegrenzt hochzuzählen bringt nichts."""
    c = _capacity(256, 1024)
    assert c.max_concurrent_uploads <= sc._MAX_CONCURRENT_UPLOADS
    assert c.render_workers <= sc._MAX_RENDER_WORKERS


# --- Die Container-Falle ----------------------------------------------------

@pytest.fixture
def dateien(monkeypatch):
    """Ersetzt das Lesen aus /sys/fs/cgroup durch einen Wörterbuch-Inhalt."""
    def _apply(inhalt: dict[str, str]):
        monkeypatch.setattr(sc, "_read_text", lambda pfad: inhalt.get(pfad))
    return _apply


def test_container_grenze_schlaegt_wirtssystem(dateien, monkeypatch):
    """--cpus=2 auf einer 64-Kern-Maschine muss 2 ergeben, nicht 64."""
    dateien({"/sys/fs/cgroup/cpu.max": "200000 100000"})
    monkeypatch.setattr(sc.os, "cpu_count", lambda: 64)
    ergebnis = sc._detect()
    assert ergebnis.cores == 2.0
    assert ergebnis.cores_source == "cgroup v2"


def test_cgroup_v1_wird_auch_gelesen(dateien):
    dateien({
        "/sys/fs/cgroup/cpu/cpu.cfs_quota_us": "150000",
        "/sys/fs/cgroup/cpu/cpu.cfs_period_us": "100000",
    })
    assert sc._detect().cores == 1.5


def test_unbegrenzte_cgroup_faellt_auf_die_maschine_zurueck(dateien, monkeypatch):
    """"max" heißt keine Grenze. Dann zählt, was wirklich da ist."""
    dateien({"/sys/fs/cgroup/cpu.max": "max 100000"})
    monkeypatch.setattr(sc, "_cores_from_affinity", lambda: None)
    monkeypatch.setattr(sc.os, "cpu_count", lambda: 8)
    ergebnis = sc._detect()
    assert ergebnis.cores == 8.0
    assert ergebnis.cores_source == "Wirtssystem"


def test_cgroup_v1_platzhalter_ist_keine_speichergrenze(dateien):
    """cgroup v1 schreibt für "unbegrenzt" eine Zahl nahe 2^63 statt "max".
    Die als echte Grenze zu lesen hieße, von 8 Exabyte RAM auszugehen."""
    dateien({"/sys/fs/cgroup/memory/memory.limit_in_bytes": str(2 ** 63 - 1)})
    assert sc._memory_from_cgroup() is None


def test_kaputte_dateien_legen_nichts_lahm(dateien):
    """Unlesbarer Inhalt darf keinen Absturz beim Hochfahren bedeuten."""
    dateien({
        "/sys/fs/cgroup/cpu.max": "voellig kaputt",
        "/sys/fs/cgroup/memory.max": "auch kaputt",
    })
    ergebnis = sc._detect()
    assert ergebnis.cores >= 1
    assert ergebnis.memory_bytes > 0
    assert ergebnis.max_concurrent_uploads >= 1


def test_ohne_jede_information_wird_vorsichtig_geschaetzt(dateien, monkeypatch):
    """Wenn wir nichts wissen, ist Untertreiben richtig: ein zu großer
    Schätzwert überlastet die Maschine, ein zu kleiner macht sie nur langsam."""
    dateien({})
    monkeypatch.setattr(sc, "_cores_from_affinity", lambda: None)
    monkeypatch.setattr(sc.os, "cpu_count", lambda: None)
    monkeypatch.setattr(sc, "_memory_from_host", lambda: None)
    ergebnis = sc._detect()
    assert ergebnis.cores == 1.0
    assert ergebnis.memory_source == "Schätzwert"
    assert ergebnis.max_concurrent_uploads == 1


def test_erkennung_wird_nur_einmal_gemacht():
    """Kerne ändern sich im Betrieb nicht, und der Wert steckt in heißen Pfaden
    (jeder Upload, jeder Auftrag)."""
    assert sc.capacity() is sc.capacity()
