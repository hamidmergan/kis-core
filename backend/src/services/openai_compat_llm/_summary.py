"""Zusammenfassungs-Generierung (Summary-Tool) via the configured LLM."""

import re

from src.tool_prompts import (
    SUMMARY_DEFAULT as _SUMMARY_DEFAULT,
    SUMMARY_LANGUAGE_FALLBACK as _LANGUAGE_FALLBACK,
    SUMMARY_LANGUAGE_PROBE as _LANGUAGE_PROBE,
)

from src.services.openai_compat_llm.base import load_prompt
from src.security.usage_log import log_llm_response as _verbrauch

# Enough text for a reliable language call, small enough to stay cheap.
_LANGUAGE_SAMPLE_CHARS = 1500

# A language name is one or two words. Anything longer is a chatty answer we drop.
_LANGUAGE_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ -][^\W\d_]+)?$", re.UNICODE)


def _language_sample(text: str, sample_chars: int = _LANGUAGE_SAMPLE_CHARS) -> str:
    """An excerpt from the middle as a language sample, the edges mislead."""
    if len(text) <= sample_chars:
        return " ".join(text.split())
    mid = len(text) // 2
    # Normalise only the window, not the whole text.
    window = text[max(0, mid - sample_chars): mid + sample_chars]
    body = " ".join(window.split())
    if len(body) <= sample_chars:
        return body
    start = (len(body) - sample_chars) // 2
    return body[start:start + sample_chars]


def _clean_language_name(raw: str | None) -> str | None:
    """Reduce a probe answer to a bare language name, or None if it is not one."""
    name = (raw or "").strip().strip(".!\"'").strip()
    if not name or len(name) > 30:
        return None
    return name if _LANGUAGE_NAME_RE.match(name) else None


class _SummaryMixin:
    """Erwartet: self._client (OpenAI), self._model."""

    def _detect_language(self, text: str) -> str | None:
        """Asks the model for the language of the sample, None on any error."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _LANGUAGE_PROBE},
                    {"role": "user", "content": _language_sample(text)},
                ],
                temperature=0,
            )
            _verbrauch("summary", self, response)
            return _clean_language_name(response.choices[0].message.content)
        except Exception:
            return None

    def generate_summary(self, text: str) -> str:
        """Generates a summary in the language of the source text."""
        language = self._detect_language(text) or _LANGUAGE_FALLBACK

        template = load_prompt("prompt_summary", _SUMMARY_DEFAULT)
        system_prompt = template.replace("{language}", language)
        if "{language}" not in template:
            system_prompt += f"\nWrite the summary in {language}."
        # An old placeholder from the database is escaped instead of passed through.
        system_prompt = system_prompt.replace("{format}", "plain text")

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            _verbrauch("summary", self, response)
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM hat keine Antwort generiert")
            return content.strip()
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"LLM API error: {e}") from e
