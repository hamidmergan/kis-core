"""Whisper Transcription/Translation (non-chunked) + verbose_json Varianten."""

import json
import time

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.services.kisski.base import clean_whisper_response, is_transient_error


class _WhisperMixin:
    """Erwartet: self._client (OpenAI), self._provider, self._base_url."""

    @observe(name="whisper-transcribe")
    def transcribe(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio in its original language using KISSKI Whisper."""
        langfuse_context.update_current_observation(
            metadata={"provider": self._provider, "base_url": self._base_url, "model": self._whisper_model},
        )
        try:
            with open(file_path, "rb") as f:
                result = str(self._client.audio.transcriptions.create(
                    model=self._whisper_model,
                    file=f,
                    response_format=response_format,
                ))
            if not result:
                raise RuntimeError("Whisper returned no output")
            return clean_whisper_response(result)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI Whisper API error: {e}") from e

    @observe(name="whisper-translate")
    def transcribe_and_translate(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio and translate to English using KISSKI Whisper."""
        langfuse_context.update_current_observation(
            metadata={"provider": self._provider, "base_url": self._base_url, "model": self._whisper_model},
        )
        try:
            with open(file_path, "rb") as f:
                response = self._client.audio.translations.create(
                    model=self._whisper_model,
                    file=f,
                    response_format=response_format,
                )
            if not response:
                raise RuntimeError("Whisper returned no output")
            return clean_whisper_response(str(response))
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI Whisper API error: {e}") from e

    def _verbose_call(self, file_path: str, translate: bool) -> tuple[list[dict], str]:
        """Shared helper: call Whisper verbose_json for transcribe or translate.

        Returns ``(segments, language)`` where *language* is the detected source
        language code (e.g. 'de', 'en'). For the translations endpoint the
        output text is always English regardless of *language*.
        """
        backoffs = [5, 15]  # 3 attempts total: immediate, +5s, +15s
        last_err: Exception | None = None
        for attempt in range(len(backoffs) + 1):
            try:
                with open(file_path, "rb") as f:
                    endpoint = self._client.audio.translations if translate else self._client.audio.transcriptions
                    result = endpoint.create(
                        model=self._whisper_model,
                        file=f,
                        response_format="verbose_json",
                    )
                if hasattr(result, "segments") and result.segments:
                    segs = [{"start": s.start, "end": s.end, "text": s.text.strip()}
                            for s in result.segments if getattr(s, "text", "").strip()]
                    lang = getattr(result, "language", "") or ""
                    return segs, lang
                data = json.loads(str(result)) if isinstance(result, str) else result
                if isinstance(data, dict):
                    segs = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                            for s in data.get("segments", []) if s.get("text", "").strip()]
                    return segs, data.get("language", "") or ""
                return [], ""
            except Exception as e:
                last_err = e
                if attempt < len(backoffs) and is_transient_error(e):
                    wait = backoffs[attempt]
                    mode = "translate" if translate else "transcribe"
                    logger.warning(
                        "KISSKI Whisper {} verbose_json error (attempt {}/{}): {} – retrying in {}s",
                        mode, attempt + 1, len(backoffs) + 1, e, wait,
                    )
                    time.sleep(wait)
                    continue
                break
        raise RuntimeError(f"KISSKI Whisper verbose_json error: {last_err}") from last_err

    def transcribe_verbose(self, file_path: str) -> tuple[list[dict], str]:
        """Transcribe audio in source language. Returns ``(segments, language)``."""
        return self._verbose_call(file_path, translate=False)

    def translate_verbose(self, file_path: str) -> list[dict]:
        """Translate audio to English (Whisper translate task). Returns segments only."""
        segs, _ = self._verbose_call(file_path, translate=True)
        return segs
