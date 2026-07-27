"""Filename helpers for screencast artifacts: translated stems + timestamp."""

from datetime import datetime
from pathlib import Path

from loguru import logger

from src.services.translation import translate_output_filename


def translate_stem(
    filename: str,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
    service=None,
) -> str:
    """Übersetzt den Namensstamm einer Datei. Ohne Endung.

    ``service`` ist der Übersetzer, den der Nutzer für diesen Job gewählt hat.
    Ohne ihn ging der Aufruf immer direkt an DeepL, auch wenn der Job über ein
    Sprachmodell übersetzt wurde. Ohne DeepL-Schlüssel blieb der Dateiname dann
    unübersetzt, während der Inhalt übersetzt war.
    """
    if not filename or not filename.strip():
        return "screencast"

    if service is not None:
        try:
            translated = service.translate_filename(filename, source_lang, target_lang)
            stem = Path(translated).stem
            if stem:
                return stem
        except Exception as e:
            logger.warning("Dateiname über den gewählten Anbieter fehlgeschlagen: {}", e)

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
