"""Chunked Whisper-Varianten: Audio wird bei Bedarf gesplittet, einzeln
transkribiert und wieder zusammengeführt."""

import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.services.openai_compat_llm import _chunk_cache
from src.services.openai_compat_llm._chunking import (
    CHUNK_MAX_SEC,
    MAX_AUDIO_SEC,
    AudioTooLongError,
    compute_split_points,
    find_silence_starts,
    get_audio_duration,
    split_audio,
)
from src.services.openai_compat_llm._subtitles import merge_srt, merge_vtt
from src.limits import STT_CHUNK_DEFAULT_PARALLELISM, STT_CHUNK_MAX_PARALLELISM

# (finished_chunks, total_chunks) -> None. Fires per finished chunk so a long
# transcription can say "part 3 of 12" instead of just "running".
ProgressFn = Callable[[int, int], None] | None


def chunk_concurrency() -> int:
    """How many chunks of one recording go to the provider at once.

    Read per call, not cached, so a change in the admin panel takes effect on
    the next job without restarting the worker. Unusable values fall back to the
    default and oversized ones are capped: a typo here would otherwise hit the
    provider for the whole university.
    """
    try:
        from src import database as db
        value = int(db.get_setting("stt_chunk_parallelism", str(STT_CHUNK_DEFAULT_PARALLELISM)))
    except Exception:
        return STT_CHUNK_DEFAULT_PARALLELISM
    if value < 1:
        return STT_CHUNK_DEFAULT_PARALLELISM
    return min(value, STT_CHUNK_MAX_PARALLELISM)


def _reject_if_too_long(duration: float) -> None:
    if duration > MAX_AUDIO_SEC:
        raise AudioTooLongError(duration)


def _report(on_progress: ProgressFn, done: int, total: int) -> None:
    """Report chunk progress, never letting a reporting failure kill the job.

    The callback writes to the DB, so a hiccup there would otherwise throw away
    a transcription that actually succeeded.
    """
    if on_progress is None:
        return
    try:
        on_progress(done, total)
    except Exception as e:
        logger.warning("Chunk progress could not be recorded: {}", e)


