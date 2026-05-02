"""Reachability-Checks für externe Services im Admin-Settings-Panel.

Nicht laufende Container erzeugen mehrsekündige DNS-Timeouts. Jeder Check wird
30s gecacht, damit Reloads der Admin-Seite innerhalb dieses Fensters instant sind.
"""

import asyncio
import time as _time_mod
from urllib.parse import urlparse

# In-Memory-Cache: {key: (expiry_monotonic, result)}
_REACH_CACHE: dict[str, tuple[float, bool]] = {}
_REACH_TTL = 30.0


def _cached_check(key: str, fn) -> bool:
    now = _time_mod.monotonic()
    hit = _REACH_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        result = bool(fn())
    except Exception:
        result = False
    _REACH_CACHE[key] = (now + _REACH_TTL, result)
    return result


async def dns_ok(url: str, timeout: float = 1.0) -> bool:
    """Hard-timeout DNS pre-check. Returns False quickly if host won't resolve
    (e.g. Docker container is down, causing gethostbyname to block for ~8s).
    """
    if not url:
        return False
    host = urlparse(url).hostname
    if not host:
        return False
    cache_key = f"dns:{host}"
    now = _time_mod.monotonic()
    hit = _REACH_CACHE.get(cache_key)
    if hit and hit[0] > now:
        return hit[1]
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(loop.getaddrinfo(host, None), timeout=timeout)
        ok = True
    except Exception:
        ok = False
    _REACH_CACHE[cache_key] = (now + _REACH_TTL, ok)
    return ok


def check_fish_speech_available(settings) -> bool:
    if not settings.fish_speech_base_url:
        return False

    def _do():
        from src.services.fish_speech_client import FishSpeechClient
        return FishSpeechClient(settings.fish_speech_base_url).is_available()

    return _cached_check(f"fish:{settings.fish_speech_base_url}", _do)


def check_kokoro_available(settings) -> bool:
    if not settings.kokoro_base_url:
        return False

    def _do():
        from src.services.kokoro_client import KokoroClient
        return KokoroClient(settings.kokoro_base_url).is_available()

    return _cached_check(f"kokoro:{settings.kokoro_base_url}", _do)


def check_mylab_available(settings) -> bool:
    if not settings.mylab_tts_base_url:
        return False

    def _do():
        from src.services.openai_compat_tts import OpenAICompatTTSClient
        return OpenAICompatTTSClient(settings.mylab_tts_base_url).is_available()

    return _cached_check(f"mylab_tts:{settings.mylab_tts_base_url}", _do)


def check_mylab_base_available(settings) -> bool:
    """Check whether the myLab platform is reachable (used for Whisper, Image, Embeddings, OCR)."""
    url = settings.fallback_provider_base_url or settings.mylab_tts_base_url
    if not url:
        return False

    def _do():
        import httpx
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{url.rstrip('/')}/v1/models")
        return resp.status_code < 500

    return _cached_check(f"mylab_base:{url}", _do)
