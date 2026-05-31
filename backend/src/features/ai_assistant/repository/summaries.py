import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


def update_aia_source_summaries_status(uuid: str, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_sources SET summaries_status = %s WHERE uuid = %s",
                (status, uuid),
            )
        conn.commit()

def bulk_create_page_summaries(source_id: int, summaries: list[dict]) -> None:
    if not summaries:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            values = []
            params: list = []
            for s in summaries:
                values.append("(%s, %s, %s)")
                params.extend([source_id, s["page_number"], s["summary"]])
            # KNOWN ISSUE: plain INSERT with no unique constraint on
            # (source_id, page_number). Safe for the sequential resume path
            # (run_generate_summaries skips already-summarized pages), but two
            # concurrent summary runs on the same source could insert duplicate
            # page rows. Add a unique constraint + ON CONFLICT DO NOTHING before
            # making backfill pick up partially-summarized sources.
            cur.execute(
                f"""INSERT INTO aia_page_summaries (source_id, page_number, summary)
                    VALUES {', '.join(values)}""",
                params,
            )
        conn.commit()

def delete_page_summaries_by_source(source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_page_summaries WHERE source_id = %s",
                (source_id,),
            )
        conn.commit()

def get_page_summaries_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM aia_page_summaries
                   WHERE source_id = %s
                   ORDER BY page_number""",
                (source_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


# --- KI Tutor: Mindmaps ---

