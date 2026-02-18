ALLOWED_EXTENSIONS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".tex": "application/x-tex",
}

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB

TRANSCRIPTION_EXTENSIONS = {
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
}

MAX_TRANSCRIPTION_BYTES = 500 * 1024 * 1024  # 500 MB

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

MAX_SCREENCAST_SLIDES = 30
MAX_OUTPUT_VIDEO_BYTES = 500 * 1024 * 1024  # 500 MB
