"""Chunked Whisper-Varianten: Audio wird bei Bedarf gesplittet, einzeln
transkribiert und wieder zusammengeführt."""

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.services.openai_compat_llm._chunking import (
    CHUNK_MAX_SEC,
    MAX_AUDIO_SEC,
    compute_split_points,
    find_silence_starts,
    get_audio_duration,
    split_audio,
)
from src.services.openai_compat_llm._subtitles import merge_srt, merge_vtt


def _reject_if_too_long(duration: float) -> None:
    if duration > MAX_AUDIO_SEC:
        raise RuntimeError(
            f"Audio zu lang ({duration / 60:.1f} min). Maximum: {MAX_AUDIO_SEC // 60} Minuten."
        )


class _WhisperChunkedMixin:
    """Erwartet alle `_WhisperMixin`-Methoden auf self (via Multi-Inheritance)."""

    def transcribe_chunked(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio, splitting files that exceed KISSKI's 600s limit at silence points."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            return self.transcribe(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit - splitting into chunks", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[str, float]] = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self.transcribe, path, response_format): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} transcribed", i + 1, len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} transcription failed: {e}") from e

            ordered = [results[i] for i in range(len(chunks))]
            if response_format == "srt":
                return merge_srt(ordered)
            if response_format == "vtt":
                return merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

    def transcribe_and_translate_chunked(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe and translate audio, splitting files that exceed KISSKI's 600s limit."""
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            return self.transcribe_and_translate(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit - splitting into chunks (translate mode)", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[str, float]] = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self.transcribe_and_translate, path, response_format): (i, offset)
                    for i, (path, offset) in enumerate(chunks)
                }
                for future in as_completed(futures):
                    i, offset = futures[future]
                    try:
                        results[i] = (future.result(), offset)
                        logger.info("Chunk {}/{} translated", i + 1, len(chunks))
                    except Exception as e:
                        raise RuntimeError(f"Chunk {i + 1} translation failed: {e}") from e

            ordered = [results[i] for i in range(len(chunks))]
            if response_format == "srt":
                return merge_srt(ordered)
            if response_format == "vtt":
                return merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

    def transcribe_chunked_verbose(self, file_path: str) -> tuple[list[dict], float, str]:
        """Transcribe audio with timestamps, splitting if needed.

        Returns ``(segments, duration, language)`` where segments =
        ``[{start, end, text}, ...]`` and language is the detected source
        language (e.g. 'de', 'en').
        """
        duration = get_audio_duration(file_path)
        _reject_if_too_long(duration)
        if duration <= CHUNK_MAX_SEC:
            segs, lang = self.transcribe_verbose(file_path)
            return segs, duration, lang

        logger.info("Audio {:.1f}s exceeds limit - splitting for verbose transcription", duration)
        silence_starts = find_silence_starts(file_path)
        split_points = compute_split_points(duration, silence_starts)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = split_audio(file_path, split_points, tmpdir)
            results: dict[int, tuple[tuple[list[dict], str], float]] = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self.transcribe_verbose, path): (i, offset)
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
            with ThreadPoolExecutor(max_workers=4) as executor:
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
