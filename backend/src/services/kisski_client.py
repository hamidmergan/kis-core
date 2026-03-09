"""KISSKI LLM client – OpenAI-compatible wrapper for script generation and Whisper transcription."""

import json
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger
from openai import OpenAI

# ── Audio chunking constants ───────────────────────────────────────────────────

_CHUNK_MAX_SEC = 540        # 9 min – safely under KISSKI's 600 s limit
_MAX_AUDIO_SEC = 6000       # 100 min – hard limit for transcription uploads
_SILENCE_NOISE_DB = -40     # dB threshold for silence detection
_SILENCE_MIN_DURATION = 0.3  # minimum silence duration to consider (seconds)
_SPLIT_SEARCH_WINDOW = 60   # seconds to search around each target split point


# ── Audio chunking helpers ─────────────────────────────────────────────────────

def _get_audio_duration(file_path: str) -> float:
    """Return audio/video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        duration = stream.get("duration")
        if duration:
            return float(duration)
    raise RuntimeError("Could not determine audio duration via ffprobe")


def _find_silence_starts(file_path: str) -> list[float]:
    """Run ffmpeg silencedetect and return a list of silence_start timestamps."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-af", f"silencedetect=noise={_SILENCE_NOISE_DB}dB:d={_SILENCE_MIN_DURATION}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    output = result.stderr + result.stdout
    return [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([\d.]+)", output)]


def _compute_split_points(duration: float, silence_starts: list[float]) -> list[float]:
    """Return split timestamps aligned to nearby silence points."""
    split_points: list[float] = []
    target = _CHUNK_MAX_SEC
    while target < duration - 10:
        window_min = target - _SPLIT_SEARCH_WINDOW
        window_max = target + _SPLIT_SEARCH_WINDOW
        candidates = [s for s in silence_starts if window_min <= s <= window_max]
        best = min(candidates, key=lambda s: abs(s - target)) if candidates else target
        split_points.append(best)
        target = best + _CHUNK_MAX_SEC
    return split_points


def _split_audio(file_path: str, split_points: list[float], tmpdir: str) -> list[tuple[str, float]]:
    """Split audio at given timestamps (stream-copy, no re-encode).

    Returns list of (chunk_path, start_offset_seconds).
    """
    ext = Path(file_path).suffix
    boundaries = [0.0] + split_points + [None]  # None = end of file
    chunks: list[tuple[str, float]] = []
    for i, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        chunk_path = str(Path(tmpdir) / f"chunk_{i:03d}{ext}")
        cmd = ["ffmpeg", "-i", file_path, "-ss", str(start)]
        if end is not None:
            cmd += ["-to", str(end)]
        cmd += ["-c", "copy", "-y", chunk_path]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg split failed for chunk {i}: {result.stderr[:200]}")
        chunks.append((chunk_path, start))
    return chunks


# ── Transcript merging helpers ─────────────────────────────────────────────────

def _offset_srt_ts(ts: str, offset_sec: float) -> str:
    """Shift an SRT timestamp (HH:MM:SS,mmm) by offset_sec."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
    total_ms = max(0, total_ms + int(offset_sec * 1000))
    h2, total_ms = divmod(total_ms, 3_600_000)
    m2, total_ms = divmod(total_ms, 60_000)
    s2, ms2 = divmod(total_ms, 1000)
    return f"{h2:02d}:{m2:02d}:{s2:02d},{ms2:03d}"


def _merge_srt(chunks: list[tuple[str, float]]) -> str:
    """Merge SRT chunks, shifting timestamps and renumbering entries."""
    entries: list[tuple[str, str, str]] = []
    for text, offset in chunks:
        for block in re.split(r"\n\n+", text.strip()):
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
            if not m:
                continue
            entries.append((_offset_srt_ts(m.group(1), offset), _offset_srt_ts(m.group(2), offset), "\n".join(lines[2:])))
    return "\n".join(f"{i}\n{s} --> {e}\n{c}\n" for i, (s, e, c) in enumerate(entries, 1))


def _offset_vtt_ts(ts: str, offset_sec: float) -> str:
    """Shift a VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) by offset_sec."""
    parts = ts.split(":")
    h, m, s_ms = (parts[0], parts[1], parts[2]) if len(parts) == 3 else ("0", parts[0], parts[1])
    s, ms = s_ms.split(".")
    total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
    total_ms = max(0, total_ms + int(offset_sec * 1000))
    h2, total_ms = divmod(total_ms, 3_600_000)
    m2, total_ms = divmod(total_ms, 60_000)
    s2, ms2 = divmod(total_ms, 1000)
    return f"{h2:02d}:{m2:02d}:{s2:02d}.{ms2:03d}"


def _merge_vtt(chunks: list[tuple[str, float]]) -> str:
    """Merge VTT chunks, shifting timestamps."""
    cues: list[str] = []
    for text, offset in chunks:
        lines = text.splitlines()
        # skip WEBVTT header line(s)
        i = 0
        while i < len(lines) and not re.search(r"-->", lines[i]):
            i += 1
        cue_lines: list[str] = []
        for line in lines[i:]:
            m = re.match(r"([\d:]+\.?\d*)\s+-->\s+([\d:]+\.?\d*)(.*)", line)
            if m:
                if cue_lines:
                    cues.append("\n".join(cue_lines))
                    cue_lines = []
                cue_lines.append(f"{_offset_vtt_ts(m.group(1), offset)} --> {_offset_vtt_ts(m.group(2), offset)}{m.group(3)}")
            else:
                cue_lines.append(line)
        if cue_lines:
            cues.append("\n".join(cue_lines))
    return "WEBVTT\n\n" + "\n\n".join(c.strip() for c in cues if c.strip())

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


# Predefined tone styles for batch script generation.
# Each value is appended as an extra rule to the system prompt.
_SCRIPT_STYLES: dict[str, str] = {
    "standard":     "",
    "professional": "Use a polished, professional tone suitable for corporate training.",
    "academic":     "Use a formal academic tone, as in a university lecture.",
    "casual":       "Use a friendly, approachable tone.",
}


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

    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "kisski"):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        if provider == "ollama":
            # Disable thinking mode (Qwen3 default) to keep output parseable
            self._extra_body: dict = {"think": False}
            self._batch_max_workers: int = 3
            self._batch_timeout: float = 180.0
            self._batch_size: int = 1  # small model: one block per call, no delimiter needed
        else:
            self._extra_body = {}
            self._batch_max_workers = 3
            self._batch_timeout = 180.0
            self._batch_size = 3

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
                extra_body=self._extra_body or None,
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
        is_first_batch: bool,
        is_last_batch: bool,
        glossary: dict[str, str] | None,
        style: str,
        add_greeting: bool,
        add_closing: bool,
        min_chars: int = 400,
        max_chars: int = 700,
    ) -> list[str]:
        batch_size = len(batch_texts)

        # Build input: raw content blocks separated by ===
        slides_input = "\n===\n".join(
            text.strip() if text.strip() else "[empty]"
            for text in batch_texts
        )

        # Build system prompt
        glossary_hint = ""
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            glossary_hint = f"Use the following terminology consistently in your output:\n{lines}\n\n"

        greeting_rule = (
            "- The first content block opens the presentation. Begin its script with a time-neutral greeting such as 'Welcome' or 'Hello everyone' – never use time-specific phrases like 'Good morning' or 'Good evening'.\n"
            if (is_first_batch and add_greeting) else
            "- Do not use any greeting or welcome phrase.\n"
        )
        closing_rule = (
            "- The last content block closes the presentation. End its script with a brief neutral closing such as 'Thank you for your attention' or 'Thanks for watching' – no time-specific phrases.\n"
            if (is_last_batch and add_closing) else
            "- Do not add any closing statement or thank-you.\n"
        )
        style_rule = f"- {_SCRIPT_STYLES[style]}\n" if _SCRIPT_STYLES.get(style) else ""

        system_prompt = glossary_hint + (
            "You are an expert at creating spoken narration scripts for presentations. "
            f"Generate a spoken script for EACH of the {batch_size} content blocks below. "
            "The blocks are separated by ===. "
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
            + greeting_rule
            + closing_rule
            + style_rule +
            f"- Keep each script between {min_chars} and {max_chars} characters.\n"
            "- For empty content blocks, output nothing (just write the ||| delimiter).\n"
            "\n"
            f"Separate the {batch_size} scripts using the delimiter ||| on its own line. "
            "No other text before, between, or after. Example output for 2 blocks:\n"
            "Researchers have found that regular breaks significantly reduce cognitive fatigue.\n"
            "|||\n"
            "Three core principles guide effective workplace ergonomics."
        )

        user_message = slides_input

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=batch_size * max(600, int(max_chars // 3)) + 200,
                timeout=self._batch_timeout,
                extra_body=self._extra_body or None,
            )
            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError(f"Batch {batch_index + 1}/{batch_count}: LLM returned empty response")

            # Parse separator-delimited output – truncation just means a shorter last script
            content_clean = content.strip()
            # LLMs sometimes prepend ||| before the first script – remove it
            if content_clean.startswith("|||"):
                content_clean = content_clean[3:].lstrip("\n ")
            parts = re.split(r"\|\|\|", content_clean)
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
        self,
        slide_texts: list[str],
        glossary: dict[str, str] | None = None,
        style: str = "standard",
        add_greeting: bool = True,
        add_closing: bool = True,
        min_chars: int = 400,
        max_chars: int = 700,
        batch_size: int | None = None,
        max_workers: int | None = None,
    ) -> list[str]:
        if batch_size is None:
            batch_size = self._batch_size
        if max_workers is None:
            max_workers = self._batch_max_workers
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

        def _run_batch_with_retry(texts: list[str], idx: int, n: int) -> tuple[int, list[str]]:
            is_first = idx == 0
            is_last = idx == batch_count - 1
            for attempt in range(2):
                try:
                    scripts = self._generate_scripts_single_batch(
                        texts, idx, batch_count, is_first, is_last,
                        glossary, style, add_greeting, add_closing, min_chars, max_chars,
                    )
                    return idx, scripts
                except RuntimeError as e:
                    if attempt == 0:
                        logger.warning("Batch {}/{} failed (attempt 1): {} – retrying in 5s", idx + 1, batch_count, e)
                        time.sleep(5)
                    else:
                        logger.warning(
                            "Batch {}/{} failed (attempt 2): {} – returning empty strings for {} slide(s)",
                            idx + 1, batch_count, e, n,
                        )
                        return idx, [""] * n
            return idx, [""] * n  # unreachable, but satisfies type checker

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_run_batch_with_retry, texts, idx, len(texts)): idx
                for idx, (_, texts) in enumerate(batches)
            }
            for future in as_completed(futures):
                try:
                    idx, scripts = future.result()
                    results[idx] = scripts
                    logger.info("Batch {}/{} completed", idx + 1, batch_count)
                except Exception as e:
                    idx = futures[future]
                    logger.warning("Batch {}/{} unexpected error: {}", idx + 1, batch_count, e)
                    results[idx] = [""] * batch_size

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

    def transcribe_chunked(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio, splitting files that exceed KISSKI's 600 s limit at silence points."""
        duration = _get_audio_duration(file_path)
        if duration > _MAX_AUDIO_SEC:
            raise RuntimeError(
                f"Audio zu lang ({duration / 60:.1f} min). Maximum: {_MAX_AUDIO_SEC // 60} Minuten."
            )
        if duration <= _CHUNK_MAX_SEC:
            return self.transcribe(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit – splitting into chunks", duration)
        silence_starts = _find_silence_starts(file_path)
        split_points = _compute_split_points(duration, silence_starts)
        logger.info("Split points: {}", split_points)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = _split_audio(file_path, split_points, tmpdir)
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
                return _merge_srt(ordered)
            if response_format == "vtt":
                return _merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

    def transcribe_and_translate_chunked(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe and translate audio, splitting files that exceed KISSKI's 600 s limit."""
        duration = _get_audio_duration(file_path)
        if duration > _MAX_AUDIO_SEC:
            raise RuntimeError(
                f"Audio zu lang ({duration / 60:.1f} min). Maximum: {_MAX_AUDIO_SEC // 60} Minuten."
            )
        if duration <= _CHUNK_MAX_SEC:
            return self.transcribe_and_translate(file_path, response_format=response_format)

        logger.info("Audio {:.1f}s exceeds limit – splitting into chunks (translate mode)", duration)
        silence_starts = _find_silence_starts(file_path)
        split_points = _compute_split_points(duration, silence_starts)

        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = _split_audio(file_path, split_points, tmpdir)
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
                return _merge_srt(ordered)
            if response_format == "vtt":
                return _merge_vtt(ordered)
            return " ".join(text for text, _ in ordered).strip()

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
