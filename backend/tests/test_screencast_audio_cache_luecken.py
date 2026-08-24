"""Ausgeschlossene Folien behalten ihren alten Ton, damit Wiederaufnehmen nichts kostet."""

from src.storage import hat_audio_slide, job_prefix, save_audio_cache

UUID = "b" * 32


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
