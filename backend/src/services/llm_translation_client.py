"""LLM-based translation client - same interface as DeepLClient."""

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from openai import APIError, OpenAI, RateLimitError


_CHUNK_SIZE = 40
_BATCH_PARALLELISM = 4
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds, exponential: 2, 4, 8 plus jitter


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
    "- Do not introduce dashes or semicolons that are not present in the source text. Prefer periods, commas, colons, exclamation marks, and question marks.\n"
    "- Maintain consistent terminology throughout the text.\n"
    "- Do not add, remove, or reorder any content.\n"
    "{glossary}"
)

_BATCH_SYSTEM_PROMPT = (
    "You are a professional translator specializing in academic and university content.\n"
    "Translate each numbered item {instruction}.\n"
    "Rules:\n"
    "- Return ONLY the numbered list in the exact same format, nothing else.\n"
    "- No explanations, no notes, no preamble, no commentary.\n"
    "- Use formal register appropriate for academic and educational materials.\n"
    "- Preserve all formatting, line breaks, whitespace, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a well-established translation exists in the target language.\n"
    "- NEVER translate URLs, domains, email addresses, or code snippets. Leave them exactly as they are.\n"
    "- Do not introduce dashes or semicolons that are not present in the source text. Prefer periods, commas, colons, exclamation marks, and question marks.\n"
    "- Maintain consistent terminology throughout.\n"
    "- Do not add, remove, or reorder any content.\n"
    "{glossary}"
)


def _format_glossary(glossary: dict[str, str] | None) -> str:
    """Build a glossary instruction block for the system prompt."""
    if not glossary:
        return ""
    lines = "\n".join(f"  {src} → {tgt}" for src, tgt in glossary.items())
    return (
        "\nYou MUST use the following terminology exactly as specified:\n"
        f"{lines}\n"
    )


class LLMTranslationClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider: str = "openai_compat",
        glossary: dict[str, str] | None = None,
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider = provider
        self._glossary = glossary or {}

    def _extra_body(self) -> dict:
        return {}

    def _completion_with_retry(self, system: str, user: str) -> str:
        """Chat completion with exponential backoff on 429 / transient API errors."""
        last_exc: Exception | None = None
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.1,
                    max_tokens=4096,
                    extra_body=self._extra_body() or None,
                )
                return response.choices[0].message.content or ""
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

        system = _SYSTEM_PROMPT.format(
            instruction=instruction,
            glossary=_format_glossary(self._glossary),
        )
        return self._completion_with_retry(system, text)

    def _translate_chunk(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a single chunk in one API call. Falls back to per-item calls on parse mismatch."""
        if source_lang:
            instruction = f"from {source_lang} to {target_lang}"
        else:
            instruction = f"to {target_lang} (auto-detect source language)"

        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        system = _BATCH_SYSTEM_PROMPT.format(
            instruction=instruction,
            glossary=_format_glossary(self._glossary),
        )

        raw = self._completion_with_retry(system, numbered)

        parts = re.split(r"^\d+\.\s+", raw, flags=re.MULTILINE)
        results = [p.rstrip("\n") for p in parts if p]

        if len(results) == len(texts):
            return results

        logger.warning(
            "LLM chunk parse mismatch: expected {}, got {}. Falling back to per-item calls.",
            len(texts), len(results),
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

