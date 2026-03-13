import deepl
from loguru import logger


class DeepLClient:
    def __init__(self, api_key: str):
        self._translator = deepl.Translator(api_key)

    @property
    def raw(self) -> deepl.Translator:
        """Direct access to the underlying deepl.Translator for Document API."""
        return self._translator

    @staticmethod
    def _normalize_source(lang: str) -> str | None:
        """DeepL source language must not have regional variant (EN-US → EN, PT-BR → PT). Return None for auto-detect."""
        if not lang:
            return None
        return lang.split("-")[0]

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        result = self._translator.translate_text(
            text, source_lang=self._normalize_source(source_lang), target_lang=target_lang
        )
        return result.text

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a list of strings in a single API call."""
        if not texts:
            return []
        normalized = self._normalize_source(source_lang)
        total_chars = sum(len(t) for t in texts)
        logger.info(
            "DeepL batch call: {} texts, {} chars total ({} → {})",
            len(texts), total_chars, normalized, target_lang,
        )
        results = self._translator.translate_text(
            texts, source_lang=normalized, target_lang=target_lang
        )
        return [r.text for r in results]
