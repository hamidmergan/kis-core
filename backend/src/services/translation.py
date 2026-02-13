from pathlib import Path

from loguru import logger

from src.services.deepl_client import DeepLClient
from src.services.glossary import GlossaryService


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
