"""Screencast-Skript-Generierung (refine + Batch) via the configured LLM."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.tool_prompts import SCRIPT_REFINE_DEFAULT as _SCRIPT_REFINE_DEFAULT

from src.services.openai_compat_llm.base import load_prompt


class _ScriptsMixin:
    """Erwartet: self._client (OpenAI), self._model, self._extra_body,
    self._batch_size, self._batch_max_workers, self._batch_timeout."""

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
        No length or format constraints - follows the user instruction freely.
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
            system_prompt = load_prompt("prompt_script_refine", _SCRIPT_REFINE_DEFAULT).format(
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
            "- NO semicolons, NO dashes - use only periods, commas, exclamation marks, and question marks.\n"
            "- Address the audience directly as 'you'.\n"
            "- Natural, conversational tone - like a university lecturer speaking.\n"
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

            # Parse separator-delimited output - truncation just means a shorter last script
            content_clean = content.strip()
            # LLMs sometimes prepend ||| before the first script - remove it
            if content_clean.startswith("|||"):
                content_clean = content_clean[3:].lstrip("\n ")
            parts = re.split(r"\|\|\|", content_clean)
            scripts = [p.strip() for p in parts]

            if len(scripts) != batch_size:
                logger.warning(
                    "Batch {}/{}: expected {} scripts, got {} - padding/trimming",
                    batch_index + 1, batch_count, batch_size, len(scripts),
                )
                scripts = (scripts + [""] * batch_size)[:batch_size]

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
                        logger.warning("Batch {}/{} failed (attempt 1): {} - retrying in 5s", idx + 1, batch_count, e)
                        time.sleep(5)
                    else:
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
