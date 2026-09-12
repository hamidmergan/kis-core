"""What both podcast tasks need."""

import os

import redis
from loguru import logger

_r = redis.from_url(os.environ.get("REDIS_URL", "redis://kis-redis:6379/0"))


class JobCancelled(Exception):
    """The person pressed cancel, this is not a fault."""


def assert_not_cancelled(job_uuid: str) -> None:
    try:
        if _r.exists(f"job:cancel:{job_uuid}"):
            raise JobCancelled()
    except redis.RedisError as e:
        logger.warning("Abbruchmarke nicht lesbar: {}", e)


def tts_client(provider_id: int):
    """The voice provider of this run, the same resolver the screencast uses."""
    from src.dependencies import get_tts_client_for_provider

    client = get_tts_client_for_provider(provider_id)
    if client is None:
        raise RuntimeError(f"TTS-Anbieter {provider_id} nicht gefunden oder abgeschaltet")
    if not client.is_available():
        raise RuntimeError(f"TTS-Anbieter {provider_id} nicht erreichbar")
    return client
