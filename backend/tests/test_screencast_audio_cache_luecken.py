"""Ausgeschlossene Folien behalten ihren alten Ton, damit Wiederaufnehmen nichts kostet."""

from src import storage
from src.storage import audio_folien_mit_ton, clear_audio_cache, hat_audio_slide, job_prefix, save_audio_cache

UUID = "b" * 32
ANDERE_UUID = "c" * 32


def _audio_dir(lokal):
    return lokal / job_prefix(1, UUID) / "audio"


def test_none_laesst_die_vorhandene_datei_stehen(lokal):
    save_audio_cache(1, UUID, [b"ID3alt0", b"ID3alt1"])
    save_audio_cache(1, UUID, [b"ID3neu0", None])
    assert (_audio_dir(lokal) / "slide_000.mp3").read_bytes() == b"ID3neu0"
    assert (_audio_dir(lokal) / "slide_001.mp3").read_bytes() == b"ID3alt1"


def test_leere_bytes_schreiben_eine_leere_datei(lokal):
    """Eine Folie ohne Skript hat keinen Ton, der Platz bleibt aber belegt."""
    save_audio_cache(1, UUID, [b""])
    assert (_audio_dir(lokal) / "slide_000.mp3").read_bytes() == b""


def test_nur_none_schreibt_gar_nichts(lokal):
    save_audio_cache(1, UUID, [None, None])
    assert not (_audio_dir(lokal)).exists()


def test_hat_audio_slide_erkennt_inhalt(lokal):
    save_audio_cache(1, UUID, [b"ID3", b""])
    assert hat_audio_slide(1, UUID, 0) is True


def test_leere_datei_gilt_als_kein_ton(lokal):
    """Null Bytes sind kein gueltiges MP3, der Rueckgriff darf sie nicht nehmen."""
    save_audio_cache(1, UUID, [b"ID3", b""])
    assert hat_audio_slide(1, UUID, 1) is False


def test_fehlende_datei_gilt_als_kein_ton(lokal):
    save_audio_cache(1, UUID, [b"ID3"])
    assert hat_audio_slide(1, UUID, 5) is False


def test_audio_folien_mit_ton_findet_nur_belegte_plaetze(lokal):
    from src.storage import audio_folien_mit_ton
    save_audio_cache(1, UUID, [b"ID3", b"", b"ID3"])
    assert audio_folien_mit_ton(1, UUID) == {0, 2}


def test_audio_folien_mit_ton_ohne_ordner(lokal):
    from src.storage import audio_folien_mit_ton
    assert audio_folien_mit_ton(1, "c" * 32) == set()


class _FakePaginator:
    """Gibt vorgegebene Seiten zurueck, wie der echte S3-Paginator."""

    def __init__(self, seiten):
        self._seiten = seiten

    def paginate(self, **kw):
        return iter(self._seiten)


class _FakeS3Listing:
    """S3-Attrappe, die nur list_objects_v2 ueber einen Paginator kennt."""

    def __init__(self, seiten):
        self._seiten = seiten

    def get_paginator(self, name):
        return _FakePaginator(self._seiten)


def test_audio_folien_mit_ton_s3_findet_nur_belegte_plaetze(monkeypatch):
    """Der S3-Zweig muss dieselbe Menge liefern wie der lokale, ueber zwei Seiten verteilt."""
    praefix = job_prefix(1, UUID) + "/audio/"
    seiten = [
        {"Contents": [
            {"Key": praefix + "slide_000.mp3", "Size": 120},
            {"Key": praefix + "slide_001.mp3", "Size": 0},
        ]},
        {"Contents": [
            {"Key": praefix + "slide_002.mp3", "Size": 88},
        ]},
    ]
    monkeypatch.setattr(storage, "USE_S3", True)
    monkeypatch.setattr(storage, "_s3", lambda: _FakeS3Listing(seiten))

    assert audio_folien_mit_ton(1, UUID) == {0, 2}


def test_audio_folien_mit_ton_s3_verwirft_unpassenden_schluessel(monkeypatch):
    """Ein Schluessel ausserhalb des slide_NNN-Musters darf nicht als -1 in der Menge landen."""
    praefix = job_prefix(1, UUID) + "/audio/"
    seiten = [
        {"Contents": [
            {"Key": praefix + "slide_000.mp3", "Size": 120},
            {"Key": praefix + "unsinn.txt", "Size": 999},
        ]},
    ]
    monkeypatch.setattr(storage, "USE_S3", True)
    monkeypatch.setattr(storage, "_s3", lambda: _FakeS3Listing(seiten))

    assert audio_folien_mit_ton(1, UUID) == {0}


def test_clear_audio_cache_entfernt_alle_tondateien(lokal):
    save_audio_cache(1, UUID, [b"ID3alt0", b"ID3alt1"])
    entfernt = clear_audio_cache(1, UUID)
    assert entfernt == 2
    assert not _audio_dir(lokal).exists()


def test_clear_audio_cache_ohne_ordner_wirft_nicht(lokal):
    assert clear_audio_cache(1, UUID) == 0


def test_clear_audio_cache_laesst_anderen_auftrag_unangetastet(lokal):
    """Der Schluessel darf nur den Ordner GENAU dieses Auftrags treffen."""
    save_audio_cache(1, UUID, [b"ID3"])
    save_audio_cache(1, ANDERE_UUID, [b"ID3andere"])

    clear_audio_cache(1, UUID)

    assert not _audio_dir(lokal).exists()
    anderer_ordner = lokal / job_prefix(1, ANDERE_UUID) / "audio"
    assert (anderer_ordner / "slide_000.mp3").read_bytes() == b"ID3andere"
