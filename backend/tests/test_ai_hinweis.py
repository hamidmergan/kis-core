"""Shared helpers that stamp the AI notice into generated files."""

import io

from PIL import Image

from src.services.ai_hinweis import (
    AI_HINWEIS_TEXT,
    ffmpeg_metadata_args,
    png_info_with_notice,
    text_with_notice,
    vtt_with_notice,
)


def test_ffmpeg_metadata_args_carries_the_notice():
    assert ffmpeg_metadata_args() == ["-metadata", f"comment={AI_HINWEIS_TEXT}"]


def test_text_with_notice_prepends_a_leading_line():
    result = text_with_notice("Hallo Welt")
    assert result == f"{AI_HINWEIS_TEXT}\n\nHallo Welt"


def test_vtt_with_notice_inserts_a_note_block_after_the_header():
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"
    result = vtt_with_notice(vtt)
    assert result == f"WEBVTT\n\nNOTE\n{AI_HINWEIS_TEXT}\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"


def test_png_info_with_notice_round_trips_through_a_saved_image():
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, "PNG", pnginfo=png_info_with_notice())
    buf.seek(0)
    with Image.open(buf) as img:
        assert img.info.get("Comment") == AI_HINWEIS_TEXT
