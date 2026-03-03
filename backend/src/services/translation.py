from pathlib import Path

from loguru import logger

from src.services.deepl_client import DeepLClient
from src.services.glossary import GlossaryService


def translate_output_filename(filename: str, output_ext: str | None = None, source_lang: str = "DE", target_lang: str = "EN-US") -> str:
    stem = Path(filename).stem
    ext = output_ext if output_ext is not None else Path(filename).suffix
    fallback = f"{stem}{ext}"
    if not stem.strip():
        return fallback
    try:
        from src.config import Settings
        api_key = Settings().deepl_api_key
        if not api_key:
            return fallback
        deepl = DeepLClient(api_key)
        readable = stem.replace("_", " ").replace("-", " ").strip()
        if not readable:
            return fallback
        translated = deepl.translate_text(readable, source_lang, target_lang)
        translated = translated.strip().replace(" ", "_")
        translated = "".join(c for c in translated if c.isalnum() or c in ("_", "-", "."))
        if not translated:
            return fallback
        return f"{translated}{ext}"
    except Exception as e:
        logger.warning("Filename translation failed for '{}': {}", filename, e)
        return fallback


class TranslationService:
    def __init__(self, deepl_client: DeepLClient, glossary: GlossaryService):
        self._deepl = deepl_client
        self._glossary = glossary

    @property
    def deepl_client(self) -> DeepLClient:
        return self._deepl

    @property
    def glossary(self) -> GlossaryService:
        return self._glossary

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text or not text.strip():
            return text
        prepared_text, replacements = self._glossary.apply_to_text(text)
        translated = self._deepl.translate_text(prepared_text, source_lang, target_lang)
        return self._glossary.restore_text(translated, replacements)

    def translate_batch(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        """Translate a list of strings in a single DeepL API call, with glossary support."""
        if not texts:
            return []
        prepared: list[str] = []
        replacements_list: list[dict] = []
        for text in texts:
            p, r = self._glossary.apply_to_text(text)
            prepared.append(p)
            replacements_list.append(r)
        translated = self._deepl.translate_batch(prepared, source_lang, target_lang)
        return [
            self._glossary.restore_text(t, r)
            for t, r in zip(translated, replacements_list)
        ]

    def translate_filename(self, filename: str, source_lang: str, target_lang: str) -> str:
        stem = Path(filename).stem
        ext = Path(filename).suffix
        if not stem.strip():
            return filename
        try:
            # Replace underscores/hyphens with spaces for better translation
            readable = stem.replace("_", " ").replace("-", " ")
            readable = readable.strip()
            if not readable:
                return filename
            translated = self.translate_text(readable, source_lang, target_lang)
            # Clean up: replace spaces with underscores, remove problematic chars
            translated = translated.strip()
            translated = translated.replace(" ", "_")
            # Remove characters that are problematic in filenames
            translated = "".join(
                c for c in translated if c.isalnum() or c in ("_", "-", ".")
            )
            if not translated:
                return filename
            return f"{translated}{ext}"
        except Exception as e:
            logger.warning("Filename translation failed for '{}': {}", filename, e)
            return filename
