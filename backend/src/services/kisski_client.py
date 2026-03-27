"""KISSKI LLM client – OpenAI-compatible wrapper for script generation and Whisper transcription."""

import json
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger
from langfuse.decorators import langfuse_context, observe
from langfuse.openai import OpenAI

# ── Audio chunking constants ───────────────────────────────────────────────────

_CHUNK_MAX_SEC = 540        # 9 min – safely under KISSKI's 600 s limit

def _seconds_to_srt_timestamp(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")


def _seconds_to_vtt_timestamp(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:06.3f}"


def _verbose_json_to_output(data: dict, response_format: str) -> str:
    if response_format == "srt":
        parts = []
        for i, seg in enumerate(data.get("segments", []), 1):
            start = _seconds_to_srt_timestamp(seg["start"])
            end = _seconds_to_srt_timestamp(seg["end"])
            parts.append(f"{i}\n{start} --> {end}\n{seg['text'].strip()}")
        return "\n\n".join(parts)
    if response_format == "vtt":
        parts = ["WEBVTT"]
        for seg in data.get("segments", []):
            start = _seconds_to_vtt_timestamp(seg["start"])
            end = _seconds_to_vtt_timestamp(seg["end"])
            parts.append(f"\n{start} --> {end}\n{seg['text'].strip()}")
        return "\n".join(parts)
    return data.get("text", "").strip()
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


from src.tool_prompts import SUMMARY_DEFAULT as _SUMMARY_DEFAULT, SCRIPT_REFINE_DEFAULT as _SCRIPT_REFINE_DEFAULT


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
        self._provider = provider
        self._base_url = base_url
        self._extra_body: dict = {}
        if provider == "ollama":
            self._batch_max_workers: int = 3
            self._batch_timeout: float = 180.0
            self._batch_size: int = 3
        else:
            self._batch_max_workers = 3
            self._batch_timeout = 180.0
            self._batch_size = 3

    def refine_script(
        self,
        user_prompt: str,
        current_script: str = "",
        slide_text: str = "",
        target_lang: str = "EN-US",
        selected_text: str | None = None,
        messages: list[dict] | None = None,
    ) -> str:
        """Refine or create a narration script for a single slide based on a user instruction.

        Uses the current script as the base if provided, otherwise falls back to slide_text.
        If selected_text is given, the instruction applies only to that excerpt.
        No length or format constraints — follows the user instruction freely.
        """
        current_script_content = current_script.strip() or slide_text.strip()
        is_followup = messages is not None and len(messages) > 1
        if selected_text and selected_text.strip():
            instruction = user_prompt.strip() or "Improve this excerpt."
            if is_followup:
                system_prompt = (
                    f"You are an expert editor of spoken narration scripts for presentations.\n"
                    f"The user is refining your previous response. Apply the new instruction to your last answer.\n"
                    f"Output ONLY the refined text. Do not repeat the instruction. Do not add labels or explanations. "
                    f"Write in flowing spoken language suitable for a university lecture. "
                    f"Never exceed 600 words. "
                    f"Output must be in {target_lang}, unless the task explicitly requests a translation to a different language.\n\n"
                    f"Original excerpt for context: «{selected_text.strip()}»"
                )
            else:
                system_prompt = (
                    f"You are an expert editor of spoken narration scripts for presentations.\n"
                    f"You will receive a selected excerpt from a script and a task to perform on it.\n"
                    f"Output ONLY the resulting text that should replace the excerpt. "
                    f"Do not repeat the instruction. Do not add labels or explanations. "
                    f"Write in flowing spoken language suitable for a university lecture. "
                    f"Never exceed 600 words. "
                    f"Output must be in {target_lang}, unless the task explicitly requests a translation to a different language.\n\n"
                    f"Selected excerpt: «{selected_text.strip()}»\n\n"
                    f"Task: {instruction}"
                )
        else:
            system_prompt = _load_prompt("prompt_script_refine", _SCRIPT_REFINE_DEFAULT).format(
                TARGET_LANG=target_lang,
                CURRENT_SCRIPT=current_script_content,
                USER_INSTRUCTION=user_prompt.strip(),
            )

        # Build message history: system + prior turns + final user message
        chat_messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if messages and len(messages) > 1:
            # All messages except the last (current) user message — already included via user_prompt in prompt
            for m in messages[:-1]:
                chat_messages.append({"role": m["role"], "content": m["content"]})
        chat_messages.append({"role": "user", "content": user_prompt.strip() or "Generate the script."})

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=chat_messages,
                temperature=0.4,
                max_tokens=800,
                extra_body=self._extra_body or None,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM returned empty response")
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
        add_greeting: bool,
        add_closing: bool,
        min_chars: int = 1500,
        max_chars: int = 2000,
        target_lang: str = "EN-US",
        source_lang: str = "DE",
    ) -> list[str]:
        batch_size = len(batch_texts)

        # Build input: raw content blocks separated by ===
        annotated: list[str] = []
        for j, text in enumerate(batch_texts):
            content = text.strip() if text.strip() else "[empty]"
            if is_first_batch and add_greeting and j == 0:
                content = "[FIRST SLIDE: open with a greeting]\n" + content
            annotated.append(content)
        slides_input = "\n===\n".join(annotated)

        # Build system prompt
        glossary_hint = ""
        if glossary:
            lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
            glossary_hint = f"Use the following terminology consistently in your output:\n{lines}\n\n"

        greeting_rule = (
            "- The block marked [FIRST SLIDE] opens the presentation. Begin its script with a time-neutral greeting such as 'Welcome' or 'Hello everyone' (never time-specific like 'Good morning'). Apply all punctuation rules normally.\n"
            if (is_first_batch and add_greeting) else
            "- Do not use any greeting or welcome phrase.\n"
        )
        closing_rule = (
            "" if (is_last_batch and add_closing) else
            "- Do not add any closing statement or thank-you.\n"
        )

        system_prompt = glossary_hint + (
            "You are an expert at creating spoken narration scripts for presentations. "
            f"Generate a spoken script for EACH of the {batch_size} content blocks below. "
            "The blocks are separated by ===. "
            f"The slide content is in {source_lang}. Output MUST be in {target_lang}.\n"
            "Rules:\n"
            "- Do NOT add any new information.\n"
            "- Do NOT hallucinate.\n"
            "- Keep all facts, numbers, names, dates, and links exactly as they are.\n"
            "- Convert bullet points, tables, and lists into flowing text.\n"
            "- Remove citations, footnotes, and formatting artifacts.\n"
            "- NO semicolons, NO dashes – use only periods, commas, exclamation marks, and question marks.\n"
            "- Address the audience directly as 'you'.\n"
            "- Natural, conversational tone – like a university lecturer speaking.\n"
            + greeting_rule
            + closing_rule
            + f"- Keep each script between {min_chars} and {max_chars} characters.\n"
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
                max_tokens=batch_size * max(800, int(max_chars // 2.5)) + 400,
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
        add_greeting: bool = True,
        add_closing: bool = True,
        min_chars: int = 1500,
        max_chars: int = 2000,
        target_lang: str = "EN-US",
        source_lang: str = "DE",
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
                        glossary, add_greeting, add_closing, min_chars, max_chars, target_lang, source_lang,
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

        # Ensure closing is appended to the last non-empty script
        if add_closing:
            _CLOSING_PHRASES = ("thank you", "thanks for", "thanks everyone", "that's all")
            for i in range(len(ordered) - 1, -1, -1):
                if ordered[i].strip():
                    if not any(p in ordered[i].lower() for p in _CLOSING_PHRASES):
                        ordered[i] = ordered[i].rstrip().rstrip(".") + ". Thank you for your attention."
                    break

        return ordered

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

        system_prompt = _load_prompt("prompt_summary", _SUMMARY_DEFAULT).replace(
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

    @observe(name="whisper-transcribe")
    def transcribe(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio in its original language using KISSKI Whisper."""
        langfuse_context.update_current_observation(
            metadata={"provider": self._provider, "base_url": self._base_url, "model": "whisper-large-v2"},
        )
        try:
            with open(file_path, "rb") as f:
                result = str(self._client.audio.transcriptions.create(
                    model="whisper-large-v2",
                    file=f,
                    response_format=response_format,
                ))
            if not result:
                raise RuntimeError("Whisper returned no output")
            return _clean_whisper_response(result)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"KISSKI Whisper API error: {e}") from e

    @observe(name="whisper-translate")
    def transcribe_and_translate(self, file_path: str, response_format: str = "text") -> str:
        """Transcribe audio and translate to English using KISSKI Whisper."""
        langfuse_context.update_current_observation(
            metadata={"provider": self._provider, "base_url": self._base_url, "model": "whisper-large-v2"},
        )
        try:
            with open(file_path, "rb") as f:
                response = self._client.audio.translations.create(
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
