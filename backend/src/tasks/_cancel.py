"""The cancel mark of a job in Redis, read by every task that can be stopped."""

import redis
from loguru import logger

from src.core.redis_url import REDIS_URL

_r = redis.from_url(REDIS_URL)


def cancel_key(job_uuid: str) -> str:
    return f"job:cancel:{job_uuid}"


def mark_is_set(job_uuid: str) -> bool:
    """Whether the mark exists, a Redis failure is raised."""
    return bool(_r.exists(cancel_key(job_uuid)))


def is_cancelled(job_uuid: str) -> bool:
    """Whether the person pressed cancel, an unreadable mark counts as not cancelled."""
    try:
        return mark_is_set(job_uuid)
    except redis.RedisError as e:
        logger.warning("Abbruchmarke nicht lesbar: {}", e)
        return False


def clear_cancel(job_uuid: str) -> None:
    """A new run starts clean, the mark of the cancelled one lives 10 minutes otherwise."""
    try:
        _r.delete(cancel_key(job_uuid))
    except redis.RedisError as e:
        logger.warning("Abbruchmarke nicht loeschbar: {}", e)
