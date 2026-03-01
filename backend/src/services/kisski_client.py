"""KISSKI LLM client – OpenAI-compatible wrapper for script generation and Whisper transcription."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger
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
    "- Halte das Skript prägnant: zwischen 20 und 100 Wörter. Nicht kürzer, nicht länger."
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
    "- Keep the script concise: between 20 and 100 words. Not shorter, not longer."
)


def _load_prompt(key: str, default: str) -> str:
    """Load a system prompt from DB settings, falling back to the hardcoded default."""
    try:
        from src import database as db
        val = db.get_setting(key, "")
        return val if val.strip() else default
    except Exception:
        return default


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
        default_prompt = _SYSTEM_PROMPT_EN if language.upper() == "EN" else _SYSTEM_PROMPT_DE
        prompt_key = "prompt_script_en" if language.upper() == "EN" else "prompt_script_de"
        system_prompt = _load_prompt(prompt_key, default_prompt)
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            system_prompt = f"Use the following terminology consistently in your output:\n{lines}\n\n" + system_prompt
        # user_prompt goes in the user message (not system) to keep the system prompt English-only
        user_message = text
        if user_prompt and user_prompt.strip():
            user_message += (
                f"\n\nAdditional instructions to apply "
                f"(apply semantically, output must remain in English):\n{user_prompt.strip()}"
            )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM hat keine Antwort generiert")
            return content.strip()
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI API Fehler: {e}") from e

    def _generate_scripts_single_batch(
        self,
        batch_texts: list[str],
        batch_index: int,
        batch_count: int,
        global_start: int,
        total_slides: int,
        user_prompt: str | None,
        glossary: dict[str, str] | None,
    ) -> list[str]:
        """Run one LLM call for a slice of slides and return scripts for that slice.

        Uses a plain-text separator (|||) instead of JSON so response truncation
        never causes a parse failure – whatever the LLM writes is usable.
        """
        batch_size = len(batch_texts)
        global_end = global_start + batch_size  # exclusive

        # Build slide input with global slide numbers for context
        slides_input = ""
        for local_i, text in enumerate(batch_texts):
            global_i = global_start + local_i
            position = f"Slide {global_i + 1} of {total_slides}"
            if global_i == 0:
                position += " (first slide)"
            slides_input += f"### {position}\n{text.strip() if text.strip() else '[empty slide]'}\n\n"

        # Build system prompt (English-only – no German text here)
        glossary_hint = ""
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            glossary_hint = f"Use the following terminology consistently in your output:\n{lines}\n\n"

        system_prompt = glossary_hint + (
            "You are an expert at creating spoken narration scripts for presentation slides. "
            f"Generate a spoken script for EACH of the {batch_size} slides below "
            f"(slides {global_start + 1} to {global_end} of {total_slides} total). "
            "Rules:\n"
            "- Do NOT add any new information.\n"
            "- Do NOT hallucinate.\n"
            "- Keep all facts, numbers, names, and dates exactly as they are.\n"
            "- Output MUST be in English.\n"
            "- Convert bullet points, tables, and lists into flowing text.\n"
            "- Remove citations, footnotes, and formatting artifacts.\n"
            "- NO semicolons, NO dashes – use only periods and commas.\n"
            "- Address the audience directly as 'you'.\n"
            "- Natural, conversational tone – like a university lecturer speaking.\n"
            "- Only use a greeting on slide 1 of the full presentation if the content clearly indicates a title or introduction.\n"
            "- Never use greetings on any other slide.\n"
            "- Keep each script between 20 and 100 words.\n"
            "- For empty slides, output nothing (just write the ||| delimiter).\n"
            "- Do NOT add closing statements like 'thank you', 'any questions', or 'that concludes' on any slide.\n"
            "\n"
            f"Separate the {batch_size} scripts using the delimiter ||| on its own line. "
            "No other text before, between, or after. Example format for 3 slides:\n"
            "Script text for slide one.\n"
            "|||\n"
            "Script text for slide two.\n"
            "|||\n"
            "Script text for slide three."
        )

        # user_prompt goes in the user message (not system) to keep system prompt English-only
        user_message = slides_input
        if user_prompt and user_prompt.strip():
            user_message += (
                f"\n\nAdditional instructions to apply to each script "
                f"(apply semantically, output must remain in English):\n{user_prompt.strip()}\n"
                f"Note: instructions mentioning 'last slide' apply only to slide {total_slides}."
            )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=batch_size * 350,
            )
            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError(f"Batch {batch_index + 1}/{batch_count}: LLM returned empty response")

            # Parse separator-delimited output – truncation just means a shorter last script
            parts = re.split(r"\|\|\|", content)
            scripts = [p.strip() for p in parts]

            if len(scripts) != batch_size:
                logger.warning(
                    "Batch {}/{}: expected {} scripts, got {} – padding/trimming",
                    batch_index + 1, batch_count, batch_size, len(scripts),
                )
                scripts = (scripts + [""] * batch_size)[:batch_size]

            return scripts

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI API Fehler (Batch {batch_index + 1}): {e}") from e

    def generate_scripts_batch(
        self, slide_texts: list[str], user_prompt: str | None = None,
        glossary: dict[str, str] | None = None,
        batch_size: int = 3,
        max_workers: int = 10,
    ) -> list[str]:
        """Generate spoken scripts for all slides, split into parallel batches.

        Slides are divided into groups of up to `batch_size` and all batches are
        submitted concurrently via ThreadPoolExecutor. Results are reassembled in
        the original slide order. Batches that fail return empty strings instead
        of raising so partial results are always delivered.

        Args:
            slide_texts: List of extracted text per slide.
            user_prompt: Optional additional instructions from the user.
            glossary: Optional term mapping to enforce in the output.
            batch_size: Maximum number of slides per LLM call (default 3).
            max_workers: Maximum parallel LLM threads (default 10).

        Returns:
            List of scripts in the same order as slide_texts.
        """
        total_slides = len(slide_texts)

        # Split into batches
        batches: list[tuple[int, list[str]]] = []  # (global_start, texts)
        for start in range(0, total_slides, batch_size):
            batches.append((start, slide_texts[start:start + batch_size]))

        batch_count = len(batches)
        logger.info(
            "Generating scripts for {} slides in {} batch(es) of up to {} (max_workers={})",
            total_slides, batch_count, batch_size, max_workers,
        )

        results: dict[int, list[str]] = {}  # batch_index → scripts

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._generate_scripts_single_batch,
                    texts, idx, batch_count, global_start, total_slides,
                    user_prompt, glossary,
                ): (idx, len(texts))
                for idx, (global_start, texts) in enumerate(batches)
            }
            for future in as_completed(futures):
                idx, n = futures[future]
                try:
                    results[idx] = future.result()
                    logger.info("Batch {}/{} completed", idx + 1, batch_count)
                except RuntimeError as e:
                    logger.warning(
                        "Batch {}/{} failed: {} – returning empty strings for {} slide(s)",
                        idx + 1, batch_count, e, n,
                    )
                    results[idx] = [""] * n

        # Reassemble in slide order
        ordered: list[str] = []
        for idx in range(batch_count):
            ordered.extend(results[idx])

        return ordered

    def summarize(self, text: str, task: str = "transcribe") -> str:
        """Summarize a transcript using KISSKI LLM.

        Args:
            text: Transcript text to summarize.
            task: "transcribe" (summarize in source language) or
                  "translate" (summarize in English).

        Returns:
            A short plain-text summary.

        Raises:
            RuntimeError: If the LLM API returns an error.
        """
        _default_summarize = (
            "Erstelle eine ausführliche Zusammenfassung des folgenden Transkripts. "
            "Erfasse alle wichtigen Themen, Argumente, Fakten, Zahlen und Schlussfolgerungen vollständig. "
            "Die Zusammenfassung soll strukturiert und gut lesbar sein, aber nichts Wesentliches auslassen. "
            "Antworte nur mit der Zusammenfassung, ohne Einleitung oder Erklärung."
        )
        system_content = _load_prompt("prompt_summarize", _default_summarize)
        if task == "translate":
            system_content += " Respond in English."

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_content},
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

    def generate_summary(
        self,
        text: str,
        user_prompt: str | None = None,
        output_format: str = "txt",
    ) -> str:
        """Generate a summary of the given text using KISSKI LLM.

        Args:
            text: The extracted text to summarize.
            user_prompt: Optional additional instructions appended below the base prompt.
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

        _default_summary = (
            "Erstelle eine Zusammenfassung ausschließlich basierend auf dem folgenden Inhalt. "
            "Erfinde nichts, ergänze nichts, interpretiere nichts was nicht explizit im Text steht. "
            "{format} "
            "Antworte nur mit der Zusammenfassung, ohne einleitende oder abschließende Erklärung."
        )
        system_prompt = _load_prompt("prompt_summary", _default_summary).replace(
            "{format}", format_instructions.get(output_format, format_instructions["txt"])
        )

        if user_prompt:
            system_prompt += f"\n\nZusätzliche Anweisungen:\n{user_prompt}"

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