class _WhisperChunkedMixin:
    """Erwartet alle `_WhisperMixin`-Methoden auf self (via Multi-Inheritance)."""

    def transcribe_chunked(self, file_path: str, response_format: str = "text",
                           cache_key: str | None = None,
                           on_progress: ProgressFn = None) -> str:
        """Transcribe audio, splitting files that exceed KISSKI's 600s limit at silence points.

        ``cache_key`` (e.g. the job_uuid) enables per-chunk Redis caching so a Celery
        retry skips chunks that already succeeded instead of restarting from zero.
        ``on_progress(done, total)`` fires after each finished chunk.
        """
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            return self.transcribe(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit - splitting into chunks", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        def _transcribe_or_cached(path: str, idx: int, total: int) -> str:
            if cache_key:
                hit = _chunk_cache.get_text(cache_key, idx)
                if hit is not None:
                    logger.info("Chunk {}/{} cache hit", idx + 1, total)
                    return hit
            text = self.transcribe(path, response_format=response_format)
            if cache_key:
                _chunk_cache.put_text(cache_key, idx, text)
            return text

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[str, float]] = {}
            with ThreadPoolExecutor(max_workers=chunk_concurrency()) as executor:
                futures = {
                    executor.submit(_transcribe_or_cached, path, i, len(chunks)): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} transcribed", i + 1, len(chunks))
                        _report(on_progress, len(results), len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} transcription failed: {e}") from e

            if cache_key:
                _chunk_cache.clear_text(cache_key, len(chunks))
            ordered = [results[i] for i in range(len(chunks))]
            if response_format == "srt":
                return merge_srt(ordered)
            if response_format == "vtt":
                return merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

    def transcribe_and_translate_chunked(self, file_path: str, response_format: str = "text",
                                         cache_key: str | None = None,
                                         on_progress: ProgressFn = None) -> str:
        """Transcribe and translate audio, splitting files that exceed KISSKI's 600s limit.

        ``cache_key`` (e.g. the job_uuid) enables per-chunk Redis caching so a retry
        skips chunks that already succeeded. ``on_progress(done, total)`` fires
        after each finished chunk.
        """
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            return self.transcribe_and_translate(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit - splitting into chunks (translate mode)", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        def _translate_or_cached(path: str, idx: int, total: int) -> str:
            if cache_key:
                hit = _chunk_cache.get_text(cache_key, idx)
                if hit is not None:
                    logger.info("Chunk {}/{} cache hit (translate)", idx + 1, total)
                    return hit
            text = self.transcribe_and_translate(path, response_format=response_format)
            if cache_key:
                _chunk_cache.put_text(cache_key, idx, text)
            return text

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[str, float]] = {}
            with ThreadPoolExecutor(max_workers=chunk_concurrency()) as executor:
                futures = {
                    executor.submit(_translate_or_cached, path, i, len(chunks)): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} translated", i + 1, len(chunks))
                        _report(on_progress, len(results), len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} translation failed: {e}") from e

            if cache_key:
                _chunk_cache.clear_text(cache_key, len(chunks))
            ordered = [results[i] for i in range(len(chunks))]
            if response_format == "srt":
                return merge_srt(ordered)
            if response_format == "vtt":
                return merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

    def transcribe_chunked_verbose(
        self, file_path: str, cache_key: str | None = None
    ) -> tuple[list[dict], float, str]:
        """Transcribe audio with timestamps, splitting if needed.

        Returns ``(segments, duration, language)`` where segments =
        ``[{start, end, text}, ...]`` and language is the detected source
        language (e.g. 'de', 'en').

        ``cache_key`` (e.g. source_uuid) enables per-chunk Redis caching so
        Celery retries skip chunks that already succeeded.
        """
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            segs, lang = self.transcribe_verbose(file_path)
            return segs, duration, lang

        logger.info("Audio {:.1f}s exceeds limit - splitting for verbose transcription", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        def _transcribe_or_cached(path: str, idx: int) -> tuple[list[dict], str]:
            if cache_key:
                hit = _chunk_cache.get(cache_key, idx)
                if hit is not None:
                    logger.info("Chunk {}/{} cache hit (verbose)", idx + 1, len(chunks))
                    return hit
            segs, lang = self.transcribe_verbose(path)
            if cache_key:
                _chunk_cache.put(cache_key, idx, segs, lang)
            return segs, lang

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[tuple[list[dict], str], float]] = {}
            with ThreadPoolExecutor(max_workers=chunk_concurrency()) as executor:
                futures = {
                    executor.submit(_transcribe_or_cached, path, i): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} transcribed (verbose)", i + 1, len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} verbose transcription failed: {e}") from e

            all_segments: list[dict] = []
            first_lang = ""
            for i in range(len(chunks)):
                (segs, lang), offset = results[i]
                if i == 0:
                    first_lang = lang
                for seg in segs:
                    all_segments.append({
                        "start": seg["start"] + offset,
                        "end": seg["end"] + offset,
                        "text": seg["text"],
                    })

            if cache_key:
                _chunk_cache.clear(cache_key, len(chunks))

        return all_segments, duration, first_lang

    def translate_chunked_verbose(self, file_path: str) -> list[dict]:
        """Translate audio to English with timestamps, splitting if needed.

        Returns segments ``[{start, end, text}, ...]`` in English. Audio
        duration/limit handling mirrors :meth:`transcribe_chunked_verbose`.
        """
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            return self.translate_verbose(file_path)

        logger.info("Audio {:.1f}s exceeds limit - splitting for verbose translation", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[list[dict], float]] = {}
            with ThreadPoolExecutor(max_workers=chunk_concurrency()) as executor:
                futures = {
                    executor.submit(self.translate_verbose, path): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} translated (verbose)", i + 1, len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} verbose translation failed: {e}") from e

            all_segments: list[dict] = []
            for i in range(len(chunks)):
                segs, offset = results[i]
                for seg in segs:
                    all_segments.append({
                        "start": seg["start"] + offset,
                        "end": seg["end"] + offset,
                        "text": seg["text"],
                    })

        return all_segments
