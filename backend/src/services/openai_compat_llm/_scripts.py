"""Screencast-Skript-Generierung (refine + Batch) via the configured LLM."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.tool_prompts import SCRIPT_REFINE_DEFAULT as _SCRIPT_REFINE_DEFAULT

from src.services.openai_compat_llm.base import load_prompt
from src.security.usage_log import log_llm_response as _verbrauch

# Wait before the second attempt of a batch.
_BATCH_RETRY_DELAY = 5.0


# Shortest result that can still be a statement.
_MIN_USABLE_SCRIPT_CHARS = 8


def is_blank_script(script: str) -> bool:
    """Empty, or too short to be a spoken statement."""
    letters = re.sub(r"[^\w\s]", "", script or "").strip()
    return len(letters) < _MIN_USABLE_SCRIPT_CHARS


class _ScriptCountMismatch(RuntimeError):
    """The batch came back with a different number of scripts than requested."""

    def __init__(self, expected: int, got: int):
        super().__init__(f"{got} Skripte statt {expected}")
        self.expected = expected
        self.got = got


# From how many own words on a slide is fit as a reference point.
_MIN_VERGLEICHSWOERTER = 6

# How much better another script must fit to count as an offset.
_VERSATZ_ABSTAND = 0.15


def _inhaltswoerter(text: str) -> set[str]:
    """Words from four letters on, without numbers and punctuation."""
    return {w for w in re.findall(r"[^\W\d_]{4,}", (text or "").lower())}


def _deckung(script: str, slide_text: str) -> float:
    """Share of the slide words that appear in the script."""
    folie = _inhaltswoerter(slide_text)
    return len(folie & _inhaltswoerter(script)) / len(folie) if folie else 0.0


def find_misaligned(scripts: list[str], slide_texts: list[str]) -> int | None:
    """Index of a slide whose content another script of the group tells."""
    if len(scripts) < 2:
        return None
    for j, text in enumerate(slide_texts):
        if len(_inhaltswoerter(text)) < _MIN_VERGLEICHSWOERTER:
            continue
        werte = [_deckung(s, text) for s in scripts]
        best = max(range(len(werte)), key=lambda k: werte[k])
        if best != j and werte[best] > werte[j] + _VERSATZ_ABSTAND:
            return j
    return None


class _ScriptMisaligned(RuntimeError):
    """The batch's scripts belong to different slides than requested."""

    def __init__(self, slide_index: int):
        super().__init__(f"Folie {slide_index + 1} der Gruppe erzählt ein fremdes Skript")
        self.slide_index = slide_index


def _glossary_hint(glossary: dict[str, str] | None) -> str:
    if not glossary:
        return ""
    lines = "\n".join(f"- {k} → {v}" for k, v in glossary.items())
    return f"Use the following terminology consistently in your output:\n{lines}\n\n"


def build_length_and_format_rules(
    batch_size: int,
    target_lang: str,
    greeting_rule: str,
    closing_rule: str,
    min_chars: int,
    max_chars: int,
) -> str:
    """System instruction for script generation, the length is a ceiling."""
    return (
        "You are an expert at creating spoken narration scripts for presentations. "
        f"Generate a spoken script for EACH of the {batch_size} content blocks below. "
        "The blocks are separated by ===. "
        f"The slide content may be in any language. Output MUST be in {target_lang}.\n"
        "Rules:\n"
        "- Do NOT add any new information.\n"
        "- Do NOT hallucinate.\n"
        "- Keep all facts, numbers, names, dates, and links exactly as they are.\n"
        "- Convert bullet points, tables, and lists into flowing text.\n"
        "- Remove citations, footnotes, and formatting artifacts.\n"
        "- NO semicolons, NO dashes - use only periods, commas, exclamation marks, and question marks.\n"
        "- Address the audience directly as 'you'.\n"
        "- Natural, conversational tone - like a university lecturer speaking.\n"
        + greeting_rule
        + closing_rule
        + f"- Never write more than {max_chars} characters for one script.\n"
        f"- The length follows the slide. A content-rich slide may approach {min_chars} characters. "
        "A slide with one line of content gets two or three sentences and nothing more.\n"
        "- NEVER repeat a sentence, a phrase, a name or a fact to reach a length. "
        "Repetition is always worse than a short script. Stop as soon as the slide is covered.\n"
        "- EVERY block that contains any text gets a script of at least one sentence. "
        "A block that looks similar to the previous one still gets its own script, "
        "phrased differently. Never leave such a block empty.\n"
        "- Only a block with NO text at all stays empty. Write nothing for it, "
        "not a placeholder word, not brackets, just the ||| delimiter.\n"
        "\n"
        f"Separate the {batch_size} scripts using the delimiter ||| on its own line. "
        "No other text before, between, or after. Example output for 2 blocks:\n"
        "Researchers have found that regular breaks significantly reduce cognitive fatigue.\n"
        "|||\n"
        "Three core principles guide effective workplace ergonomics."
    )


