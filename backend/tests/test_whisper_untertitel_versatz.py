"""Subtitles of several parts: every part shifted by where it starts."""

from src.services.openai_compat_llm._subtitles import merge_srt, merge_vtt


def test_srt_teile_werden_verschoben_und_neu_gezaehlt():
    teil = "1\n00:00:01,500 --> 00:00:02,000\nHallo\n"
    assert merge_srt([(teil, 0.0), (teil, 3600.0)]) == (
        "1\n00:00:01,500 --> 00:00:02,000\nHallo\n\n"
        "2\n01:00:01,500 --> 01:00:02,000\nHallo\n"
    )


def test_vtt_teile_werden_verschoben():
    teil = "WEBVTT\n\n00:01.500 --> 00:02.000\nHallo\n"
    assert merge_vtt([(teil, 0.0), (teil, 60.5)]) == (
        "WEBVTT\n\n00:00:01.500 --> 00:00:02.000\nHallo\n\n00:01:02.000 --> 00:01:02.500\nHallo"
    )
