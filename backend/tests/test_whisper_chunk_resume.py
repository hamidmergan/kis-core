"""Resume + caching for the standalone chunked transcription path (general.transcribe).

A chunk that fails (e.g. 429) must not throw away the chunks that already succeeded:
each successful chunk is cached per (job, chunk index) so a re-run skips it. Mirrors the
AIA media-ingestion behaviour for the non-verbose transcription tool.
"""
import pytest

from src.services.openai_compat_llm import _whisper_chunked as wc


class _StubWhisper(wc._WhisperChunkedMixin):
    def __init__(self, fail_on=None):
        self.transcribed: list[int] = []        # chunk indices actually sent to the API
        self._fail_on = set(fail_on or [])

    @staticmethod
    def _idx(path: str) -> int:
        return int(path.split("chunk_")[1].split(".")[0])

    def transcribe(self, path: str, response_format: str = "text") -> str:
        i = self._idx(path)
        self.transcribed.append(i)
        if i in self._fail_on:
            raise RuntimeError("Whisper API error (KISSKI): Error code: 429 - rate limit")
        return f"t{i}"


@pytest.fixture
def store(monkeypatch):
    # Deterministic 4-chunk split, no ffmpeg, no Redis. Serial so the failure order is fixed.
    monkeypatch.setattr(wc, "CHUNK_TRANSCRIBE_CONCURRENCY", 1)
    monkeypatch.setattr(wc, "get_audio_duration", lambda p: 2000.0)
    monkeypatch.setattr(wc, "find_silence_starts", lambda p: [])
    monkeypatch.setattr(wc, "compute_split_points", lambda d, s: [540.0, 1080.0, 1620.0])
    monkeypatch.setattr(
        wc, "split_audio",
        lambda fp, sp, tmp: [(f"{tmp}/chunk_{i:03d}.mp3", i * 540.0) for i in range(len(sp) + 1)],
    )
    cache: dict = {}
    monkeypatch.setattr(wc._chunk_cache, "get_text", lambda k, i: cache.get((k, i)), raising=False)
    monkeypatch.setattr(wc._chunk_cache, "put_text",
                        lambda k, i, t: cache.__setitem__((k, i), t), raising=False)
    monkeypatch.setattr(wc._chunk_cache, "clear_text",
                        lambda k, n: [cache.pop((k, j), None) for j in range(n)], raising=False)
    return cache


def test_failed_chunk_keeps_earlier_chunks_cached(store):
    w = _StubWhisper(fail_on=[2])            # 3rd of 4 chunks fails
    with pytest.raises(RuntimeError, match="Chunk 3 transcription failed"):
        w.transcribe_chunked("f.webm", cache_key="job1")
    # chunks 0 and 1 succeeded before the failure -> cached; the failed chunk 2 is not.
    assert store[("job1", 0)] == "t0"
    assert store[("job1", 1)] == "t1"
    assert ("job1", 2) not in store


def test_rerun_resumes_from_cache(store):
    store[("job1", 0)] = "t0"                # pretend chunks 0,1 finished in a prior run
    store[("job1", 1)] = "t1"
    w = _StubWhisper()                       # this run: nothing fails
    out = w.transcribe_chunked("f.webm", cache_key="job1")
    assert out == "t0 t1 t2 t3"             # full text assembled in chunk order
    assert w.transcribed == [2, 3]          # only the uncached chunks hit the API
    # a fully successful run clears the cache for that job
    assert ("job1", 0) not in store and ("job1", 3) not in store


def test_no_cache_key_means_no_caching(store):
    w = _StubWhisper(fail_on=[1])
    with pytest.raises(RuntimeError):
        w.transcribe_chunked("f.webm")      # cache_key omitted -> resume disabled
    assert store == {}


def test_translate_chunked_also_resumes(store):
    # The translate variant shares the same cache wiring.
    store[("job2", 0)] = "t0"
    w = _StubWhisper()
    w.transcribe_and_translate = w.transcribe  # same stub for the translate call
    out = w.transcribe_and_translate_chunked("f.webm", cache_key="job2")
    assert out == "t0 t1 t2 t3"
    assert w.transcribed == [1, 2, 3]       # chunk 0 came from cache
