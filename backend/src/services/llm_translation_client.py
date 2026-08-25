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

# Reasoning-Modelle verbrauchen den Großteil ihrer Ausgabe fürs Denken, bevor
# ein einziges Zeichen Übersetzung erscheint, und der Aufwand wächst mit der
# Zahl der Einträge, nicht mit deren Länge. Gemessen an qwen3.5-122b-a10b:
# 1 kurzer Satz kostet rund 1000 Token, 6 kurze Sätze kosten 6856.
#
# max_tokens ist eine Obergrenze, keine Reservierung. Großzügig ansetzen kostet
# nichts, zu knapp ansetzen dagegen viel: jeder Abriss löst eine Teilung und
# damit einen weiteren Aufruf von ungefähr 80 Sekunden aus.
_TOKENS_BASE = 4096
_TOKENS_PER_ITEM = 1500
_MAX_OUTPUT_TOKENS = 32768


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

    @staticmethod
    def _max_tokens_for(user: str, item_count: int = 1) -> int:
        """Token-Budget: Sockel plus Anteil je Eintrag plus Anteil für die Länge.

        Die feste 4096 von früher reichte weder für einen großen Block noch
        verlässlich für einen einzelnen Satz, sobald das Modell denkt. Ganz
        verhindern lässt sich ein Abriss nicht, dafür gibt es die Prüfung auf
        finish_reason.
        """
        budget = _TOKENS_BASE + _TOKENS_PER_ITEM * max(1, item_count) + len(user) // 2
        return min(_MAX_OUTPUT_TOKENS, budget)

    def _completion_with_retry(
        self, system: str, user: str, max_tokens: int | None = None, item_count: int = 1
    ) -> tuple[str, str]:
        """Chat completion with exponential backoff on 429 / transient API errors.

        Liefert (Inhalt, finish_reason). finish_reason == "length" heißt, die
        Antwort wurde an der Token-Grenze abgeschnitten und ist unvollständig.
        """
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

        system = _SYSTEM_PROMPT.format(
            instruction=instruction,
            glossary=_format_glossary(self._glossary),
        )
        translated, finish_reason = self._completion_with_retry(system, text)
        if finish_reason == "length":
            # Ein einzelner Text lässt sich nicht weiter teilen, also mehr
            # Platz geben. Bei Reasoning-Modellen liegt das fast immer am
            # Denkanteil, nicht an der Länge der Übersetzung.
            logger.warning(
                "Übersetzung abgeschnitten ({} Zeichen), zweiter Anlauf mit {} Token.",
                len(text), _MAX_OUTPUT_TOKENS,
            )
            translated, finish_reason = self._completion_with_retry(
                system, text, max_tokens=_MAX_OUTPUT_TOKENS
            )
        if finish_reason == "length":
            # Auch mit vollem Budget abgeschnitten. Lieber laut abbrechen als
            # eine halbe Übersetzung in die Datei schreiben.
            raise RuntimeError(
                f"Übersetzung wurde abgeschnitten ({len(text)} Zeichen Vorlage). "
                "Text ist zu lang für das eingestellte Modell."
            )
        return translated

    @staticmethod
    def _parse_numbered(raw: str, n: int) -> tuple[list[str | None], list[int]]:
        """Parse a ``1. ...\\n2. ...`` response into ``n`` slots keyed by item number.

        Keying by the explicit number (not split position) means a single dropped or
        duplicated line shifts nothing. Returns ``(results, missing)`` where ``results``
        holds ``None`` for any item the model omitted and ``missing`` lists those 0-based
        indices, so the caller can retranslate only those instead of the whole chunk.
        """
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
        """Translate a single chunk in one API call.

        On a parse mismatch we retranslate only the missing items individually rather
        than the whole chunk, so a single dropped line costs one extra call instead of
        exploding a 40-item chunk into 40 per-item calls. Only a fully unparseable response falls all the way back to per-item.
        """
        if source_lang:
            instruction = f"from {source_lang} to {target_lang}"
        else:
            instruction = f"to {target_lang} (auto-detect source language)"

        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        system = _BATCH_SYSTEM_PROMPT.format(
            instruction=instruction,
            glossary=_format_glossary(self._glossary),
        )

        raw, finish_reason = self._completion_with_retry(system, numbered, item_count=len(texts))

        if finish_reason == "length":
            # Der Block wurde an der Token-Grenze abgeschnitten. Die fehlenden
            # Einträge würde _parse_numbered finden, den angefangenen nicht:
            # der sieht aus wie ein fertiger Eintrag. Deshalb wird der ganze
            # Block halbiert und neu übersetzt, notfalls bis auf einen Eintrag.
            # Bei einem einzigen Eintrag hilft Teilen nicht mehr, dann versucht
            # es translate_text mit dem vollen Token-Budget.
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

        if len(missing) == len(texts):
            logger.warning(
                "LLM chunk unparseable ({} items), per-item fallback.", len(texts),
            )
            return self._translate_each(texts, source_lang, target_lang)

        logger.warning(
            "LLM chunk: {}/{} items missing, retranslating those individually.",
            len(missing), len(texts),
        )
        fixes = self._translate_each([texts[i] for i in missing], source_lang, target_lang)
        for idx, fixed in zip(missing, fixes):
            results[idx] = fixed
        return results  # type: ignore[return-value]

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

