"""Remembers the Whisper result per part so a second attempt repeats nothing."""

import json
import os

import redis

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

_client: redis.Redis | None = None


def _r() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(_REDIS_URL, decode_responses=True)
    return _client


def _key(cache_key: str, chunk_index: int) -> str:
    return f"whisper:chunk:{cache_key}:{chunk_index}"


def _text_key(cache_key: str, chunk_index: int) -> str:
    # Its own namespace so text and segments are never confused.
    return f"whisper:chunktext:{cache_key}:{chunk_index}"


def get(cache_key: str, chunk_index: int) -> tuple[list[dict], str] | None:
    """Return cached ``(segments, language)`` for a chunk, or None if not cached."""
    try:
        raw = _r().get(_key(cache_key, chunk_index))
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data["segments"], data.get("language", "")
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def put(cache_key: str, chunk_index: int, segments: list[dict], language: str) -> None:
    """Store ``(segments, language)`` for a chunk. Best-effort: swallow Redis errors."""
    try:
        _r().setex(
            _key(cache_key, chunk_index),
            _TTL_SECONDS,
            json.dumps({"segments": segments, "language": language}),
        )
    except Exception:
        pass


def clear(cache_key: str, total_chunks: int) -> None:
    """Drop all chunk entries for a cache key. Called once a source is fully indexed."""
    try:
        client = _r()
        for i in range(total_chunks):
            client.delete(_key(cache_key, i))
    except Exception:
        pass


# The same for the tool that returns one text per part.

def get_text(cache_key: str, chunk_index: int) -> str | None:
    """The remembered text, or None, an empty text is a valid hit."""
    try:
        return _r().get(_text_key(cache_key, chunk_index))
    except Exception:
        return None


def put_text(cache_key: str, chunk_index: int, text: str) -> None:
    """Store a chunk's transcribed text. Best-effort: swallow Redis errors."""
    try:
        _r().setex(_text_key(cache_key, chunk_index), _TTL_SECONDS, text)
    except Exception:
        pass


def clear_text(cache_key: str, total_chunks: int) -> None:
    """Drop all text-chunk entries for a cache key. Called once a job fully succeeds."""
    try:
        client = _r()
        for i in range(total_chunks):
            client.delete(_text_key(cache_key, i))
    except Exception:
        pass
