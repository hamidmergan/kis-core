"""LLM-based translation client - same interface as DeepLClient."""

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from openai import APIError, OpenAI, RateLimitError
from src.security.usage_log import log_llm_response as _verbrauch


_CHUNK_SIZE = 20
_BATCH_PARALLELISM = 4
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds, exponential: 2, 4, 8 plus jitter

# Below this a cut-off text is not split any further, the model is then the problem.
_MIN_SPLIT_CHARS = 500
# Where a long text may be cut, and how much of the mark stays on the left side.
_SPLIT_MARKS = (("\n\n", 0), ("\n", 0), (". ", 1), (" ", 0))

# Thinking models need room per entry, being generous costs nothing.
_TOKENS_BASE = 4096
_TOKENS_PER_ITEM = 1500
_MAX_OUTPUT_TOKENS = 32768


def _split_in_half(text: str) -> tuple[str, str, str] | None:
    """Cuts at the mark closest to the middle, None when the text is too short to cut."""
    if len(text) < _MIN_SPLIT_CHARS:
        return None
    mitte = len(text) // 2
    for mark, bleibt_links in _SPLIT_MARKS:
        stellen = [i for i in (text.rfind(mark, 0, mitte), text.find(mark, mitte)) if i > 0]
        if not stellen:
            continue
        i = min(stellen, key=lambda x: abs(x - mitte))
        return text[:i + bleibt_links], mark[bleibt_links:], text[i + len(mark):]
    return None


_SYSTEM_PROMPT = (
    "You are a professional translator specializing in academic and university content.\n"
    "Translate the given text {instruction}.\n"
    "Rules:\n"
    "- Output ONLY the translated text, nothing else.\n"
    "- No explanations, no notes, no preamble, no commentary.\n"
    "- Use formal register appropriate for academic and educational materials.\n"
    "- Preserve all formatting, line breaks, whitespace, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a well-established translation exists in the target language.\n"
    "- NEVER translate URLs, domains, email addresses, or code snippets. Leave them exactly as they are.\n"
    "- If the text contains a token matching __GLOSSARY_<number>__, copy it into your output EXACTLY as it appears, character for character. Never translate, alter, or remove such a token.\n"
    "- Do not introduce dashes or semicolons that are not present in the source text. Prefer periods, commas, colons, exclamation marks, and question marks.\n"
    "- Maintain consistent terminology throughout the text.\n"
    "- Do not add, remove, or reorder any content.\n"
)

_BATCH_SYSTEM_PROMPT = (
    "You are a professional translator specializing in academic and university content.\n"
    "Translate each numbered item {instruction}.\n"
    "Rules:\n"
    "- Return ONLY the numbered list in the exact same format, nothing else.\n"
    "- Return exactly one numbered item per input item, in the same order. Never merge two items into one and never split one item into two, even when that reads better.\n"
    "- No explanations, no notes, no preamble, no commentary.\n"
    "- Use formal register appropriate for academic and educational materials.\n"
    "- Preserve all formatting, line breaks, whitespace, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a well-established translation exists in the target language.\n"
    "- NEVER translate URLs, domains, email addresses, or code snippets. Leave them exactly as they are.\n"
    "- If an item contains a token matching __GLOSSARY_<number>__, copy it into your output EXACTLY as it appears, character for character. Never translate, alter, or remove such a token.\n"
    "- Do not introduce dashes or semicolons that are not present in the source text. Prefer periods, commas, colons, exclamation marks, and question marks.\n"
    "- Maintain consistent terminology throughout.\n"
    "- Do not add, remove, or reorder any content.\n"
)


class LLMTranslationClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider: str = "openai_compat",
        sampling: dict | None = None,
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider = provider
        # Abtastwerte aus dem Admin, leer heisst der eingebaute Wert gilt.
        self._sampling = dict(sampling or {})

    def sampling(self, standard: float) -> dict:
        """Die Admin-Werte wenn gesetzt, sonst die eingebaute Temperatur."""
        werte = getattr(self, "_sampling", None)
        return dict(werte) if werte else {"temperature": standard}

    def _extra_body(self) -> dict:
        return {}

    @staticmethod
    def _max_tokens_for(user: str, item_count: int = 1) -> int:
        """Token budget from a base, the entry count and the length."""
        budget = _TOKENS_BASE + _TOKENS_PER_ITEM * max(1, item_count) + len(user) // 2
        return min(_MAX_OUTPUT_TOKENS, budget)

    def _completion_with_retry(
        self, system: str, user: str, max_tokens: int | None = None, item_count: int = 1
    ) -> tuple[str, str]:
        """One call with growing waits, returns content and finish reason."""
        last_exc: Exception | None = None
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    **self.sampling(0.1),
                    max_tokens=max_tokens or self._max_tokens_for(user, item_count),
                    extra_body=self._extra_body() or None,
                )
                _verbrauch("translation", self, response)
                choice = response.choices[0]
                return choice.message.content or "", getattr(choice, "finish_reason", "stop") or "stop"
            except RateLimitError as e:
                last_exc = e
                if attempt == _RETRY_ATTEMPTS - 1:
                    break
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("LLM 429 rate limit, retry {}/{} in {:.1f}s", attempt + 1, _RETRY_ATTEMPTS, delay)
                time.sleep(delay)
            except APIError as e:
                # 5xx and other transient API errors
                last_exc = e
                status = getattr(e, "status_code", None)
                if status is None or status < 500:
                    raise
                if attempt == _RETRY_ATTEMPTS - 1:
                    break
                delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("LLM {} error, retry {}/{} in {:.1f}s", status, attempt + 1, _RETRY_ATTEMPTS, delay)
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        if source_lang:
            instruction = f"from {source_lang} to {target_lang}"
        else:
            instruction = f"to {target_lang} (auto-detect source language)"

        system = _SYSTEM_PROMPT.format(instruction=instruction)
        translated, finish_reason = self._completion_with_retry(system, text)
        if finish_reason == "length":
            # A single text cannot be split, so give it more room.
            logger.warning(
                "Übersetzung abgeschnitten ({} Zeichen), zweiter Anlauf mit {} Token.",
                len(text), _MAX_OUTPUT_TOKENS,
            )
            translated, finish_reason = self._completion_with_retry(
                system, text, max_tokens=_MAX_OUTPUT_TOKENS
            )
        if finish_reason == "length":
            # Still cut off with the full budget, so halve the text and translate both parts.
            haelften = _split_in_half(text)
            if haelften is None:
                raise RuntimeError(
                    f"Übersetzung wurde abgeschnitten ({len(text)} Zeichen Vorlage). "
                    "Text ist zu lang für das eingestellte Modell."
                )
            links, trenner, rechts = haelften
            logger.warning(
                "Übersetzung abgeschnitten ({} Zeichen), teile in {} und {}.",
                len(text), len(links), len(rechts),
            )
            return (
                self.translate_text(links, source_lang, target_lang)
                + trenner
                + self.translate_text(rechts, source_lang, target_lang)
            )
        return translated

    @staticmethod
    def _parse_numbered(raw: str, n: int) -> tuple[list[str | None], list[int]]:
        """Reads the numbered answer, missing entries are reported."""
        parsed: dict[int, str] = {}
        for m in re.finditer(
            r"^\s*(\d+)\.\s*(.*?)(?=\n\s*\d+\.\s|\Z)", raw, flags=re.MULTILINE | re.DOTALL
        ):
            num = int(m.group(1))
            text = m.group(2).strip()
            if 1 <= num <= n and text:
                parsed.setdefault(num, text)
        results: list[str | None] = [parsed.get(i + 1) for i in range(n)]
        missing = [i for i, r in enumerate(results) if r is None]
        return results, missing

    def _translate_chunk(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translates a batch in one call, missing parts are fetched individually."""
        if source_lang:
            instruction = f"from {source_lang} to {target_lang}"
        else:
            instruction = f"to {target_lang} (auto-detect source language)"

        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        system = _BATCH_SYSTEM_PROMPT.format(instruction=instruction)

        raw, finish_reason = self._completion_with_retry(system, numbered, item_count=len(texts))

        if finish_reason == "length":
            # Cut off at the token limit, so halve the block and translate again.
            if len(texts) == 1:
                return [self.translate_text(texts[0], source_lang, target_lang)]
            half = len(texts) // 2
            logger.warning(
                "LLM chunk abgeschnitten ({} Einträge), teile in {} und {}.",
                len(texts), half, len(texts) - half,
            )
            return (
                self._translate_chunk(texts[:half], source_lang, target_lang)
                + self._translate_chunk(texts[half:], source_lang, target_lang)
            )

        results, missing = self._parse_numbered(raw, len(texts))

        if not missing:
            return results  # type: ignore[return-value]

        # A short list means the model renumbered its own paragraphs, so no number can be trusted.
        logger.warning(
            "LLM chunk: {}/{} items missing, whole chunk per-item.", len(missing), len(texts),
        )
        return self._translate_each(texts, source_lang, target_lang)

    def _translate_each(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate each text with an individual API call, in parallel."""
        max_workers = min(len(texts), _BATCH_PARALLELISM)
        results: list[str | None] = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.translate_text, t, source_lang, target_lang): i
                       for i, t in enumerate(texts)}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        return results  # type: ignore[return-value]

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        if not texts:
            return []

        if self._provider == "local":
            # Small local models don't reliably follow numbered list format - go straight to per-item.
            logger.info(
                "LLM per-item (local): {} texts ({} → {})",
                len(texts), source_lang, target_lang,
            )
            return self._translate_each(texts, source_lang, target_lang)

        chunks = [texts[i:i + _CHUNK_SIZE] for i in range(0, len(texts), _CHUNK_SIZE)]
        logger.info(
            "LLM batch: {} texts in {} chunk(s) of up to {}, {} parallel ({} → {})",
            len(texts), len(chunks), _CHUNK_SIZE, _BATCH_PARALLELISM, source_lang, target_lang,
        )

        chunk_results: list[list[str] | None] = [None] * len(chunks)
        max_workers = min(len(chunks), _BATCH_PARALLELISM)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._translate_chunk, c, source_lang, target_lang): i
                for i, c in enumerate(chunks)
            }
            for future in as_completed(futures):
                chunk_results[futures[future]] = future.result()

        return [t for chunk in chunk_results for t in chunk]  # type: ignore[union-attr]

