"""Shared helpers that stamp the AI notice into generated files."""

import io

from PIL import Image

from src.services.ai_hinweis import (
    AI_HINWEIS_TEXT,
    ffmpeg_metadata_args,
    png_info_with_notice,
    vtt_with_notice,
)


def test_ffmpeg_metadata_args_carries_the_notice():
    assert ffmpeg_metadata_args() == ["-metadata", f"comment={AI_HINWEIS_TEXT}"]


def test_vtt_with_notice_inserts_a_single_line_note_after_the_header():
    vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"
    result = vtt_with_notice(vtt)
    assert result == f"WEBVTT\n\nNOTE {AI_HINWEIS_TEXT}\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"


def test_vtt_with_notice_tolerates_crlf_line_endings():
    vtt = "WEBVTT\r\n\r\n00:00:00.000 --> 00:00:01.000\r\nHallo\r\n"
    result = vtt_with_notice(vtt)
    assert f"NOTE {AI_HINWEIS_TEXT}" in result
    assert result.startswith("WEBVTT\r\n\r\nNOTE")


def test_vtt_with_notice_tolerates_extra_header_lines():
    vtt = "WEBVTT\nKind: captions\nLanguage: de\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"
    result = vtt_with_notice(vtt)
    assert result == f"WEBVTT\nKind: captions\nLanguage: de\n\nNOTE {AI_HINWEIS_TEXT}\n\n00:00:00.000 --> 00:00:01.000\nHallo\n"


def test_vtt_with_notice_leaves_non_vtt_text_unstamped(caplog):
    result = vtt_with_notice("not a vtt file")
    assert result == "not a vtt file"


def test_vtt_with_notice_leaves_headerless_vtt_unstamped():
    result = vtt_with_notice("WEBVTT")
    assert result == "WEBVTT"


def test_png_info_with_notice_round_trips_through_a_saved_image():
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, "PNG", pnginfo=png_info_with_notice())
    buf.seek(0)
    with Image.open(buf) as img:
        assert img.info.get("Comment") == AI_HINWEIS_TEXT
