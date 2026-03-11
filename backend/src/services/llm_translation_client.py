"""LLM-based translation client — same interface as DeepLClient."""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger
from openai import OpenAI


_SYSTEM_PROMPT = (
    "You are a professional translator.\n"
    "Translate the given text from {source_lang} to {target_lang}.\n"
    "Rules:\n"
    "- Output ONLY the translated text, nothing else.\n"
    "- No explanations, no notes, no preamble.\n"
    "- Preserve all formatting, line breaks, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a standard translation exists."
)

_BATCH_SYSTEM_PROMPT = (
    "You are a professional translator.\n"
    "Translate each numbered item from {source_lang} to {target_lang}.\n"
    "Rules:\n"
    "- Return ONLY the numbered list in the same format, nothing else.\n"
    "- No explanations, no notes, no preamble.\n"
    "- Preserve all formatting, line breaks, and special characters exactly.\n"
    "- Preserve technical terms, proper nouns, and abbreviations unless a standard translation exists."
)


class LLMTranslationClient:
    def __init__(self, api_key: str, base_url: str, model: str, provider: str = "kisski"):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider = provider

    def _extra_body(self) -> dict:
        if self._provider == "ollama":
            return {"think": False}
        return {}

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        system = _SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=4096,
            extra_body=self._extra_body() or None,
        )
        return response.choices[0].message.content or ""

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        if not texts:
            return []

        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        system = _BATCH_SYSTEM_PROMPT.format(source_lang=source_lang, target_lang=target_lang)

        if self._provider == "ollama":
            # Small models don't reliably follow numbered list format — translate in parallel
            max_workers = min(len(texts), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.translate_text, t, source_lang, target_lang): i
                           for i, t in enumerate(texts)}
                results: list[str | None] = [None] * len(texts)
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
            return results  # type: ignore[return-value]

        logger.info(
            "LLM batch call: {} texts ({} → {})",
            len(texts), source_lang, target_lang,
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": numbered},
            ],
            temperature=0.1,
            max_tokens=4096,
            extra_body=self._extra_body() or None,
        )
        raw = response.choices[0].message.content or ""

        # Parse "N. text" lines
        parts = re.split(r"^\d+\.\s+", raw, flags=re.MULTILINE)
        # First split element is empty string before "1. "
        results = [p.rstrip("\n") for p in parts if p]

        if len(results) != len(texts):
            logger.warning(
                "LLM batch parse mismatch: expected {}, got {}. Falling back to individual calls.",
                len(texts), len(results),
            )
            max_workers = min(len(texts), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.translate_text, t, source_lang, target_lang): i
                           for i, t in enumerate(texts)}
                fallback: list[str | None] = [None] * len(texts)
                for future in as_completed(futures):
                    fallback[futures[future]] = future.result()
            return fallback  # type: ignore[return-value]

        return results
