"""A .youtube source counts as media in both studio tasks, a .pdf source does not."""
from src.features.ai_assistant.tasks.studio.data_table import _is_media_source as data_table_is_media
from src.features.ai_assistant.tasks.studio.mindmap import _is_media_source as mindmap_is_media


def test_mindmap_youtube_ist_medium():
    assert mindmap_is_media("Vorlesung.youtube") is True


def test_mindmap_pdf_ist_kein_medium():
    assert mindmap_is_media("Skript.pdf") is False


def test_data_table_youtube_ist_medium():
    assert data_table_is_media("Vorlesung.youtube") is True


def test_data_table_pdf_ist_kein_medium():
    assert data_table_is_media("Skript.pdf") is False
