"""Reads a YouTube link into a video id and asks YouTube for the title, nothing else is fetched."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
from loguru import logger

from src.limits import WEB_PAGE_MAX_URL_CHARS, YOUTUBE_OEMBED_TIMEOUT_SECONDS
from src.services.web_page_fetch import USER_AGENT, LinkError

_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "www.youtube-nocookie.com", "youtu.be",
}
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_PREFIXES = ("shorts", "live", "embed")
_LEADING_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
OEMBED_URL = "https://www.youtube.com/oembed"


@dataclass(frozen=True)
class YoutubeVideo:
    video_id: str
    canonical_url: str


def canonical_url(video_id: str) -> str:
    """The one link form that gets stored, whatever the person pasted."""
    return f"https://www.youtube.com/watch?v={video_id}"


def parse_youtube_url(raw: str) -> YoutubeVideo:
    """Accepts the usual YouTube link forms and rejects everything else."""
    raw = (raw or "").strip()
    if not raw or len(raw) > WEB_PAGE_MAX_URL_CHARS:
        raise LinkError("ai.youtube.invalid", 400)
    if any(ch.isascii() and not ch.isprintable() for ch in raw):
        raise LinkError("ai.youtube.invalid", 400)
    # People paste links without the scheme, the browser adds it for them too.
    if not _LEADING_SCHEME.match(raw):
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        raise LinkError("ai.youtube.invalid", 400)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or host not in _HOSTS or parts.username or parts.password:
        raise LinkError("ai.youtube.invalid", 400)
    segments = [s for s in parts.path.split("/") if s]
    candidate = ""
    if host == "youtu.be":
        candidate = segments[0] if segments else ""
    elif len(segments) >= 2 and segments[0] in _PATH_PREFIXES:
        candidate = segments[1]
    elif segments == ["watch"]:
        candidate = parse_qs(parts.query).get("v", [""])[0]
    if not _VIDEO_ID.match(candidate):
        raise LinkError("ai.youtube.invalid", 400)
    return YoutubeVideo(video_id=candidate, canonical_url=canonical_url(candidate))


def is_youtube_url(raw: str) -> bool:
    """True when the link would be accepted as a YouTube video."""
    try:
        parse_youtube_url(raw)
    except LinkError:
        return False
    return True


def fallback_title(video_id: str) -> str:
    """The name when YouTube names none, the person can rename it."""
    return f"YouTube {video_id}"


def fetch_title(video_id: str, transport: httpx.BaseTransport | None = None) -> str:
    """Asks the public oEmbed endpoint for the title, a network failure yields the fallback."""
    params = {"url": canonical_url(video_id), "format": "json"}
    try:
        with httpx.Client(
            timeout=httpx.Timeout(YOUTUBE_OEMBED_TIMEOUT_SECONDS), follow_redirects=False,
            headers={"User-Agent": USER_AGENT}, transport=transport, trust_env=False,
        ) as client:
            response = client.get(OEMBED_URL, params=params)
    except httpx.HTTPError as e:
        logger.warning("YouTube oEmbed unreachable for {}: {}", video_id, e)
        return fallback_title(video_id)
    if response.status_code in (401, 403):
        raise LinkError("ai.youtube.notEmbeddable", 400)
    if response.status_code in (400, 404):
        raise LinkError("ai.youtube.notFound", 400)
    if response.status_code != 200:
        logger.warning("YouTube oEmbed answered {} for {}", response.status_code, video_id)
        return fallback_title(video_id)
    try:
        title = response.json().get("title")
    except ValueError:
        title = None
    return (str(title).strip() if title else "") or fallback_title(video_id)
