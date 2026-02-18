"""KISSKI LLM client – OpenAI-compatible wrapper for script generation and Whisper transcription."""

import json
import re
from pathlib import Path

from openai import OpenAI

_SYSTEM_PROMPT_DE = (
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
    "- Das Skript soll sich wie ein Universitätsdozent anhören der spricht.\n"
    "- Keine Semikolons und keine Gedankenstriche – nur Punkte und Kommas.\n"
    "- Sprich die Zuhörer direkt an mit 'Sie'.\n"
    "- Beginne NICHT jede Folie mit einer Begrüßung – nur auf der Titelfolie.\n"
    "- Beende das Skript NICHT mit Füllphrasen wie 'Lassen Sie uns beginnen'.\n"
    "- Halte das Skript prägnant: zwischen 20 und 200 Wörter. Nicht kürzer, nicht länger."
)

_SYSTEM_PROMPT_EN = (
    "You are an expert at creating spoken narration scripts for individual presentation slides. "
    "Convert the slide content into a fluent, spoken script for ONE slide only. "
    "Rules:\n"
    "- Do NOT add any new information.\n"
    "- Do NOT hallucinate.\n"
    "- Keep all facts, numbers, names, and dates exactly as they are.\n"
    "- The output MUST be in English.\n"
    "- Convert bullet points, tables, and lists into flowing text.\n"
    "- Remove citations, footnotes, and formatting artifacts.\n"
    "- Add natural transitions between sections.\n"
    "- NO semicolons, NO dashes – use only periods and commas.\n"
    "- Address the audience directly as 'you'.\n"
    "- Natural, conversational tone – like a university lecturer speaking.\n"
    "- Do NOT start with 'Welcome' or greetings on every slide – only on the title slide.\n"
    "- Do NOT end with filler phrases like 'Let us dive in' or 'Let us get started'.\n"
    "- Keep the script concise: between 20 and 200 words. Not shorter, not longer."
)


def _clean_whisper_response(raw: str) -> str:
    """Clean Whisper API response that may be JSON-encoded (wrapped in quotes with escaped newlines)."""
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            text = text[1:-1]
            text = text.replace("\\n", "\n").replace("\\r", "\r")
    return text.strip()


class KisskiClient:
    """Lightweight wrapper around the KISSKI (GWDG) OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate_script(
        self, text: str, language: str = "DE", user_prompt: str | None = None,
        glossary: dict[str, str] | None = None,
    ) -> str:
        """Convert extracted document text into a spoken script.

        Args:
            text: Raw text extracted from a document.
            language: Output language – 'DE' (default) or 'EN'.
            user_prompt: Optional additional instructions appended to the system prompt.

        Returns:
            A fluent, spoken-style script based on the input text.

        Raises:
            RuntimeError: If the LLM API returns an error.
        """
        system_prompt = _SYSTEM_PROMPT_EN if language.upper() == "EN" else _SYSTEM_PROMPT_DE
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            system_prompt = f"Use the following terminology consistently in your output:\n{lines}\n\n" + system_prompt
        if user_prompt:
            system_prompt += f"""

Additional instructions from the user (written in German – interpret them semantically and apply them to the English output):
{user_prompt}

