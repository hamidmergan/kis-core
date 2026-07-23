"""Zusammenfassungs-Generierung (Summary-Tool) via the configured LLM."""

import re

from src.tool_prompts import (
    SUMMARY_DEFAULT as _SUMMARY_DEFAULT,
    SUMMARY_LANGUAGE_FALLBACK as _LANGUAGE_FALLBACK,
    SUMMARY_LANGUAGE_PROBE as _LANGUAGE_PROBE,
)

from src.services.openai_compat_llm.base import load_prompt

# Enough text for a reliable language call, small enough to stay cheap.
_LANGUAGE_SAMPLE_CHARS = 1500

# A language name is one or two words. Anything longer is a chatty answer we drop.
_LANGUAGE_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ -][^\W\d_]+)?$", re.UNICODE)


def _language_sample(text: str, sample_chars: int = _LANGUAGE_SAMPLE_CHARS) -> str:
    """Return a slice from the middle of *text* for the language probe.

    Cover pages, title blocks, footers and imprints sit at the edges of a
    document and are usually written in the institution's language rather than
    the document's. Judging from the opening lines is exactly how an English
    paper ends up summarized in German.
    """
    body = " ".join(text.split())
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
        """Ask the model for the language of a boilerplate-free sample.

        Returns None on any failure, the caller then falls back to a generic
        instruction rather than losing the summary over a probe.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _LANGUAGE_PROBE},
                    {"role": "user", "content": _language_sample(text)},
                ],
                temperature=0,
            )
            return _clean_language_name(response.choices[0].message.content)
        except Exception:
            return None

    def generate_summary(self, text: str) -> str:
        """Generate a plain-text summary of the given text using the configured LLM.

        Args:
            text: The extracted text to summarize.

        Returns:
            A plain-text summary in the language of the source document.

        Raises:
            RuntimeError: If the LLM API returns an error.
        """
        language = self._detect_language(text) or _LANGUAGE_FALLBACK

        template = load_prompt("prompt_summary", _SUMMARY_DEFAULT)
        system_prompt = template.replace("{language}", language)
        if "{language}" not in template:
            system_prompt += f"\nWrite the summary in {language}."

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM hat keine Antwort generiert")
            return content.strip()
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"LLM API error: {e}") from e
