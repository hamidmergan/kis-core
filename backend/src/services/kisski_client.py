"""KISSKI LLM client – OpenAI-compatible wrapper for script generation."""

from openai import OpenAI

_SYSTEM_PROMPT = (
    "Du bist ein Experte für die Erstellung von Vorleseskripten. "
    "Erstelle aus dem folgenden Dokumentinhalt ein fließendes, gesprochenes Skript, "
    "das sich natürlich anhört, wenn es vorgelesen wird. "
    "Regeln:\n"
    "- Füge KEINE neuen Informationen hinzu.\n"
    "- Halluziniere NICHT.\n"
    "- Behalte alle Fakten, Zahlen, Namen und Daten exakt bei.\n"
    "- Verwende die gleiche Sprache wie der Input-Text.\n"
    "- Wandle Stichpunkte, Tabellen und Aufzählungen in fließenden Text um.\n"
    "- Entferne Quellenangaben, Fußnoten und Formatierungsartefakte.\n"
    "- Füge natürliche Übergänge zwischen Abschnitten ein.\n"
    "- Das Skript soll sich wie ein Podcast oder Hörbuch anhören."
)


class KisskiClient:
    """Lightweight wrapper around the KISSKI (GWDG) OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate_script(self, text: str) -> str:
        """Convert extracted document text into a spoken script.

        Args:
            text: Raw text extracted from a document.

        Returns:
            A fluent, spoken-style script based on the input text.

        Raises:
            RuntimeError: If the LLM API returns an error.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
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
