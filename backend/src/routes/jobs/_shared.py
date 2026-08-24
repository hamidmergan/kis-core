"""Shared constants + Job-Row-Formatter für die /jobs-Endpunkte."""

import json as json_lib
import os

from src.i18n import DEFAULT_LOCALE, t
from src.storage import file_exists, load_result_meta


_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")


_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".tex": "application/x-tex",
    ".txt": "text/plain",
    ".html": "text/html",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}


_TOOL_KEYS = (
    "screencast_render",
    "screencast_translate",
    "tts",
    "translation",
    "transcription",
    "image_generate",
    "image_edit",
    "image_analyze",
    "summary",
)


def _tool_label(tool: str, locale: str) -> str:
    return t(f"tool.{tool}", locale)


_META_TOOLS = {"screencast_translate", "screencast_render"}


_TOOL_FILTER_GROUPS: dict[str, list[str]] = {
    "screencast": ["screencast_translate", "screencast_render"],
    "image": ["image_generate", "image_edit", "image_analyze"],
}


_SCREENCAST_TOOLS = {"screencast_translate", "screencast_render"}


def _tools_matching_query(q: str, locale: str = DEFAULT_LOCALE) -> list[str]:
    """Return tool keys whose label (in the user's locale) contains q (case-insensitive)."""
    q_lower = q.lower()
    return [k for k in _TOOL_KEYS if q_lower in _tool_label(k, locale).lower()]


def _expand_tool_filter(tool_filter: str) -> list[str] | None:
    if not tool_filter:
        return None
    return _TOOL_FILTER_GROUPS.get(tool_filter, [tool_filter])


def _dt(val) -> str | None:
    """Convert datetime or string to ISO string, or return None."""
    if val is None:
        return None
    return (val.isoformat() + "Z") if hasattr(val, "isoformat") else val


def _format_job_rows(
    jobs: list[dict], locale: str = DEFAULT_LOCALE, is_admin: bool = False
) -> list[dict]:
    """Format raw DB job rows into the standard API response format."""
    result = []
    for job in jobs:
        has_download = (
            job["status"] == "success"
            and bool(job["result_path"])
            and file_exists(job["result_path"])
        )
        created_at_raw = job["created_at"]
        created_at = created_at_raw.isoformat() if hasattr(created_at_raw, "isoformat") else (created_at_raw or "")
        date_part = created_at[:10]
        time_part = created_at[11:19].replace(":", "-") if len(created_at) >= 19 else ""
        folder_name = f"{date_part}_{time_part}_{job['job_uuid']}" if date_part and time_part else job["job_uuid"]

        tts_params: dict = {}
        is_generating_scripts = False
        tool = job["tool"]
        if tool in ("tts", "screencast_render", "screencast_translate"):
            try:
                progress = json_lib.loads(job["progress"] or "{}")
                if tool == "tts":
                    tts_params = progress.get("tts_params", {})
                else:
                    tts_params = {k: progress[k] for k in ("voice_id", "voice_label", "provider") if k in progress}
                if tool == "screencast_translate":
                    is_generating_scripts = bool(progress.get("generating_scripts"))
            except Exception:
                pass

        meta = None
        if job["status"] in ("success", "failed") and tool in _META_TOOLS:
            meta = load_result_meta(job["user_id"], job["job_uuid"])
            # Die Zahlen zum Lauf sind eine Betriebsauskunft und gehen nur an Admins.
            if meta and not is_admin:
                meta = {k: v for k, v in meta.items() if k != "stats"}

        result.append({
            "job_uuid": job["job_uuid"],
            "tool": tool,
            "tool_label": _tool_label(tool, locale),
            "original_filename": job["original_filename"],
            "status": job["status"],
            "error": job["error_message"],
            "created_at": _dt(job["created_at"]),
            "started_at": _dt(job["started_at"]),
            "completed_at": _dt(job["completed_at"]),
            "render_started_at": _dt(job["render_started_at"]),
            "render_queued_at": _dt(job["render_queued_at"]),
            "expires_at": _dt(job["expires_at"]),
            "has_download": has_download,
            "result_filename": job["result_filename"],
            "folder_name": folder_name,
            "tts_params": tts_params or None,
            "is_generating_scripts": is_generating_scripts,
            "meta": meta,
        })
    return result
