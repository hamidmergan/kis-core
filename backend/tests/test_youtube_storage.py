"""The pasted transcript hangs off a source stem that never gets a file of its own."""
import pytest

from src import storage
from src.i18n import t

_VTT = "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\nHallo\n"


def test_provided_vtt_key_hangs_off_the_source_stem():
    key = storage.aia_provided_vtt_key("users/1/aia/workspaces/w/sources/abc.youtube")
    assert key == "users/1/aia/workspaces/w/sources/abc_provided.vtt"


def test_save_provided_transcript_writes_the_vtt_and_returns_the_source_path(lokal):
    file_path = storage.save_aia_provided_transcript(1, "w", "abc", _VTT)

    assert file_path == str(lokal / "users/1/aia/workspaces/w/sources/abc.youtube")
    assert not (lokal / "users/1/aia/workspaces/w/sources/abc.youtube").exists()
    assert (lokal / "users/1/aia/workspaces/w/sources/abc_provided.vtt").exists()
    assert storage.get_file(storage.aia_provided_vtt_key(file_path)).decode("utf-8") == _VTT


def test_delete_source_files_removes_the_provided_vtt(lokal):
    file_path = storage.save_aia_provided_transcript(1, "w", "abc", _VTT)

    storage.delete_aia_source_files(file_path)

    assert not (lokal / "users/1/aia/workspaces/w/sources/abc_provided.vtt").exists()


@pytest.mark.parametrize("key", [
    "ai.youtube.invalid", "ai.youtube.duplicate", "ai.youtube.notFound", "ai.youtube.notEmbeddable",
    "ai.youtube.noTimestamps", "ai.youtube.emptyTranscript", "ai.youtube.tooLong", "ai.youtube.noFile",
    "ai.link.useYoutube",
])
def test_youtube_texts_exist_in_both_languages(key):
    assert t(key, "de", label="Modul") != key
    assert t(key, "en", label="module") != key
    assert t(key, "de", label="Modul") != t(key, "en", label="module")
