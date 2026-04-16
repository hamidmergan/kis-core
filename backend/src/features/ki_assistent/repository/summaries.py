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


def update_kia_source_summaries_status(uuid: str, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE kia_sources SET summaries_status = %s WHERE uuid = %s",
                (status, uuid),
            )
        conn.commit()

def bulk_create_paragraph_summaries(source_id: int, summaries: list[dict]) -> None:
    if not summaries:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            values = []
            params: list = []
            for s in summaries:
                values.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                params.extend([
                    source_id,
                    s["page_number"],
                    s["block_index"],
                    s["bbox"]["x0"],
                    s["bbox"]["y0"],
                    s["bbox"]["x1"],
                    s["bbox"]["y1"],
                    s["content"],
                    s["summary"],
                ])
            cur.execute(
                f"""INSERT INTO kia_paragraph_summaries
                    (source_id, page_number, block_index, bbox_x0, bbox_y0, bbox_x1, bbox_y1, content, summary)
                    VALUES {', '.join(values)}""",
                params,
            )
        conn.commit()

def delete_paragraph_summaries_by_source(source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM kia_paragraph_summaries WHERE source_id = %s",
                (source_id,),
            )
        conn.commit()

def get_paragraph_summaries_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM kia_paragraph_summaries
                   WHERE source_id = %s
                   ORDER BY page_number, block_index""",
                (source_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


# --- KI Tutor: Mindmaps ---

