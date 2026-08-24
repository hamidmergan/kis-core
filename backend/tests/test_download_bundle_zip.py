"""Round-trip tests for the streaming ZIP bundle.

_ZipStreamWriter reports virtual (absolute) offsets and drains its buffer after
every entry so the whole archive is never held in RAM. These tests confirm the
produced byte stream is still a valid, extractable ZIP.
"""

import io
import zipfile

from src.routes.jobs import _download


def _collect(gen) -> bytes:
    return b"".join(gen)


def _fake_store(files: dict[str, bytes], monkeypatch):
    """Wire get_job_file / job_file_exists to an in-memory {filename: bytes} map."""
    def _get(user_id, job_uuid, filename):
        if filename not in files:
            raise FileNotFoundError(filename)
        return files[filename]

    def _exists(user_id, job_uuid, filename):
        return filename in files

    monkeypatch.setattr(_download, "get_job_file", _get)
    monkeypatch.setattr(_download, "job_file_exists", _exists)


def test_bundle_is_valid_zip_with_all_parts(monkeypatch):
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", True)
    files = {
        "output.mp4": b"MP4-BYTES" * 1000,
        "audio/slide_000.mp3": b"AUDIO-0" * 500,
        "audio/slide_001.mp3": b"AUDIO-1" * 500,
        "original.pptx": b"ORIGINAL-BYTES" * 400,
        "translated.pptx": b"PPTX-BYTES" * 800,
        "untertitel.vtt": b"WEBVTT\n",
        "accepted_scripts.json": b'{"scripts": ["a", "b"]}',
    }
    _fake_store(files, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(
        1, "job", "MyDeck", audio_count=2, ziel_wort="englisch", info_text="Screencast: MyDeck\n",
    ))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.testzip() is None  # CRC check across every entry
    assert sorted(zf.namelist()) == [
        "Audios/folie_001.mp3",
        "Audios/folie_002.mp3",
        "MyDeck_englisch.pptx",
        "MyDeck_info.txt",
        "MyDeck_original.pptx",
        "MyDeck_sprechtexte.json",
        "MyDeck_untertitel.vtt",
        "MyDeck_video.mp4",
    ]
    assert zf.read("MyDeck_video.mp4") == files["output.mp4"]
    assert zf.read("MyDeck_englisch.pptx") == files["translated.pptx"]
    assert zf.read("MyDeck_original.pptx") == files["original.pptx"]
    assert zf.read("MyDeck_sprechtexte.json") == files["accepted_scripts.json"]
    assert zf.read("Audios/folie_001.mp3") == files["audio/slide_000.mp3"]
    assert zf.read("MyDeck_info.txt").decode() == "Screencast: MyDeck\n"


def test_bundle_prefers_corrected_pptx(monkeypatch):
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", False)
    files = {
        "output.mp4": b"MP4",
        "original.pptx": b"ORIGINAL",
        "corrected.pptx": b"CORRECTED",
        "translated.pptx": b"TRANSLATED",
        "user_scripts.json": b"[]",
    }
    _fake_store(files, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(1, "job", "Deck", audio_count=0, ziel_wort="englisch"))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.testzip() is None
    assert zf.read("Deck_englisch.pptx") == b"CORRECTED"
    # Audio disabled -> no audio entries even if slides exist
    assert not any(n.startswith("Audios/") for n in zf.namelist())


def test_bundle_ohne_uebersetzung_heisst_die_datei_original(monkeypatch):
    """Auf dem englischen Weg gibt es nur eine Datei, und das ist die hochgeladene."""
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", False)
    _fake_store({"output.mp4": b"MP4", "translated.pptx": b"HOCHGELADEN"}, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(1, "job", "Deck", audio_count=0, ziel_wort="englisch"))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.namelist() == ["Deck_video.mp4", "Deck_original.pptx"]
    assert zf.read("Deck_original.pptx") == b"HOCHGELADEN"


def test_bundle_ohne_info_text_laesst_die_datei_weg(monkeypatch):
    """Ohne Text keine leere Info-Datei im Archiv."""
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", False)
    _fake_store({"output.mp4": b"MP4"}, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(1, "job", "Deck", audio_count=0))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.namelist() == ["Deck_video.mp4"]


def test_bundle_skips_missing_files(monkeypatch):
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", True)
    # Only the MP4 exists; everything else is absent.
    _fake_store({"output.mp4": b"ONLY-MP4"}, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(1, "job", "Deck", audio_count=3))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.testzip() is None
    assert zf.namelist() == ["Deck_video.mp4"]


def test_bundle_with_no_files_is_valid_empty_zip(monkeypatch):
    monkeypatch.setattr(_download, "BUNDLE_INCLUDE_AUDIO", True)
    _fake_store({}, monkeypatch)

    raw = _collect(_download._streaming_zip_bundle(1, "job", "Deck", audio_count=0))

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.namelist() == []


def test_writer_reports_continuous_virtual_offset():
    """tell() must stay continuous across drains (zipfile relies on it)."""
    w = _download._ZipStreamWriter()
    w.write(b"hello")
    assert w.tell() == 5
    assert w.drain() == b"hello"
    assert w.tell() == 5  # base advanced, buffer reset
    w.write(b"world!")
    assert w.tell() == 11
    assert w.drain() == b"world!"
    assert w.tell() == 11
