"""Shared text and embedding helpers for the AI Act transparency notice.

Used by every tool that hands a generated file back to the user (audio,
video, image, or plain text). Each embed helper matches what the target
format can safely carry without breaking it — see
private/superpowers/specs/2026-09-13-ai-act-kennzeichnung-design.md for why
some formats (SRT, Markdown, LaTeX, DOCX, PPTX) are intentionally skipped.
"""

import re

from loguru import logger
from PIL import PngImagePlugin

AI_HINWEIS_TEXT = "Diese Datei wurde mithilfe von KI erstellt. This file was created with AI assistance."

_VTT_HEADER_SEPARATOR = re.compile(r"\r?\n\r?\n")


def ffmpeg_metadata_args() -> list[str]:
    """ffmpeg arguments that stamp the notice into the output file's metadata comment."""
    return ["-metadata", f"comment={AI_HINWEIS_TEXT}"]


def vtt_with_notice(vtt_text: str) -> str:
    """A WebVTT file with the notice as a single NOTE line right after the header.

    Tolerant of CRLF and extra header metadata lines between WEBVTT and the
    first cue, since real STT providers don't always match this project's
    own WEBVTT\\n\\n-prefixed generator. NOTE lines are ignored by every
    player and by our own VTT text extractor (src/utils/text_extraction.py),
    so this never shows up as a caption or leaks into re-extracted text.
    """
    if not vtt_text.startswith("WEBVTT"):
        logger.warning("vtt_with_notice: text does not start with WEBVTT, leaving unstamped")
        return vtt_text
    match = _VTT_HEADER_SEPARATOR.search(vtt_text)
    if not match:
        logger.warning("vtt_with_notice: no header/body separator found, leaving unstamped")
        return vtt_text
    end = match.end()
    return f"{vtt_text[:end]}NOTE {AI_HINWEIS_TEXT}\n\n{vtt_text[end:]}"


def png_info_with_notice() -> PngImagePlugin.PngInfo:
    """A PNG text chunk carrying the notice, pass as `Image.save(..., pnginfo=...)`."""
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", AI_HINWEIS_TEXT)
    return info
