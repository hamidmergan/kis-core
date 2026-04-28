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


def get_aia_glossary(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.definition, g.definition_en,
                          g.example_sentence, g.example_sentence_en, g.page_number,
                          MIN(c.start_time) AS start_time
                   FROM aia_glossary_entries g
                   LEFT JOIN aia_chunks c
                     ON c.source_id = g.source_id AND c.page_number = g.page_number
                   WHERE g.source_id = %s
                   GROUP BY g.id
                   ORDER BY g.term_de""",
                (source_id,),
            )
            return [dict(r) for r in cur.fetchall()]

def get_aia_glossary_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.definition, g.definition_en,
                          g.example_sentence, g.example_sentence_en, g.page_number,
                          s.filename,
                          MIN(c.start_time) AS start_time
                   FROM aia_glossary_entries g
                   JOIN aia_sources s ON s.id = g.source_id
                   LEFT JOIN aia_chunks c
                     ON c.source_id = g.source_id AND c.page_number = g.page_number
                   WHERE s.module_id = %s
                   GROUP BY g.id, s.filename
                   ORDER BY g.term_de""",
                (module_id,),
            )
            return [dict(r) for r in cur.fetchall()]

def bulk_create_glossary_entries(source_id: int, entries: list[dict]) -> list[dict]:
    if not entries:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            values = []
            params: list = []
            for e in entries:
                values.append("(%s, %s, %s, %s, %s, %s, %s, %s)")
                params.extend([
                    source_id,
                    e["term_de"],
                    e["term_en"],
                    e["definition"],
                    e.get("definition_en", ""),
                    e.get("example_sentence", ""),
                    e.get("example_sentence_en", ""),
                    e.get("page_number"),
                ])
            cur.execute(
                f"""INSERT INTO aia_glossary_entries
                    (source_id, term_de, term_en, definition, definition_en, example_sentence, example_sentence_en, page_number)
                    VALUES {', '.join(values)}
                    RETURNING id, term_de, term_en, definition, definition_en, example_sentence, example_sentence_en, page_number""",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return rows

def delete_aia_glossary(source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_glossary_entries WHERE source_id = %s", (source_id,))
        conn.commit()

def delete_all_glossary_entries(module_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM aia_glossary_entries
                   WHERE source_id IN (SELECT id FROM aia_sources WHERE module_id = %s)""",
                (module_id,),
            )
            count = cur.rowcount
        conn.commit()
    return count

def delete_glossary_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_glossary_entries WHERE id = %s RETURNING id", (entry_id,))
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted


# ─── Exercise Sets ────────────────────────────────────────────────────────────

