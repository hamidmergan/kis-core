"""The pasted transcript takes Whisper's place, everything after it stays the same."""

import pytest

from src import storage
from src.features.ai_assistant.routes import _media_files
from src.features.ai_assistant.tasks import _provided_transcript as pt
from src.features.ai_assistant.tasks import ingestion
from src.services import aia_chunker

_VTT = (
    "WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\nHallo und willkommen\n\n"
    "2\n00:00:04.000 --> 00:00:09.000\nHeute geht es um Photosynthese\n"
)


def test_load_provided_segments_reads_the_stored_vtt(lokal):
    file_path = storage.save_aia_provided_transcript(1, "w", "abc", _VTT)

    segments = pt.load_provided_segments(file_path)

    assert [s["text"] for s in segments] == ["Hallo und willkommen", "Heute geht es um Photosynthese"]
    assert segments[1]["end"] == 9.0


def test_load_provided_segments_is_empty_without_a_file(lokal):
    assert pt.load_provided_segments(str(lokal / "users/1/aia/workspaces/w/sources/nix.youtube")) == []


def test_detect_language_reads_the_code_locally():
    segments = [{"text": "Today we look at how plants turn light into sugar."}] * 4
    assert pt.detect_language(segments) == "en"


def test_detect_language_falls_back_when_the_text_is_too_short():
    assert pt.detect_language([{"text": "Hallo"}]) == "de"


def test_store_transcript_artifacts_writes_text_and_vtt(lokal):
    file_path = str(lokal / "users/1/aia/workspaces/w/sources/abc.youtube")
    segments = [{"start": 0.0, "end": 4.0, "text": "Hallo"}, {"start": 4.0, "end": 9.0, "text": "Welt"}]

    chunks = ingestion._store_transcript_artifacts(file_path, segments, "de")

    assert chunks[0]["start_time"] == 0.0 and chunks[-1]["end_time"] == 9.0
    txt = storage.get_file(storage.aia_transcript_key(file_path)).decode("utf-8")
    assert "Hallo" in txt and "Welt" in txt
    vtt = storage.get_file(storage.aia_vtt_key(file_path, "de")).decode("utf-8")
    assert vtt.startswith("WEBVTT") and "00:00:04.000 --> 00:00:09.000" in vtt


def test_youtube_counts_as_media_but_not_as_upload():
    assert aia_chunker.is_media_file("youtube") is True
    assert aia_chunker.is_media_file("mp4") is True
    assert aia_chunker.is_media_file("pdf") is False
    assert ".youtube" in _media_files._MEDIA_EXTENSIONS
    assert ".youtube" not in _media_files._ALLOWED_EXTENSIONS


class _Db:
    """Stubs every db.* call run_index_source makes on the youtube branch."""

    def __init__(self, source, calls):
        self.source = source
        self.calls = calls

    def get_aia_source(self, uuid):
        return self.source

    def update_aia_source_status(self, uuid, status, **kw):
        self.calls["status"].append((status, kw))

    def update_aia_source_progress(self, *a, **kw):
        pass

    def delete_aia_chunks_by_source(self, sid):
        pass

    def clear_pool_for_source(self, sid):
        pass

    def create_aia_chunk(self, **kw):
        self.calls["chunks"].append(kw)
        return len(self.calls["chunks"])

    def update_chunk_embedding(self, cid, vec):
        pass

    def get_aia_sources_by_workspace(self, wid):
        return [dict(self.source, status="ready")]

    def get_aia_workspace_by_id(self, wid):
        return {"uuid": "w"}

    def update_aia_workspace_status(self, *a, **kw):
        pass

    def clear_aia_source_progress(self, uuid):
        pass


class _EmbeddingProvider:
    """A fixed-size embedding stub, one short vector per text."""

    model_name = "emb"

    def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


def _youtube_source(file_path):
    return {
        "id": 5, "uuid": "abc", "workspace_id": 7, "file_path": file_path,
        "file_type": "youtube", "filename": "Video.youtube", "status": "pending",
    }


def _stub_ingest_dependencies(monkeypatch, source, calls):
    """Wires db, the embedding provider and the file opener the way every youtube-branch test needs."""
    monkeypatch.setattr(ingestion, "db", _Db(source, calls))
    from src.services import aia_embeddings
    monkeypatch.setattr(aia_embeddings, "get_embedding_provider_with_fallback", lambda: _EmbeddingProvider())
    monkeypatch.setattr(aia_embeddings, "fingerprint_from_dim", lambda provider, dim: "fp")
    # A youtube source has no file, opening one would be the bug this test guards against.
    monkeypatch.setattr(ingestion, "open_input_file", lambda *a, **kw: pytest.fail("must not open a file"))


def test_run_index_source_youtube_branch_uses_the_pasted_transcript(lokal, monkeypatch):
    file_path = storage.save_aia_provided_transcript(1, "w", "abc", _VTT)
    source = _youtube_source(file_path)
    calls = {"chunks": [], "status": []}
    _stub_ingest_dependencies(monkeypatch, source, calls)
    from src.features.ai_assistant.tasks import _helpers
    # The source summary is the only model call left, off here so the guard sees the language alone.
    monkeypatch.setattr(ingestion, "_BUILD_INGEST_SUMMARY", False)
    monkeypatch.setattr(_helpers, "_get_llm_client", lambda: pytest.fail("the language needs no model call"))

    ingestion.run_index_source("abc", "de")

    assert calls["status"][-1][0] == "ready"
    assert calls["status"][-1][1]["duration"] == 9.0
    assert calls["status"][-1][1]["language"] == "de"
    assert calls["chunks"] and calls["chunks"][0]["start_time"] == 0.0
    assert storage.get_file(storage.aia_transcript_key(file_path)).decode("utf-8").count("Hallo") == 1
    assert storage.get_file(storage.aia_vtt_key(file_path, "de")).decode("utf-8").startswith("WEBVTT")


def test_run_index_source_youtube_branch_fails_without_a_stored_transcript(lokal, monkeypatch):
    file_path = str(lokal / "users/1/aia/workspaces/w/sources/abc.youtube")
    source = _youtube_source(file_path)
    calls = {"chunks": [], "status": []}
    _stub_ingest_dependencies(monkeypatch, source, calls)

    with pytest.raises(RuntimeError):
        ingestion.run_index_source("abc", "de")

    assert calls["status"][-1][0] == "failed"


def test_run_index_source_youtube_branch_reads_the_language_locally(lokal, monkeypatch):
    zeile = "Today we look at how plants turn light into sugar and why they need water."
    vtt = f"WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\n{zeile}\n\n2\n00:00:05.000 --> 00:00:10.000\n{zeile}\n"
    file_path = storage.save_aia_provided_transcript(1, "w", "abc", vtt)
    source = _youtube_source(file_path)
    calls = {"chunks": [], "status": []}
    _stub_ingest_dependencies(monkeypatch, source, calls)
    from src.features.ai_assistant.tasks import _helpers
    # The source summary is the only model call left, off here so the guard sees the language alone.
    monkeypatch.setattr(ingestion, "_BUILD_INGEST_SUMMARY", False)
    monkeypatch.setattr(_helpers, "_get_llm_client", lambda: pytest.fail("the language needs no model call"))

    ingestion.run_index_source("abc", "de")

    assert calls["status"][-1][0] == "ready"
    assert calls["status"][-1][1]["language"] == "en"
    assert storage.get_file(storage.aia_vtt_key(file_path, "en")).decode("utf-8").startswith("WEBVTT")