Important: Do NOT translate German words literally into the script.
Example: "Sprich die Zuhörer direkt an mit Sie" means use a formal, direct tone addressing the audience as "you" in English – not the word "Sie".
Example: "Kurze Sätze" means write short sentences in English.
Always apply the intent, not the literal words.
"""
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

    def generate_scripts_batch(
        self, slide_texts: list[str], user_prompt: str | None = None,
        glossary: dict[str, str] | None = None,
    ) -> list[str]:
        """Generate spoken scripts for all slides in a single LLM call.

        Args:
            slide_texts: List of extracted text per slide.
            user_prompt: Optional additional instructions from the user.

        Returns:
            List of scripts in the same order as slide_texts.

        Raises:
            RuntimeError: If the LLM API returns an error or invalid JSON.
        """
        slide_count = len(slide_texts)

        # Build input with slide context
        slides_input = ""
        for i, text in enumerate(slide_texts):
            if i == 0:
                position = f"Slide {i + 1} of {slide_count} (first slide)"
            elif i == slide_count - 1:
                position = f"Slide {i + 1} of {slide_count} (last slide)"
            else:
                position = f"Slide {i + 1} of {slide_count}"

            slides_input += f"### {position}\n{text.strip() if text.strip() else '[empty slide]'}\n\n"

        # Build system prompt
        glossary_hint = ""
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            glossary_hint = f"Use the following terminology consistently in your output:\n{lines}\n\n"
        system_prompt = glossary_hint + (
            "You are an expert at creating spoken narration scripts for presentation slides. "
            "You will receive all slides at once. Generate a spoken script for EACH slide. "
            "Rules:\n"
            "- Do NOT add any new information.\n"
            "- Do NOT hallucinate.\n"
            "- Keep all facts, numbers, names, and dates exactly as they are.\n"
            "- The output MUST be in English.\n"
            "- Convert bullet points, tables, and lists into flowing text.\n"
            "- Remove citations, footnotes, and formatting artifacts.\n"
            "- NO semicolons, NO dashes – use only periods and commas.\n"
            "- Address the audience directly as 'you'.\n"
            "- Natural, conversational tone – like a university lecturer speaking.\n"
            "- Only use a greeting on the first slide if the content clearly indicates a title or introduction.\n"
            "- Never use greetings on any other slide.\n"
            "- Keep each script between 20 and 200 words.\n"
            "- For empty slides, return an empty string.\n"
            "- Do NOT add closing statements like 'thank you', 'thank you for your attention', "
            "  'any questions', 'that concludes' on ANY slide – not even the last slide – "
            "  unless the user explicitly requests it in the additional instructions below.\n"
            "- You have full context of all slides – use it for natural transitions and correct placement of opening and closing statements.\n"
            "\n"
            "Return ONLY a valid JSON object with this exact structure. "
            "No markdown, no code blocks, no explanation, no text before or after:\n"
            '{"scripts": ["script for slide 1", "script for slide 2", ...]}\n'
            f"The array must contain exactly {slide_count} entries in the same order as the input slides."
        )

        if user_prompt and user_prompt.strip():
            system_prompt += (
                f"\n\nAdditional instructions from the user:\n{user_prompt.strip()}\n\n"
                "IMPORTANT: Apply these instructions semantically to the English output. "
                "Example: 'Sprich die Zuhörer mit Sie an' means use formal 'you' in English. "
                "Instructions mentioning 'last slide' or 'final slide' apply ONLY to the last slide."
            )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": slides_input},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM hat keine Antwort generiert")

            # Strip markdown code blocks robustly
            content = re.sub(r"```(?:json)?\s*", "", content).strip()
            content = content.strip("`").strip()

            data = json.loads(content)
            scripts = data.get("scripts", [])

            if len(scripts) != slide_count:
                raise RuntimeError(
                    f"LLM returned {len(scripts)} scripts but expected {slide_count}. "
                    "The model did not follow the required JSON structure."
                )

            return [str(s).strip() for s in scripts]

        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"LLM returned invalid JSON: {e}. "
                f"Raw response was: {content[:200]}"
            ) from e
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI API Fehler: {e}") from e

    def transcribe(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio in its original language using KISSKI Whisper.

        Args:
            file_path: Path to the audio file.
            response_format: Output format – "text", "srt", or "vtt".

        Returns:
            Transcription in the requested format.

        Raises:
            RuntimeError: If the Whisper API returns an error.
        """
        try:
            with open(file_path, "rb") as f:
                response = self._client.audio.transcriptions.create(
                    model="whisper-large-v2",
                    file=f,
                    response_format=response_format,
                )
            if not response:
                raise RuntimeError("Whisper returned no output")
            return _clean_whisper_response(str(response))
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI Whisper API error: {e}") from e

    def transcribe_and_translate(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio and translate to English using KISSKI Whisper.

        Args:
            file_path: Path to the audio file.
            response_format: Output format – "text", "srt", or "vtt".

        Returns:
            English translation of the audio content in the requested format.

        Raises:
            RuntimeError: If the Whisper API returns an error.
        """
        try:
            with open(file_path, "rb") as f:
                response = self._client.audio.transcriptions.create(
                    model="whisper-large-v2",
                    file=f,
                    response_format=response_format,
                    extra_body={"task": "translate"},
                )
            if not response:
                raise RuntimeError("Whisper returned no output")
            return _clean_whisper_response(str(response))
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI Whisper API error: {e}") from e
