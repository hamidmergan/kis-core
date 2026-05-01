"""Filename helpers for screencast artifacts: DeepL-translated stems + timestamp."""

from datetime import datetime
from pathlib import Path

from src.services.translation import translate_output_filename


def translate_stem(filename: str, source_lang: str = "DE", target_lang: str = "EN-US") -> str:
    """Translate the stem of a filename via DeepL. Returns the translated stem only (no extension)."""
    if not filename or not filename.strip():
        return "screencast"
    translated = translate_output_filename(
        filename, output_ext="", source_lang=source_lang, target_lang=target_lang
    )
    stem = Path(translated).stem if translated else Path(filename).stem
    return stem or "screencast"


def build_artifact_stem(translated_stem: str, when: datetime | None = None) -> str:
    """Append timestamp (YYYY-MM-DD_HHMM) to a stem for unique, sortable artifact names."""
    when = when or datetime.now()
    base = (translated_stem or "screencast").strip() or "screencast"
    return f"{base}_{when.strftime('%Y-%m-%d_%H%M')}"
