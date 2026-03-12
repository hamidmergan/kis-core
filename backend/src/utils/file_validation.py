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
}


VIDEO_DUBBING_VIDEO_EXTENSIONS = {
    ".mp4": "video/mp4",
}

VIDEO_DUBBING_AUDIO_EXTENSIONS = {
    ".mp3": "audio/mpeg",
}

SUBTITLE_EXTENSIONS = {
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}

SCREENCAST_EXTENSIONS = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


SUMMARY_EXTENSIONS = {
    ".mp3": "audio/mpeg",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
