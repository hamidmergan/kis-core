"""Whisper with parts: cut when needed, recognise individually, merge."""

import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.services.openai_compat_llm import _chunk_cache
from src.services.openai_compat_llm._chunking import (
    AudioTooLongError,
    compute_split_points,
    find_silence_starts,
    fits_single_upload,
    get_audio_duration,
    split_audio,
)
from src.services.openai_compat_llm._subtitles import merge_srt, merge_vtt
from src.limits import STT_CHUNK_PARALLELISM

# Reports the progress after every finished part.
ProgressFn = Callable[[int, int], None] | None


def chunk_concurrency() -> int:
    """How many parts go to the provider at once."""
    return STT_CHUNK_PARALLELISM


def _reject_if_too_long(duration: float) -> None:
    """Limit from the admin area, not from the code, see services/tool_limits.py."""
    from src.services.tool_limits import max_transcription_seconds

    grenze = max_transcription_seconds()
    if duration > grenze:
        raise AudioTooLongError(duration, grenze)


def _fail_chunk(kind: str, index: int, error: Exception) -> RuntimeError:
    """One uniform error message for a failed part."""
    return RuntimeError(f"Chunk {index + 1} {kind} failed: {error}")


def _report(on_progress: ProgressFn, done: int, total: int) -> None:
    """Reports the progress, an error there must not kill the job."""
    if on_progress is None:
        return
    try:
        on_progress(done, total)
    except Exception as e:
        logger.warning("Chunk progress could not be recorded: {}", e)


class _WhisperChunkedMixin:
    """Expects all `_WhisperMixin` methods on self via multiple inheritance."""

    def transcribe_chunked(self, file_path: str, response_format: str = "text",
                           cache_key: str | None = None,
                           on_progress: ProgressFn = None) -> str:
        """Recognises language, cuts overlong recordings and remembers every part."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if fits_single_upload(file_path, duration):
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
                        raise _fail_chunk("transcription", i, e) from e

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
        """Recognises and translates, cuts overlong recordings and remembers every part."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if fits_single_upload(file_path, duration):
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
                        raise _fail_chunk("translation", i, e) from e

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
        """Recognises with timestamps and returns segments, duration and language."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if fits_single_upload(file_path, duration):
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
                        raise _fail_chunk("verbose transcription", i, e) from e

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
        """Translates into English with timestamps, like recognition with parts."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if fits_single_upload(file_path, duration):
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
                        raise _fail_chunk("verbose translation", i, e) from e

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
