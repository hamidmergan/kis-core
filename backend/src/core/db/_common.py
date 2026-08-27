import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from src.core.db.pool import get_connection

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")


def _notify_job_update(job_uuid: str) -> None:
    """Publish to Redis so SSE clients receive a real-time update."""
    try:
        import redis as _redis
        r = _redis.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM jobs WHERE job_uuid = %s", (job_uuid,))
                row = cur.fetchone()
        if row:
            r.publish(f"jobs:{row[0]}", "update")
        r.close()
    except Exception as e:
        logger.warning("Redis job-update publish failed for {}: {}", job_uuid, e)


def _de_date_to_utc(date_str: str, end_of_day: bool = False) -> str:
    """Turns a German local date into a UTC timestamp for comparison."""
    year, month, day = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
    hour, minute, second = (23, 59, 59) if end_of_day else (0, 0, 0)
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=_TZ_BERLIN)
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

