"""Zusammenfassungs-Generierung (Summary-Tool) via KISSKI LLM."""

from src.tool_prompts import SUMMARY_DEFAULT as _SUMMARY_DEFAULT

from src.services.kisski.base import load_prompt


class _SummaryMixin:
    """Erwartet: self._client (OpenAI), self._model."""

    def generate_summary(
        self,
        text: str,
        output_format: str = "txt",
    ) -> str:
        """Generate a summary of the given text using KISSKI LLM.

        Args:
            text: The extracted text to summarize.
            output_format: "txt" (plain text), "md" (Markdown), or "html" (HTML fragment).

        Returns:
            A summary in the requested format.

        Raises:
            RuntimeError: If the LLM API returns an error.
        """
        format_instructions = {
            "md": "Formatiere die Zusammenfassung als Markdown (Überschriften, Aufzählungen etc. wo sinnvoll).",
            "html": (
                "Formatiere die Zusammenfassung als HTML-Fragment "
                "(nur Inhalt, kein <html>/<head>/<body>-Tag)."
            ),
            "txt": "Formatiere die Zusammenfassung als reinen, gut lesbaren Text.",
        }

        system_prompt = load_prompt("prompt_summary", _SUMMARY_DEFAULT).replace(
            "{format}", format_instructions.get(output_format, format_instructions["txt"])
        )

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
            raise RuntimeError(f"KISSKI API Fehler: {e}") from e
