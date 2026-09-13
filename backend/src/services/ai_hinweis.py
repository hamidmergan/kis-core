"""Shared text and embedding helpers for the AI Act transparency notice.

Used by every tool that hands a generated file back to the user (audio,
video, image, or plain text). Each embed helper matches what the target
format can safely carry without breaking it — see
private/superpowers/specs/2026-09-13-ai-act-kennzeichnung-design.md for why
some formats (SRT, Markdown, LaTeX, DOCX, PPTX) are intentionally skipped.
"""

from PIL import PngImagePlugin

AI_HINWEIS_TEXT = "Diese Datei wurde mithilfe von KI erstellt. This file was created with AI assistance."


def ffmpeg_metadata_args() -> list[str]:
    """ffmpeg arguments that stamp the notice into the output file's metadata comment."""
    return ["-metadata", f"comment={AI_HINWEIS_TEXT}"]


def text_with_notice(text: str) -> str:
    """Plain text output with the notice as a leading line."""
    return f"{AI_HINWEIS_TEXT}\n\n{text}"


def vtt_with_notice(vtt_text: str) -> str:
    """A WebVTT file with the notice as a NOTE block right after the WEBVTT header.

    NOTE blocks are ignored by every player and by our own VTT text extractor
    (src/utils/text_extraction.py), so this never shows up as a caption.
    """
    return vtt_text.replace("WEBVTT\n\n", f"WEBVTT\n\nNOTE\n{AI_HINWEIS_TEXT}\n\n", 1)


def png_info_with_notice() -> PngImagePlugin.PngInfo:
    """A PNG text chunk carrying the notice, pass as `Image.save(..., pnginfo=...)`."""
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", AI_HINWEIS_TEXT)
    return info
