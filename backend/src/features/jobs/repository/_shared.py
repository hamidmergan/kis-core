"""Shared imports and helpers for the jobs repository sub-modules."""
import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS
from src.core.db.pool import get_connection
from src.core.db._common import _notify_job_update, _de_date_to_utc

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")

__all__ = [
    "json", "datetime", "timedelta", "timezone",
    "psycopg2", "RealDictCursor",
    "MAX_RESULT_FILES", "JOB_RETENTION_HOURS",
    "get_connection", "_notify_job_update", "_de_date_to_utc",
]
