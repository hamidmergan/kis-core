"""File-upload validation helpers.

Beyond filename-suffix and Content-Length checks, we sniff the actual
magic bytes via the pure-python `filetype` lib to guard against renamed
binaries (`evil.exe` → `evil.pdf`). Pure-text formats have no signature,
so they fall back to a UTF-8 decode probe of the first 8 KiB.
"""

import filetype

from src.limits import (
    MAX_UPLOAD_BYTES,
    TRANSLATE_MAX_UPLOAD_BYTES,
    MAX_TRANSCRIPTION_BYTES,
    MAX_IMAGE_BYTES,
    MAX_OUTPUT_VIDEO_BYTES,
    TTS_MAX_CHARS,
    TRANSLATE_MAX_CHARS,
    SCRIPT_MAX_CHARS,
    SUMMARY_MAX_CHARS,
    SCREENCAST_MAX_CHARS,
    MAX_SCREENCAST_SLIDES,
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


SUBTITLE_EXTENSIONS = {
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}

SCREENCAST_EXTENSIONS = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


SUMMARY_EXTENSIONS = {
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

# Map of allowed extension -> set of detected `filetype` extensions that count
# as a match. Office formats are zip-based, so `zip` is accepted as a fallback
# alongside the specific OOXML signature.
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
    """Validate content and raise HTTP 400 with localized detail on mismatch.

    Wrapper for routes that already have a `locale` dependency injected -
    keeps the call-site to one line right after `await file.read()`.
    """
    from fastapi import HTTPException  # local import - this module is also used outside HTTP context
    from src.i18n import t
    try:
        validate_content(content, ext)
    except TextNotUtf8:
        raise HTTPException(status_code=400, detail=t("file.textNotUtf8", locale))
    except ContentTypeMismatch:
        raise HTTPException(status_code=400, detail=t("file.contentMismatch", locale))


def validate_content(content: bytes, ext: str) -> None:
    """Sniff magic bytes (or UTF-8) to verify content matches extension.

    Caller is responsible for size/extension whitelist checks first;
    this only handles the "is the body actually what it claims to be" step.
    Unknown extensions pass through silently - upstream whitelisting is the
    gate, this is a defense-in-depth check on top of it.
    """
    ext_lower = ext.lower()

    if ext_lower in _TEXT_EXTS:
        # No magic signature for plain text - probe the first 8 KiB as UTF-8.
        # Real text files decode cleanly; binaries fail almost immediately.
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
