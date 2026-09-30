"""Zusammenfassungs-Generierung (Summary-Tool) via the configured LLM."""

from src.tool_prompts import (
    SUMMARY_DEFAULT as _SUMMARY_DEFAULT,
    SUMMARY_LANGUAGE_FALLBACK as _LANGUAGE_FALLBACK,
)

from src.services.openai_compat_llm.base import load_prompt
from src.services.text_language import language_name
from src.security.usage_log import log_llm_response as _verbrauch


class _SummaryMixin:
    """Erwartet: self._client (OpenAI), self._model."""

    def generate_summary(self, text: str) -> str:
        """Generates a summary in the language of the source text."""
        language = language_name(text) or _LANGUAGE_FALLBACK

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