class _ScriptsMixin:
    """Expects client, model and the batch settings on the object."""

    def refine_script(
        self,
        user_prompt: str,
        current_script: str = "",
        slide_text: str = "",
        target_lang: str = "EN-US",
        selected_text: str | None = None,
        messages: list[dict] | None = None,
        glossary: dict[str, str] | None = None,
    ) -> str:
        """Rewrites the script of a single slide following an instruction."""
        current_script_content = current_script.strip() or slide_text.strip()
        is_followup = messages is not None and len(messages) > 1
        glossary_hint = _glossary_hint(glossary)
        if selected_text and selected_text.strip():
            instruction = user_prompt.strip() or "Improve this excerpt."
            if is_followup:
                system_prompt = (
                    glossary_hint +
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
                    glossary_hint +
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
            system_prompt = glossary_hint + load_prompt("prompt_script_refine", _SCRIPT_REFINE_DEFAULT).format(
                TARGET_LANG=target_lang,
                CURRENT_SCRIPT=current_script_content,
                USER_INSTRUCTION=user_prompt.strip(),
            )

        # Build message history: system + prior turns + final user message
        chat_messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if messages and len(messages) > 1:
            # All messages except the last (current) user message - already included via user_prompt in prompt
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
            _verbrauch("screencast", self, response)
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM returned empty response")
            return content.strip()
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"LLM API error: {e}") from e

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
        glossary_hint = _glossary_hint(glossary)

        greeting_rule = (
            "- The block marked [FIRST SLIDE] opens the presentation. Begin its script with a time-neutral greeting such as 'Welcome' or 'Hello everyone' (never time-specific like 'Good morning'). Apply all punctuation rules normally.\n"
            if (is_first_batch and add_greeting) else
            "- Do not use any greeting or welcome phrase.\n"
        )
        # Without a fixed suffix add_closing only means: a closing remark is allowed.
        closing_rule = (
            "" if (is_last_batch and add_closing) else
            "- Do not add any closing statement or thank-you.\n"
        )

        system_prompt = glossary_hint + build_length_and_format_rules(
            batch_size, target_lang, greeting_rule, closing_rule, min_chars, max_chars
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
            _verbrauch("screencast", self, response)
            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError(f"Batch {batch_index + 1}/{batch_count}: LLM returned empty response")

            # Parse separator-delimited output - truncation just means a shorter last script
            content_clean = content.strip()
            # LLMs sometimes prepend ||| before the first script - remove it
            if content_clean.startswith("|||"):
                content_clean = content_clean[3:].lstrip("\n ")
            parts = re.split(r"\|\|\|", content_clean)
            scripts = [p.strip() for p in parts]

            # A surplus separator at the end is harmless.
            while len(scripts) > batch_size and not scripts[-1]:
                scripts.pop()

            if len(scripts) != batch_size:
                raise _ScriptCountMismatch(batch_size, len(scripts))

            misaligned = find_misaligned(scripts, batch_texts)
            if misaligned is not None:
                raise _ScriptMisaligned(misaligned)

            return scripts

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"LLM API error (batch {batch_index + 1}): {e}") from e

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

        def _one_slide(text: str, idx: int, slide_no: int) -> str:
            """Generate a single slide, without separators nothing can slip."""
            try:
                return self._generate_scripts_single_batch(
                    [text], idx, batch_count, False, False,
                    glossary, False, False, min_chars, max_chars, target_lang, source_lang,
                )[0]
            except RuntimeError as e:
                logger.warning("Folie {} einzeln fehlgeschlagen: {}", slide_no, e)
                return ""

        def _fill_gaps(
            scripts: list[str], texts: list[str], idx: int, start: int, retry: bool = True
        ) -> list[str]:
            """Slide has text but the script does not: redo this one slide."""
            for i, (script, text) in enumerate(zip(scripts, texts)):
                if not is_blank_script(script):
                    continue
                slide_no = start + i + 1
                if not text.strip() or not retry:
                    # Really empty slide or already generated individually, just drop the placeholder.
                    scripts[i] = ""
                    continue
                logger.warning(
                    "Folie {}: kein brauchbares Skript ({!r}), einzeln nachholen",
                    slide_no, script[:40],
                )
                retry = _one_slide(text, idx, slide_no)
                if is_blank_script(retry):
                    logger.warning("Folie {}: auch einzeln kein Skript, bleibt stumm", slide_no)
                    scripts[i] = ""
                else:
                    scripts[i] = retry
            return scripts

        def _run_batch_with_retry(texts: list[str], idx: int, n: int) -> tuple[int, list[str]]:
            is_first = idx == 0
            is_last = idx == batch_count - 1
            start = batches[idx][0]
            for attempt in range(2):
                try:
                    scripts = self._generate_scripts_single_batch(
                        texts, idx, batch_count, is_first, is_last,
                        glossary, add_greeting, add_closing, min_chars, max_chars, target_lang, source_lang,
                    )
                    return idx, _fill_gaps(scripts, texts, idx, start)
                except _ScriptMisaligned as e:
                    # A second attempt does not fix this, so go individual right away.
                    logger.warning(
                        "Batch {}/{}: {} - erzeuge {} Folie(n) einzeln",
                        idx + 1, batch_count, e, n,
                    )
                    single = [_one_slide(t, idx, start + i + 1) for i, t in enumerate(texts)]
                    return idx, _fill_gaps(single, texts, idx, start, retry=False)
                except RuntimeError as e:
                    if attempt == 0:
                        logger.warning(
                            "Batch {}/{} failed (attempt 1): {} - retrying in {}s",
                            idx + 1, batch_count, e, _BATCH_RETRY_DELAY,
                        )
                        time.sleep(_BATCH_RETRY_DELAY)
                        continue
                    if isinstance(e, _ScriptCountMismatch):
                        # Auffuellen wuerde jede folgende Folie verschieben, also einzeln erzeugen.
                        logger.warning(
                            "Batch {}/{}: {} - erzeuge {} Folie(n) einzeln",
                            idx + 1, batch_count, e, n,
                        )
                        single = [_one_slide(t, idx, start + i + 1) for i, t in enumerate(texts)]
                        return idx, _fill_gaps(single, texts, idx, start, retry=False)
                    logger.warning(
                        "Batch {}/{} failed (attempt 2): {} - returning empty strings for {} slide(s)",
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
                    # Length of the actual batch, the last one is usually shorter.
                    results[idx] = [""] * len(batches[idx][1])

        # Reassemble in slide order
        ordered: list[str] = []
        for idx in range(batch_count):
            ordered.extend(results[idx])

        return ordered
