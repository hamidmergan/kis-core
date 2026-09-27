"""Validates uploads by extension, size, page count and the actual leading bytes."""

import filetype
from loguru import logger

# Unused here, but eight routes take these limits from here.
from src.utils.pdfium_lock import PDFIUM_LOCK
from src.limits import (  # noqa: F401
    MAX_SCREENCAST_SLIDES,
    MAX_TRANSCRIPTION_BYTES,
    MAX_UPLOAD_BYTES,
    SCREENCAST_MAX_CHARS,
    TRANSLATE_MAX_CHARS,
    TRANSLATE_MAX_UPLOAD_BYTES,
    TTS_MAX_CHARS,
)


ALLOWED_EXTENSIONS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".tex": "application/x-tex",
    ".txt": "text/plain",
}

TTS_EXTENSIONS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".txt": "text/plain",
}


TRANSCRIPTION_EXTENSIONS = {
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "video/webm",
    ".mpeg": "video/mpeg",
    ".mpga": "audio/mpeg",
}


SCREENCAST_EXTENSIONS = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


SUMMARY_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


# --- Magic-byte content validation ------------------------------------------

# Text formats have no signature - we accept them after a UTF-8 decode probe.
_TEXT_EXTS = {".md", ".txt", ".tex", ".srt", ".vtt"}

# Which detected types match which extension, office formats also as zip.
_EXT_TO_DETECTED: dict[str, set[str]] = {
    ".pdf":  {"pdf"},
    ".docx": {"docx", "zip"},
    ".pptx": {"pptx", "zip"},
    ".mp3":  {"mp3"},
    ".mp4":  {"mp4"},
    ".m4a":  {"m4a", "mp4"},
    ".wav":  {"wav"},
    ".flac": {"flac"},
    ".ogg":  {"ogg"},
    ".oga":  {"ogg"},
    ".webm": {"webm"},
    ".mpeg": {"mpg"},
    ".mpga": {"mp3"},
    ".png":  {"png"},
    ".jpg":  {"jpg"},
    ".jpeg": {"jpg"},
}


class ContentTypeMismatch(ValueError):
    """Raised when the file's magic bytes do not match its extension."""


class TextNotUtf8(ValueError):
    """Raised when a text-typed file is not valid UTF-8."""


def validate_or_raise(content: bytes, ext: str, locale: str = "de") -> None:
    """Checks the content and raises 400 with a translated hint."""
    from fastapi import HTTPException  # local import - this module is also used outside HTTP context
    from src.i18n import t
    try:
        validate_content(content, ext)
    except TextNotUtf8:
        raise HTTPException(status_code=400, detail=t("file.textNotUtf8", locale))
    except ContentTypeMismatch:
        raise HTTPException(status_code=400, detail=t("file.contentMismatch", locale))


def count_pages(ext: str, path: str) -> int | None:
    """Page or slide count of a file on disk, None where the format has no pages."""
    try:
        if ext == ".pdf":
            import pypdfium2 as pdfium
            with PDFIUM_LOCK:
                doc = pdfium.PdfDocument(path)
                try:
                    return len(doc)
                finally:
                    doc.close()
        if ext == ".pptx":
            from pptx import Presentation
            return len(Presentation(path).slides)
    except Exception as e:  # noqa: BLE001 - an unreadable count must not fail the upload
        logger.warning("Seitenzahl von {} nicht lesbar: {}", ext, e)
    return None


def pages_or_raise(ext: str, path: str, locale: str = "de") -> int | None:
    """Rejects a document with more pages than the management allows, returns the page count."""
    from fastapi import HTTPException  # local import - this module is also used outside HTTP context
    from src.i18n import t
    from src.services.tool_limits import max_source_pages

    seiten = count_pages(ext, path)
    grenze = max_source_pages()
    if seiten is not None and seiten > grenze:
        raise HTTPException(
            status_code=413,
            detail=t("ai.source.tooManyPages", locale, pages=seiten, max=grenze),
        )
    return seiten


def sanitize_pasted_text(raw: str) -> str:
    """Normalize free-form pasted text for safe pipeline use."""
    cleaned = raw.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "".join(
        ch for ch in cleaned
        if ch in ("\t", "\n") or (ord(ch) >= 32 and ord(ch) != 127)
    )
    return cleaned.strip()


def validate_content(content: bytes, ext: str) -> None:
    """Checks via the leading bytes whether the content matches the extension."""
    ext_lower = ext.lower()

    if ext_lower in _TEXT_EXTS:
        # Plain text has no signature, so check the first 8 KiB as UTF-8.
        try:
            content[:8192].decode("utf-8")
        except UnicodeDecodeError as e:
            raise TextNotUtf8() from e
        return

    expected = _EXT_TO_DETECTED.get(ext_lower)
    if expected is None:
        return  # not in our whitelist - upstream check decides

    kind = filetype.guess(content)
    if kind is None or kind.extension not in expected:
        raise ContentTypeMismatch()
