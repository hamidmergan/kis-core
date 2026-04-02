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
    except Exception:
        pass

_TZ_BERLIN = ZoneInfo("Europe/Berlin")

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS  # noqa: E402

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _de_date_to_utc(date_str: str, end_of_day: bool = False) -> str:
    """Convert a YYYY-MM-DD German local date to a UTC datetime string for DB comparison.

    DB timestamps are stored in UTC. The user picks a date in German local time,
    so 'date_to=2026-02-26' means up to 2026-02-26 23:59:59 Europe/Berlin,
    which is 2026-02-26 22:59:59 UTC in winter (UTC+1).
    """
    year, month, day = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
    hour, minute, second = (23, 59, 59) if end_of_day else (0, 0, 0)
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=_TZ_BERLIN)
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, dsn)
    return _pool


@contextmanager
def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    ldap_username TEXT NOT NULL UNIQUE,
                    display_name  TEXT NOT NULL,
                    email         TEXT,
                    active        INTEGER NOT NULL DEFAULT 1,
                    role          TEXT NOT NULL DEFAULT 'lecturer',
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'lecturer'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    id         SERIAL PRIMARY KEY,
                    email      TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id                  SERIAL PRIMARY KEY,
                    job_uuid            TEXT NOT NULL UNIQUE,
                    user_id             INTEGER NOT NULL DEFAULT 0,
                    tool                TEXT NOT NULL,
                    original_filename   TEXT NOT NULL DEFAULT '',
                    input_path          TEXT,
                    result_path         TEXT,
                    result_filename     TEXT,
                    status              TEXT NOT NULL DEFAULT 'pending',
                    error_message       TEXT,
                    progress            TEXT,
                    celery_task_id      TEXT,
                    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
                    started_at          TIMESTAMP,
                    completed_at        TIMESTAMP,
                    expires_at          TIMESTAMP,
                    progress_updated_at TIMESTAMP,
                    render_started_at   TIMESTAMP,
                    render_queued_at    TIMESTAMP
                )
            """)
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS render_queued_at TIMESTAMP")
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT 'unknown'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id         SERIAL PRIMARY KEY,
                    key        TEXT NOT NULL UNIQUE,
                    value      TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quotas (
                    id                SERIAL PRIMARY KEY,
                    user_id           INTEGER NOT NULL,
                    quota_type        TEXT NOT NULL,
                    used              INTEGER NOT NULL DEFAULT 0,
                    window_started_at TIMESTAMP,
                    reset_at          TIMESTAMP,
                    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, quota_type)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quota_overrides (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    quota_type  TEXT NOT NULL,
                    limit_value INTEGER NOT NULL,
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, quota_type)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quota_resets (
                    user_id  INTEGER PRIMARY KEY,
                    reset_at TIMESTAMP NOT NULL
                )
            """)
            if admin_email and admin_email.strip():
                cur.execute(
                    "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                    (admin_email.strip().lower(),),
                )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_modules (
                    id                   SERIAL PRIMARY KEY,
                    uuid                 TEXT NOT NULL UNIQUE,
                    user_id              INTEGER NOT NULL,
                    title                TEXT NOT NULL,
                    description          TEXT,
                    is_active            BOOLEAN NOT NULL DEFAULT FALSE,
                    status               TEXT NOT NULL DEFAULT 'pending',
                    enroll_code          TEXT UNIQUE,
                    enroll_code_expires  TIMESTAMP,
                    embedding_model      TEXT NOT NULL DEFAULT '',
                    embedding_fingerprint TEXT,
                    created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_access_links (
                    id         SERIAL PRIMARY KEY,
                    module_id  INTEGER NOT NULL
                                 REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    code       TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_enrollments (
                    id             SERIAL PRIMARY KEY,
                    module_id      INTEGER NOT NULL
                                     REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id        INTEGER NOT NULL,
                    link_id        INTEGER REFERENCES ki_tutor_access_links(id) ON DELETE SET NULL,
                    enrolled_until TIMESTAMP,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (module_id, user_id, link_id)
                )
            """)
            # Migration: add link_id column if table already existed without it
            cur.execute("ALTER TABLE ki_tutor_enrollments ADD COLUMN IF NOT EXISTS link_id INTEGER REFERENCES ki_tutor_access_links(id) ON DELETE SET NULL")
            # Migration: drop old unique constraint and add new one with link_id
            cur.execute("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ki_tutor_enrollments_module_id_user_id_key'
                    ) THEN
                        ALTER TABLE ki_tutor_enrollments
                            DROP CONSTRAINT ki_tutor_enrollments_module_id_user_id_key;
                    END IF;
                END $$
            """)
            cur.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ki_tutor_enrollments_module_id_user_id_link_id_key'
                    ) THEN
                        ALTER TABLE ki_tutor_enrollments
                            ADD CONSTRAINT ki_tutor_enrollments_module_id_user_id_link_id_key
                            UNIQUE (module_id, user_id, link_id);
                    END IF;
                END $$
            """)
            # Migration: migrate existing enroll_code from modules to access_links
            cur.execute("""
                INSERT INTO ki_tutor_access_links (module_id, code, expires_at)
                SELECT id, enroll_code, enroll_code_expires
                FROM ki_tutor_modules
                WHERE enroll_code IS NOT NULL
                  AND enroll_code_expires IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM ki_tutor_access_links al
                      WHERE al.code = ki_tutor_modules.enroll_code
                  )
            """)
            # Migration: link existing enrollments to their access_links
            cur.execute("""
                UPDATE ki_tutor_enrollments e
                SET link_id = al.id
                FROM ki_tutor_access_links al
                JOIN ki_tutor_modules m ON m.id = al.module_id
                WHERE e.module_id = m.id
                  AND al.code = m.enroll_code
                  AND e.link_id IS NULL
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_sources (
                    id              SERIAL PRIMARY KEY,
                    uuid            TEXT NOT NULL UNIQUE,
                    module_id       INTEGER NOT NULL
                                      REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    filename        TEXT NOT NULL,
                    file_path       TEXT NOT NULL,
                    file_type       TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    chunk_count     INTEGER NOT NULL DEFAULT 0,
                    embedding_model TEXT NOT NULL DEFAULT '',
                    toc             JSONB,
                    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: add toc column if missing
            cur.execute("""
                ALTER TABLE ki_tutor_sources ADD COLUMN IF NOT EXISTS toc JSONB
            """)
            # Migration: add summaries_status column if missing
            cur.execute("""
                ALTER TABLE ki_tutor_sources ADD COLUMN IF NOT EXISTS summaries_status TEXT NOT NULL DEFAULT 'none'
            """)
            # Migration: add duration column for audio/video sources
            cur.execute("""
                ALTER TABLE ki_tutor_sources ADD COLUMN IF NOT EXISTS duration REAL
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_chunks (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_sources(id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    content     TEXT NOT NULL,
                    embedding   vector,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: drop fixed-dimension constraint so any embedding model can be used
            cur.execute("""
                ALTER TABLE ki_tutor_chunks
                    ALTER COLUMN embedding TYPE vector
                    USING embedding::vector
            """)
            # Migration: add start_time/end_time for audio/video chunks
            cur.execute("""
                ALTER TABLE ki_tutor_chunks ADD COLUMN IF NOT EXISTS start_time REAL
            """)
            cur.execute("""
                ALTER TABLE ki_tutor_chunks ADD COLUMN IF NOT EXISTS end_time REAL
            """)
            # Hybrid Search: tsvector column for BM25-style keyword search
            cur.execute("""
                ALTER TABLE ki_tutor_chunks
                    ADD COLUMN IF NOT EXISTS search_vector tsvector
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_search
                ON ki_tutor_chunks USING gin(search_vector)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_paragraph_summaries (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_sources(id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    block_index INTEGER NOT NULL,
                    bbox_x0     REAL NOT NULL,
                    bbox_y0     REAL NOT NULL,
                    bbox_x1     REAL NOT NULL,
                    bbox_y1     REAL NOT NULL,
                    content     TEXT NOT NULL,
                    summary     TEXT NOT NULL,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_mindmaps (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    source_ids  JSONB NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    mindmap     JSONB,
                    error       TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_presentations (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    source_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_sources(id) ON DELETE CASCADE,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    title       TEXT,
                    slides      JSONB,
                    pptx_path   TEXT,
                    presenton_id TEXT,
                    error       TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE ki_tutor_presentations ADD COLUMN IF NOT EXISTS presenton_id TEXT")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_infographics (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    source_ids  JSONB NOT NULL,
                    style       TEXT NOT NULL DEFAULT 'professional',
                    status      TEXT NOT NULL DEFAULT 'pending',
                    title       TEXT,
                    layout_data JSONB,
                    error       TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_datentabellen (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    source_ids  JSONB NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    title       TEXT,
                    table_data  JSONB,
                    sources     JSONB,
                    error       TEXT,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_messages (
                    id           SERIAL PRIMARY KEY,
                    module_id    INTEGER NOT NULL
                                   REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    role         TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    source_pages JSONB,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: add enrollment_id to messages for per-link scoping
            cur.execute("ALTER TABLE ki_tutor_messages ADD COLUMN IF NOT EXISTS enrollment_id INTEGER REFERENCES ki_tutor_enrollments(id) ON DELETE SET NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_user_settings (
                    id                   SERIAL PRIMARY KEY,
                    module_id            INTEGER NOT NULL
                                           REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id              INTEGER NOT NULL,
                    chat_lang            TEXT NOT NULL DEFAULT 'de',
                    studio_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
                    sprachtraining_active BOOLEAN NOT NULL DEFAULT FALSE,
                    UNIQUE (module_id, user_id)
                )
            """)
            cur.execute("ALTER TABLE ki_tutor_user_settings ADD COLUMN IF NOT EXISTS studio_enabled BOOLEAN NOT NULL DEFAULT TRUE")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_notes (
                    id         SERIAL PRIMARY KEY,
                    module_id  INTEGER NOT NULL
                                 REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id    INTEGER NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_glossary_entries (
                    id               SERIAL PRIMARY KEY,
                    source_id        INTEGER NOT NULL
                                       REFERENCES ki_tutor_sources(id) ON DELETE CASCADE,
                    term_de          TEXT NOT NULL,
                    term_en          TEXT NOT NULL,
                    definition       TEXT NOT NULL,
                    definition_en    TEXT,
                    example_sentence TEXT,
                    example_sentence_en TEXT,
                    page_number      INTEGER,
                    created_at       TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_glossary_source
                ON ki_tutor_glossary_entries(source_id)
            """)
            # Migration: add English columns to glossary
            cur.execute("ALTER TABLE ki_tutor_glossary_entries ADD COLUMN IF NOT EXISTS definition_en TEXT")
            cur.execute("ALTER TABLE ki_tutor_glossary_entries ADD COLUMN IF NOT EXISTS example_sentence_en TEXT")
            # ─── Exercise Sets ──────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_exercise_sets (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    tool        TEXT NOT NULL,
                    title       TEXT NOT NULL,
                    mode        TEXT NOT NULL DEFAULT 'glossar',
                    source_uuid TEXT,
                    card_count  INTEGER NOT NULL DEFAULT 0,
                    status      TEXT NOT NULL DEFAULT 'generating',
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_exercise_items (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES ki_tutor_exercise_sets(id) ON DELETE CASCADE,
                    position    INTEGER NOT NULL DEFAULT 0,
                    front       TEXT NOT NULL,
                    back        TEXT NOT NULL,
                    options     JSONB,
                    correct_idx INTEGER,
                    source_label TEXT,
                    page_number INTEGER,
                    explanation TEXT,
                    start_time  REAL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_exercise_progress (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES ki_tutor_exercise_sets(id) ON DELETE CASCADE,
                    item_id     INTEGER NOT NULL
                                  REFERENCES ki_tutor_exercise_items(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    correct     BOOLEAN NOT NULL,
                    answered_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # ─── Streak Tracking ────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ki_tutor_streaks (
                    id              SERIAL PRIMARY KEY,
                    module_id       INTEGER NOT NULL
                                      REFERENCES ki_tutor_modules(id) ON DELETE CASCADE,
                    user_id         INTEGER NOT NULL,
                    current_streak  INTEGER NOT NULL DEFAULT 0,
                    max_streak      INTEGER NOT NULL DEFAULT 0,
                    last_active_date DATE,
                    UNIQUE (module_id, user_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_sets_module_user
                ON ki_tutor_exercise_sets(module_id, user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_items_set
                ON ki_tutor_exercise_items(set_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_progress_set_user
                ON ki_tutor_exercise_progress(set_id, user_id)
            """)
            # Migration: add status column if table existed before
            cur.execute("ALTER TABLE ki_tutor_exercise_sets ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ready'")
            # Migration: add start_time for audio/video exercise items
            cur.execute("ALTER TABLE ki_tutor_exercise_items ADD COLUMN IF NOT EXISTS start_time REAL")
            # Migration: add back_en for bilingual flashcards
            cur.execute("ALTER TABLE ki_tutor_exercise_items ADD COLUMN IF NOT EXISTS back_en TEXT")
            # Migration: last_run_start for tracking exercise run boundaries
            cur.execute("ALTER TABLE ki_tutor_exercise_sets ADD COLUMN IF NOT EXISTS last_run_start TIMESTAMP")
            # Migration: drop legacy mastery columns if they exist
            for col in ("correct_streak", "total_attempts", "total_correct"):
                cur.execute(f"ALTER TABLE ki_tutor_exercise_items DROP COLUMN IF EXISTS {col}")
        conn.commit()

    # Backfill tsvector for existing chunks (separate transaction)
    from loguru import logger as _log
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ki_tutor_chunks WHERE search_vector IS NULL")
            null_count = cur.fetchone()[0]
            if null_count > 0:
                _log.info("Backfilling search_vector for {} chunks...", null_count)
                cur.execute("""
                    UPDATE ki_tutor_chunks
                    SET search_vector = to_tsvector('german', content)
                    WHERE search_vector IS NULL
                """)
                _log.info("search_vector backfill done.")
            else:
                _log.info("search_vector: all chunks already populated.")
        conn.commit()

        conn.commit()


# --- Users ---

def get_user_by_username(ldap_username: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE ldap_username = %s", (ldap_username,))
            return cur.fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()


def create_user(ldap_username: str, display_name: str, email: str, active: int, role: str = "lecturer") -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (ldap_username, display_name, email, active, role) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (ldap_username, display_name, email, active, role),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id


def update_user(user_id: int, display_name: str, email: str, active: int, role: str = "lecturer") -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET display_name = %s, email = %s, active = %s, role = %s WHERE id = %s",
                (display_name, email, active, role, user_id),
            )
        conn.commit()


# --- Whitelist ---

def get_whitelist_emails() -> list[str]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT email FROM whitelist ORDER BY created_at")
            rows = cur.fetchall()
        return [row["email"] for row in rows]


def add_to_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                (email.strip().lower(),),
            )
        conn.commit()


def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
        conn.commit()


def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
            return cur.fetchone() is not None


# --- Settings (key/value store) ---

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO settings (key, value)
                   VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE
                   SET value = EXCLUDED.value,
                       updated_at = NOW()""",
                (key, value),
            )
        conn.commit()


# --- Jobs ---

def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
    username: str = "unknown",
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at, username)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (job_uuid, user_id, tool, original_filename, input_path, expires_at, username),
            )
        conn.commit()


def update_job_expiry(job_uuid: str, hours: int) -> None:
    """Extend (or set) the expires_at for a job to now + hours."""
    new_expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET expires_at = %s WHERE job_uuid = %s",
                (new_expiry, job_uuid),
            )
        conn.commit()


def set_job_input_path(job_uuid: str, input_path: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET input_path = %s WHERE job_uuid = %s",
                (input_path, job_uuid),
            )
        conn.commit()


def get_job(job_uuid: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE job_uuid = %s", (job_uuid,))
            return cur.fetchone()


def get_jobs_by_user(
    user_id: int, limit: int = 20, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
    extra_tools: list[str] | None = None,
    tool_filter: list[str] | None = None,
) -> tuple[list[dict], int]:
    conditions = ["user_id = %s", "(expires_at IS NULL OR expires_at > NOW())"]
    params: list = [user_id]
    if q:
        like = f"%{q}%"
        if extra_tools:
            conditions.append("(original_filename ILIKE %s OR tool ILIKE %s OR tool = ANY(%s))")
            params += [like, like, extra_tools]
        else:
            conditions.append("(original_filename ILIKE %s OR tool ILIKE %s)")
            params += [like, like]
    if tool_filter:
        conditions.append("tool = ANY(%s)")
        params.append(tool_filter)
    if date_from:
        conditions.append("created_at::date >= %s::date")
        params.append(date_from)
    if date_to:
        conditions.append("created_at::date <= %s::date")
        params.append(date_to)
    where = " AND ".join(conditions)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM jobs WHERE {where}", params)
            total = cur.fetchone()["total"]
            cur.execute(
                f"SELECT * FROM jobs WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows], total


def set_job_celery_task_id(job_uuid: str, celery_task_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET celery_task_id = %s WHERE job_uuid = %s",
                (celery_task_id, job_uuid),
            )
        conn.commit()


def get_job_by_celery_task_id(celery_task_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE celery_task_id = %s AND status = 'running'",
                (celery_task_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None


def delete_job(job_uuid: str) -> dict | None:
    """Delete a job record and return its file paths for cleanup."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT input_path, result_path, celery_task_id FROM jobs WHERE job_uuid = %s",
                (job_uuid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("DELETE FROM jobs WHERE job_uuid = %s", (job_uuid,))
        conn.commit()
        return dict(row)


def count_active_jobs_for_tool(user_id: int, tools: list[str]) -> int:
    """Return the number of pending/running/awaiting_user jobs the user has for any of the given tools."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user')""",
                (user_id, tools),
            )
            row = cur.fetchone()
            return row[0] if row else 0


def has_active_job_for_tool(user_id: int, tools: list[str]) -> bool:
    """Return True if the user has a pending/running/awaiting_user job for any of the given tools."""
    return count_active_jobs_for_tool(user_id, tools) > 0


def count_all_jobs_for_tool(user_id: int, tools: list[str]) -> int:
    """Return total non-terminal jobs (pending/running/awaiting_user/queued) for quota/queue-size checks."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user', 'queued')""",
                (user_id, tools),
            )
            row = cur.fetchone()
            return row[0] if row else 0


def get_next_queued_job(user_id: int, tools: list[str]) -> dict | None:
    """Atomically claim the oldest queued job by transitioning queued → pending,
    but only if the user has no currently active (pending/running) job.
    awaiting_user does NOT block dispatch — it uses no Celery slot.
    Returns the updated job row, or None if no queued job exists or user is already active."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """UPDATE jobs SET status = 'pending'
                   WHERE job_uuid = (
                       SELECT j.job_uuid FROM jobs j
                       WHERE j.user_id = %s AND j.tool = ANY(%s) AND j.status = 'queued'
                       AND NOT EXISTS (
                           SELECT 1 FROM jobs a
                           WHERE a.user_id = %s AND a.tool = ANY(%s)
                           AND a.status IN ('pending', 'running')
                       )
                       ORDER BY j.created_at ASC
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED
                   )
                   RETURNING *""",
                (user_id, tools, user_id, tools),
            )
            conn.commit()
            row = cur.fetchone()
            result = dict(row) if row else None
    if result:
        _notify_job_update(result["job_uuid"])
    return result


def count_all_jobs_for_tool_excluding(user_id: int, tools: list[str], exclude_uuid: str) -> int:
    """Count active/queued jobs (pending/running/awaiting_user/queued) excluding a specific job."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user', 'queued')
                   AND job_uuid != %s""",
                (user_id, tools, exclude_uuid),
            )
            row = cur.fetchone()
            return row[0] if row else 0


def set_generating_scripts_flag(job_uuid: str, generating: bool) -> None:
    """Merge or remove the 'generating_scripts' marker in the job's progress JSON.

    Used to signal My Jobs that the resume button should be hidden while
    script generation is in progress.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT progress FROM jobs WHERE job_uuid = %s", (job_uuid,))
            row = cur.fetchone()
            if row is None:
                return
            try:
                progress = json.loads(row[0] or "{}")
            except Exception:
                progress = {}
            if generating:
                progress["generating_scripts"] = True
            else:
                progress.pop("generating_scripts", None)
            cur.execute(
                "UPDATE jobs SET progress = %s WHERE job_uuid = %s",
                (json.dumps(progress), job_uuid),
            )
        conn.commit()
    _notify_job_update(job_uuid)


def transition_job_to_pending(
    job_uuid: str,
    user_id: int,
    from_statuses: tuple = ("awaiting_user",),
) -> bool:
    """Atomically transition a job to 'pending' from one of the allowed source statuses.

    Uses SELECT FOR UPDATE to prevent race conditions when multiple tabs
    submit the same job simultaneously.

    Returns True if the transition succeeded (this caller owns the job),
    False if another request already transitioned it (status not in from_statuses).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status FROM jobs
                   WHERE job_uuid = %s AND user_id = %s
                   FOR UPDATE""",
                (job_uuid, user_id),
            )
            row = cur.fetchone()
            if row is None or row[0] not in from_statuses:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE jobs SET status = 'pending' WHERE job_uuid = %s",
                (job_uuid,),
            )
        conn.commit()
    return True


def transition_job_to_queued(
    job_uuid: str,
    user_id: int,
    from_statuses: tuple = ("awaiting_user", "failed", "success"),
) -> bool:
    """Atomically transition a job to 'queued' from one of the allowed source statuses."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status FROM jobs
                   WHERE job_uuid = %s AND user_id = %s
                   FOR UPDATE""",
                (job_uuid, user_id),
            )
            row = cur.fetchone()
            if row is None or row[0] not in from_statuses:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE jobs SET status = 'queued', error_message = NULL WHERE job_uuid = %s",
                (job_uuid,),
            )
        conn.commit()
    _notify_job_update(job_uuid)
    return True


def get_all_results_for_user(user_id: int) -> list[dict]:
    """Return all jobs with a result_path for the given user, ordered oldest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, job_uuid, result_path, result_filename, original_filename FROM jobs
                   WHERE user_id = %s AND result_path IS NOT NULL AND status != 'failed'
                   ORDER BY created_at ASC""",
                (user_id,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_all_users(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
) -> tuple[list[dict], int]:
    """All users, newest first. Returns (users, total_count).

    Filters: q (name/username/email), date_from/date_to (YYYY-MM-DD).
    """
    conditions = []
    params: list = []

    if q:
        like = f"%{q}%"
        conditions.append("(display_name ILIKE %s OR ldap_username ILIKE %s OR email ILIKE %s)")
        params += [like, like, like]
    if date_from:
        conditions.append("created_at >= %s::timestamp")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("created_at <= %s::timestamp")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) AS total FROM users {where}", params)
            total = cur.fetchone()["total"]
    return [dict(row) for row in rows], total


def get_pending_users() -> list[dict]:
    """Users with active=0 (passed LDAP auth but not yet whitelisted)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE active = 0 ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def activate_user(user_id: int) -> None:
    """Set active=1 for the given user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = 1 WHERE id = %s", (user_id,))
        conn.commit()


def deactivate_user_by_email(email: str) -> None:
    """Set active=0 for any user with the given email."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active = 0 WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
        conn.commit()


def get_all_jobs(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
    extra_tools: list[str] | None = None,
) -> tuple[list[dict], int]:
    """All jobs across all users, with display_name via JOIN, newest first.

    Returns (jobs, total_count).
    Filters: q (user/tool/filename), date_from/date_to (YYYY-MM-DD).
    """
    conditions = ["(j.expires_at IS NULL OR j.expires_at > NOW())"]
    params: list = []

    if q:
        like = f"%{q}%"
        if extra_tools:
            conditions.append(
                "(u.display_name ILIKE %s OR u.ldap_username ILIKE %s OR j.tool ILIKE %s OR j.original_filename ILIKE %s OR j.tool = ANY(%s))"
            )
            params += [like, like, like, like, extra_tools]
        else:
            conditions.append(
                "(u.display_name ILIKE %s OR u.ldap_username ILIKE %s OR j.tool ILIKE %s OR j.original_filename ILIKE %s)"
            )
            params += [like, like, like, like]
    if date_from:
        conditions.append("j.created_at >= %s::timestamp")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("j.created_at <= %s::timestamp")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = "WHERE " + " AND ".join(conditions)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT j.*, u.display_name AS user_display_name, u.ldap_username
                   FROM jobs j
                   LEFT JOIN users u ON j.user_id = u.id
                   {where}
                   ORDER BY j.created_at DESC
                   LIMIT %s OFFSET %s""",
                params + [limit, offset],
            )
            rows = cur.fetchall()
            cur.execute(
                f"""SELECT COUNT(*) AS total FROM jobs j
                   LEFT JOIN users u ON j.user_id = u.id
                   {where}""",
                params,
            )
            total = cur.fetchone()["total"]
    return [dict(row) for row in rows], total


def get_job_stats(days: int = 30) -> dict:
    """Aggregated job statistics for the admin dashboard."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 1. Jobs per tool + status
            cur.execute("""
                SELECT tool, status, COUNT(*) AS cnt
                FROM jobs
                WHERE created_at >= NOW() - INTERVAL '%s days'
                GROUP BY tool, status
                ORDER BY tool, status
            """, (days,))
            by_tool_status = [dict(r) for r in cur.fetchall()]

            # 2. Jobs per day (last N days)
            cur.execute("""
                SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date AS day,
                       COUNT(*) AS cnt
                FROM jobs
                WHERE created_at >= NOW() - INTERVAL '%s days'
                GROUP BY day ORDER BY day
            """, (days,))
            by_day = [{"day": str(r["day"]), "count": r["cnt"]} for r in cur.fetchall()]

            # 3. Top users
            cur.execute("""
                SELECT u.display_name, u.ldap_username, COUNT(*) AS cnt
                FROM jobs j
                JOIN users u ON j.user_id = u.id
                WHERE j.created_at >= NOW() - INTERVAL '%s days'
                GROUP BY u.display_name, u.ldap_username
                ORDER BY cnt DESC LIMIT 10
            """, (days,))
            top_users = [
                {"name": r["display_name"] or r["ldap_username"], "count": r["cnt"]}
                for r in cur.fetchall()
            ]

            # 4. Avg duration per tool (only completed jobs)
            cur.execute("""
                SELECT tool,
                       ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))::numeric, 1) AS avg_sec
                FROM jobs
                WHERE status = 'success' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                  AND created_at >= NOW() - INTERVAL '%s days'
                GROUP BY tool ORDER BY tool
            """, (days,))
            avg_duration = {r["tool"]: float(r["avg_sec"]) for r in cur.fetchall()}

    return {
        "by_tool_status": by_tool_status,
        "by_day": by_day,
        "top_users": top_users,
        "avg_duration": avg_duration,
    }


def get_job_activity_log(days: int = 30, limit: int = 50) -> list[dict]:
    """Recent job activity for admin dashboard — chronological log."""
    screencast_tools = {"screencast_render", "screencast_auto", "screencast_demo_render", "screencast_translate"}
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT j.tool, j.status, j.created_at, j.completed_at,
                          j.started_at, j.render_started_at, j.original_filename,
                          u.display_name, u.ldap_username
                   FROM jobs j
                   JOIN users u ON j.user_id = u.id
                   WHERE j.created_at >= NOW() - INTERVAL '%s days'
                   ORDER BY j.created_at DESC
                   LIMIT %s""",
                (days, limit),
            )
            rows = []
            for r in cur.fetchall():
                # Duration: for screencast tools use render time, otherwise total time
                duration_sec = None
                if r["status"] == "success" and r["completed_at"]:
                    if r["tool"] in screencast_tools and r["render_started_at"]:
                        duration_sec = (r["completed_at"] - r["render_started_at"]).total_seconds()
                    elif r["started_at"]:
                        duration_sec = (r["completed_at"] - r["started_at"]).total_seconds()

                rows.append({
                    "user": r["display_name"] or r["ldap_username"] or "Unbekannt",
                    "tool": r["tool"],
                    "status": r["status"],
                    "filename": r["original_filename"],
                    "created_at": r["created_at"].isoformat() + "Z" if r["created_at"] else None,
                    "duration_seconds": round(duration_sec, 1) if duration_sec is not None else None,
                })
    return rows


def update_job_status(
    job_uuid: str,
    status: str,
    error_message: str | None = None,
    progress: dict | None = None,
) -> None:
    progress_json = json.dumps(progress) if progress is not None else None
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s,
                           started_at = COALESCE(started_at, %s)
                       WHERE job_uuid = %s AND status != 'awaiting_user'""",
                    (status, error_message, progress_json, now, now, job_uuid),
                )
            elif status in ("success", "failed"):
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s, completed_at = %s
                       WHERE job_uuid = %s AND status != 'awaiting_user'""",
                    (status, error_message, progress_json, now, now, job_uuid),
                )
            else:
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s
                       WHERE job_uuid = %s""",
                    (status, error_message, progress_json, now, job_uuid),
                )
        conn.commit()
    if status in ("success", "failed", "awaiting_user", "pending", "queued", "running"):
        _notify_job_update(job_uuid)


def reset_job_to_awaiting(job_uuid: str) -> None:
    """Stop a running render: set status back to awaiting_user, clear task ID and progress."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'awaiting_user', celery_task_id = NULL,
                       progress = NULL, progress_updated_at = %s
                   WHERE job_uuid = %s""",
                (now, job_uuid),
            )
        conn.commit()
    _notify_job_update(job_uuid)


def set_render_started_at(job_uuid: str) -> None:
    """Setzt render_started_at einmalig (COALESCE — nicht überschreiben bei Retry)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_started_at = COALESCE(render_started_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def set_render_queued_at(job_uuid: str) -> None:
    """Setzt render_queued_at einmalig — Zeitpunkt wenn Render-Job in Celery Queue eingereiht wird."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_queued_at = COALESCE(render_queued_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def claim_job_for_retry(job_uuid: str) -> bool:
    """Atomically set job status from 'failed' to 'running' for retry.
    Returns True if successful, False if job was not in 'failed' state (race condition)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs SET status = 'running', progress_updated_at = %s, error_message = NULL
                   WHERE job_uuid = %s AND status = 'failed'""",
                (now, job_uuid),
            )
            affected = cur.rowcount
        conn.commit()
        return affected == 1


def reset_stuck_jobs() -> int:
    """Mark all pending/running jobs as failed on server startup.

    Called once when the backend starts. Jobs stuck in 'pending' or 'running'
    mean the server crashed mid-task and the Celery broker lost the message.
    They can be manually retried via the retry endpoint.
    Returns the number of jobs reset.
    """
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'failed',
                       error_message = 'Server wurde neugestartet — bitte Wiederholen klicken.',
                       completed_at = %s
                   WHERE status IN ('pending', 'running')""",
                (now,),
            )
            affected = cur.rowcount
        conn.commit()
        return affected


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> list[str]:
    """Save job result. Returns job_uuids that exceed MAX_RESULT_FILES and must be evicted.

    Callers must delete each returned UUID from storage BEFORE calling delete_job()
    so that _job_folder_name() can still resolve the folder name from the DB.
    Use storage.save_result_and_evict() which handles this automatically.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "UPDATE jobs SET result_path = %s, result_filename = %s WHERE job_uuid = %s RETURNING user_id",
                (result_path, result_filename, job_uuid),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return []
            user_id = row["user_id"]
        conn.commit()

    old_jobs = get_all_results_for_user(user_id)
    excess = len(old_jobs) - MAX_RESULT_FILES
    if excess <= 0:
        return []
    return [old_jobs[i]["job_uuid"] for i in range(excess)]


def touch_job_heartbeat(job_uuid: str) -> None:
    """Update progress_updated_at without touching any other field.
    Called periodically during long external API calls to prevent the watchdog
    from falsely marking an actively-running job as stuck.
    Only updates if the job is still in 'running' state.
    """
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET progress_updated_at = %s WHERE job_uuid = %s AND status = 'running'",
                (now, job_uuid),
            )
        conn.commit()


def get_stale_awaiting_user_jobs(threshold_hours: int = 2) -> list[dict]:
    """Return awaiting_user jobs older than threshold_hours (user never came back to resume)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT job_uuid, tool FROM jobs WHERE status = 'awaiting_user' AND created_at <= %s",
                (cutoff,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_stuck_running_jobs(threshold_minutes: int = 20) -> list[dict]:
    """Return running/pending jobs that have not made progress for longer than threshold_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, tool, progress, progress_updated_at FROM jobs
                   WHERE (
                       (status = 'running' AND progress_updated_at IS NOT NULL AND progress_updated_at <= %s)
                       OR
                       (status = 'running' AND progress_updated_at IS NULL AND created_at <= %s)
                       OR
                       (status = 'pending' AND created_at <= %s)
                   )""",
                (cutoff, cutoff, cutoff),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


# --- Quota ---

def quota_get_override(user_id: int, quota_type: str) -> Optional[int]:
    """Return per-user override limit, or None if no override exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT limit_value FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
            row = cur.fetchone()
    return row[0] if row else None


def quota_set_override(user_id: int, quota_type: str, limit_value: int) -> None:
    """Upsert a per-user override. limit_value=-1 means unlimited."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_quota_overrides (user_id, quota_type, limit_value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, quota_type)
                   DO UPDATE SET limit_value = EXCLUDED.limit_value, updated_at = NOW()""",
                (user_id, quota_type, limit_value),
            )
        conn.commit()


def quota_remove_override(user_id: int, quota_type: str) -> None:
    """Remove a per-user override so the user falls back to the global default."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
        conn.commit()


def quota_reset(user_id: int, quota_type: str) -> None:
    """Admin: immediately zero a user's quota counter and clear the global reset timer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_quotas
                   SET used = 0, window_started_at = NULL, reset_at = NULL, updated_at = NOW()
                   WHERE user_id = %s AND quota_type = %s""",
                (user_id, quota_type),
            )
            cur.execute(
                "DELETE FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()


def quota_get_all_for_user(user_id: int) -> tuple[list[dict], Optional[datetime]]:
    """Return all quota rows for a user (used, reset_at, override if any) plus the global reset_at."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT
                     COALESCE(q.quota_type, o.quota_type) AS quota_type,
                     COALESCE(q.used, 0)                  AS used,
                     q.reset_at,
                     o.limit_value                        AS override
                   FROM user_quotas q
                   FULL OUTER JOIN user_quota_overrides o
                     ON o.user_id = q.user_id AND o.quota_type = q.quota_type
                   WHERE COALESCE(q.user_id, o.user_id) = %s""",
                (user_id,),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT reset_at FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
            gr = cur.fetchone()
            global_reset_at: Optional[datetime] = gr["reset_at"] if gr else None
    return [dict(row) for row in rows], global_reset_at


def quota_get_all_users_usage() -> list[dict]:
    """Admin: return all active users with quota data (used=0 if no activity yet)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          q.quota_type, COALESCE(q.used, 0) AS used, q.reset_at,
                          o.limit_value AS override
                   FROM users u
                   LEFT JOIN user_quotas q ON q.user_id = u.id
                   LEFT JOIN user_quota_overrides o
                     ON o.user_id = u.id AND o.quota_type = q.quota_type
                   WHERE u.active = 1
                   ORDER BY u.display_name, q.quota_type"""
            )
            rows = cur.fetchall()
            cur.execute("SELECT user_id, reset_at FROM user_quota_resets")
            global_resets = cur.fetchall()
    result = [dict(row) for row in rows]
    resets_by_uid = {gr["user_id"]: gr["reset_at"] for gr in global_resets}
    for row in result:
        uid = row["user_id"]
        gr_at = resets_by_uid.get(uid)
        row["global_reset_at"] = (gr_at.isoformat() + "Z") if gr_at else None
    return result


def quota_get_all_overrides() -> list[dict]:
    """Return all override rows with user display name."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          o.quota_type, o.limit_value
                   FROM user_quota_overrides o
                   JOIN users u ON u.id = o.user_id
                   ORDER BY u.display_name, o.quota_type"""
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


# --- KI Tutor: Modules ---

def create_ki_tutor_module(user_id: int, title: str, description: str | None) -> str:
    import uuid as _uuid
    module_uuid = str(_uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_modules (uuid, user_id, title, description)
                   VALUES (%s, %s, %s, %s)""",
                (module_uuid, user_id, title, description),
            )
        conn.commit()
    return module_uuid


def get_ki_tutor_module(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_modules WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_module_by_id(id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_modules WHERE id = %s", (id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_modules_by_user(user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_modules WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_ki_tutor_modules_for_student(user_id: int) -> list[dict]:
    """Return modules with enrollment info. Same module can appear multiple times (different links)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, e.id AS enrollment_id, e.link_id, e.enrolled_until,
                          al.code AS link_code, al.expires_at AS link_expires_at
                   FROM ki_tutor_modules m
                   JOIN ki_tutor_enrollments e ON e.module_id = m.id
                   LEFT JOIN ki_tutor_access_links al ON al.id = e.link_id
                   WHERE e.user_id = %s AND m.is_active = TRUE
                   ORDER BY e.created_at DESC""",
                (user_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def update_ki_tutor_module(
    uuid: str, title: str, description: str | None, is_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_modules
                   SET title = %s, description = %s, is_active = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (title, description, is_active, uuid),
            )
        conn.commit()


def update_ki_tutor_module_status(
    uuid: str,
    status: str,
    embedding_model: str | None = None,
    embedding_fingerprint: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_modules
                   SET status = %s,
                       embedding_model = COALESCE(%s, embedding_model),
                       embedding_fingerprint = COALESCE(%s, embedding_fingerprint),
                       updated_at = NOW()
                   WHERE uuid = %s""",
                (status, embedding_model, embedding_fingerprint, uuid),
            )
        conn.commit()


def set_ki_tutor_module_enroll_code(
    uuid: str, code: str, expires_at: datetime
) -> None:
    """Legacy: kept for backward compat. Prefer create_access_link."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_modules
                   SET enroll_code = %s, enroll_code_expires = %s, updated_at = NOW()
                   WHERE uuid = %s""",
                (code, expires_at, uuid),
            )
        conn.commit()


def delete_ki_tutor_module(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_modules WHERE uuid = %s", (uuid,))
        conn.commit()


# --- KI Tutor: Access Links ---

def create_access_link(module_id: int, code: str, expires_at: datetime) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO ki_tutor_access_links (module_id, code, expires_at)
                   VALUES (%s, %s, %s)
                   RETURNING id, module_id, code, expires_at, created_at""",
                (module_id, code, expires_at),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row)


def get_access_links_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, module_id, code, expires_at, created_at
                   FROM ki_tutor_access_links
                   WHERE module_id = %s
                   ORDER BY created_at ASC""",
                (module_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def delete_access_link(link_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_access_links WHERE id = %s", (link_id,))
        conn.commit()


def get_module_by_access_link_code(code: str) -> tuple[dict, dict] | None:
    """Return (module, link) tuple if code is valid and not expired."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.*, al.id AS link_id, al.expires_at AS link_expires_at
                   FROM ki_tutor_access_links al
                   JOIN ki_tutor_modules m ON m.id = al.module_id
                   WHERE al.code = %s AND al.expires_at > NOW()""",
                (code,),
            )
            row = cur.fetchone()
    if not row:
        return None
    row = dict(row)
    link = {"id": row.pop("link_id"), "expires_at": row.pop("link_expires_at")}
    return row, link


# --- KI Tutor: Enrollments ---

def enroll_student(
    module_id: int, user_id: int, enrolled_until: datetime | None,
    link_id: int | None = None,
) -> int | None:
    """Enroll student. Returns enrollment id, or None if already enrolled for this link."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_enrollments (module_id, user_id, link_id, enrolled_until)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (module_id, user_id, link_id) DO NOTHING
                   RETURNING id""",
                (module_id, user_id, link_id, enrolled_until),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def is_student_enrolled(module_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM ki_tutor_enrollments WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            return cur.fetchone() is not None


def get_enrollment(module_id: int, user_id: int, link_id: int | None = None) -> dict | None:
    """Get a specific enrollment by module, user, and optionally link."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if link_id is not None:
                cur.execute(
                    "SELECT * FROM ki_tutor_enrollments WHERE module_id = %s AND user_id = %s AND link_id = %s",
                    (module_id, user_id, link_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM ki_tutor_enrollments WHERE module_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
                    (module_id, user_id),
                )
            row = cur.fetchone()
    return dict(row) if row else None


def get_enrollment_by_id(enrollment_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_enrollments WHERE id = %s", (enrollment_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_module_by_enroll_code(code: str) -> dict | None:
    """Legacy: check both access_links and modules table."""
    result = get_module_by_access_link_code(code)
    if result:
        return result[0]  # return just the module for backward compat
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_modules
                   WHERE enroll_code = %s AND enroll_code_expires > NOW()""",
                (code,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# --- KI Tutor: Sources ---

def create_ki_tutor_source(
    module_id: int, uuid: str, filename: str, file_path: str, file_type: str
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_sources
                   (module_id, uuid, filename, file_path, file_type)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING id""",
                (module_id, uuid, filename, file_path, file_type),
            )
            source_id = cur.fetchone()[0]
        conn.commit()
    return source_id


def get_ki_tutor_source(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_sources WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_sources_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_sources WHERE module_id = %s ORDER BY created_at ASC",
                (module_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def update_ki_tutor_source_status(
    uuid: str,
    status: str,
    chunk_count: int | None = None,
    embedding_model: str | None = None,
    error_message: str | None = None,
    duration: float | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_sources
                   SET status = %s,
                       chunk_count = COALESCE(%s, chunk_count),
                       embedding_model = COALESCE(%s, embedding_model),
                       error_message = COALESCE(%s, error_message),
                       duration = COALESCE(%s, duration)
                   WHERE uuid = %s""",
                (status, chunk_count, embedding_model, error_message, duration, uuid),
            )
        conn.commit()


def update_ki_tutor_source_toc(uuid: str, toc: list[dict]) -> None:
    import json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_sources SET toc = %s WHERE uuid = %s",
                (json.dumps(toc), uuid),
            )
        conn.commit()


def delete_ki_tutor_source(uuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_sources WHERE uuid = %s", (uuid,))
        conn.commit()


# --- KI Tutor: Chunks ---

def create_ki_tutor_chunk(
    source_id: int,
    page_number: int,
    content: str,
    start_time: float | None = None,
    end_time: float | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_chunks
                   (source_id, page_number, content, search_vector, start_time, end_time)
                   VALUES (%s, %s, %s, to_tsvector('german', %s), %s, %s)
                   RETURNING id""",
                (source_id, page_number, content, content, start_time, end_time),
            )
            chunk_id = cur.fetchone()[0]
        conn.commit()
    return chunk_id


def get_ki_tutor_chunks_by_source(source_id: int) -> list[dict]:
    """Return all chunks for a source (without embeddings), ordered by page/time."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM ki_tutor_chunks
                   WHERE source_id = %s
                   ORDER BY COALESCE(start_time, 0), page_number""",
                (source_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def update_chunk_embedding(chunk_id: int, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_chunks SET embedding = %s::vector WHERE id = %s",
                (str(embedding), chunk_id),
            )
        conn.commit()


def search_similar_chunks(
    module_id: int,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 5,
) -> list[dict]:
    params: list = [str(query_embedding), module_id]
    source_filter = ""
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        params.append(source_ids)
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT c.id, c.source_id, c.page_number, c.content,
                           c.start_time, c.end_time,
                           c.embedding <=> %s::vector AS distance
                    FROM ki_tutor_chunks c
                    JOIN ki_tutor_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.embedding IS NOT NULL
                    ORDER BY distance ASC
                    LIMIT %s""",
                params,
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def hybrid_search_chunks(
    module_id: int,
    query_text: str,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 15,
    rrf_k: int = 60,
) -> list[dict]:
    """Hybrid search: combines vector similarity + BM25 keyword search via RRF."""
    from loguru import logger

    source_filter = ""
    source_param: list = []
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        source_param = [source_ids]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # 1) Vector search (top 40)
            cur.execute(
                f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                        ORDER BY c.embedding <=> %s::vector
                    ) AS rank
                    FROM ki_tutor_chunks c
                    JOIN ki_tutor_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT 40""",
                [str(query_embedding), module_id] + source_param + [str(query_embedding)],
            )
            vec_rows = cur.fetchall()
            vec_pages = sorted(set(r["page_number"] for r in vec_rows))
            logger.info("Hybrid Vector: {} hits, Seiten: {}", len(vec_rows), vec_pages)

            # 2) Keyword search (top 40) — OR-Verknüpfung damit einzelne Suchbegriffe matchen
            cur.execute(
                f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                        ORDER BY ts_rank_cd(c.search_vector,
                            (regexp_replace(plainto_tsquery('german', %s)::text, ' & ', ' | ', 'g'))::tsquery
                        ) DESC
                    ) AS rank
                    FROM ki_tutor_chunks c
                    JOIN ki_tutor_sources s ON s.id = c.source_id
                    WHERE s.module_id = %s {source_filter}
                      AND c.search_vector IS NOT NULL
                      AND c.search_vector @@ (regexp_replace(plainto_tsquery('german', %s)::text, ' & ', ' | ', 'g'))::tsquery
                    LIMIT 40""",
                [query_text, module_id] + source_param + [query_text],
            )
            kw_rows = cur.fetchall()
            kw_pages = sorted(set(r["page_number"] for r in kw_rows))
            logger.info("Hybrid Keyword: {} hits, Seiten: {}", len(kw_rows), kw_pages)

            # 2b) Exact substring fallback (catches proper names / non-German terms)
            _stop = {"der","die","das","ein","eine","und","oder","ist","hat","war","wer","was","wie","wo",
                      "mit","von","für","auf","aus","bei","den","dem","des","als","nach","über","vor","bis",
                      "wenn","dass","aber","auch","noch","nur","doch","sehr","wird","sind","kann","mehr",
                      "nicht","sich","gibt","diese","einer","einem","einen","welche","welcher","welches"}
            words = [w for w in query_text.split() if len(w) >= 2 and w.lower() not in _stop]
            if words:
                ilike_clauses = " AND ".join(["c.content ILIKE %s"] * len(words))
                ilike_params = [f"%{w}%" for w in words]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY c.id
                        ) AS rank
                        FROM ki_tutor_chunks c
                        JOIN ki_tutor_sources s ON s.id = c.source_id
                        WHERE s.module_id = %s {source_filter}
                          AND {ilike_clauses}
                        LIMIT 20""",
                    [module_id] + source_param + ilike_params,
                )
                ilike_rows = cur.fetchall()
                if ilike_rows:
                    ilike_pages = sorted(set(r["page_number"] for r in ilike_rows))
                    logger.info("Hybrid ILIKE: {} hits, Seiten: {}", len(ilike_rows), ilike_pages)
                    kw_rows = kw_rows + ilike_rows

            # 3) RRF fusion
            scores: dict[int, float] = {}
            for row in vec_rows:
                scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
            for row in kw_rows:
                scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])

            if not scores:
                return []

            # Fetch full chunk data for top results
            top_ids = sorted(scores, key=lambda i: scores[i], reverse=True)[:limit]
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM ki_tutor_chunks WHERE id = ANY(%s)""",
                (top_ids,),
            )
            chunk_map = {r["id"]: dict(r) for r in cur.fetchall()}

            # Return in score order
            results = []
            for cid in top_ids:
                if cid in chunk_map:
                    chunk = chunk_map[cid]
                    chunk["hybrid_score"] = scores[cid]
                    results.append(chunk)

            rrf_pages = sorted(set(c["page_number"] for c in results))
            logger.info("Hybrid RRF: {} final chunks, Seiten: {}", len(results), rrf_pages)

    return results


# --- KI Tutor: Messages ---

def save_ki_tutor_message(
    module_id: int,
    user_id: int,
    role: str,
    content: str,
    source_pages: list | dict | None = None,
    enrollment_id: int | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_messages
                   (module_id, user_id, role, content, source_pages, enrollment_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    module_id,
                    user_id,
                    role,
                    content,
                    json.dumps(source_pages) if source_pages is not None else None,
                    enrollment_id,
                ),
            )
        conn.commit()


def delete_ki_tutor_messages(module_id: int, user_id: int, enrollment_id: int | None = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if enrollment_id is not None:
                cur.execute(
                    "DELETE FROM ki_tutor_messages WHERE module_id = %s AND user_id = %s AND enrollment_id = %s",
                    (module_id, user_id, enrollment_id),
                )
            else:
                cur.execute(
                    "DELETE FROM ki_tutor_messages WHERE module_id = %s AND user_id = %s AND enrollment_id IS NULL",
                    (module_id, user_id),
                )
        conn.commit()


def get_ki_tutor_messages(
    module_id: int, user_id: int, limit: int = 20, enrollment_id: int | None = None
) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            if enrollment_id is not None:
                cur.execute(
                    """SELECT * FROM ki_tutor_messages
                       WHERE module_id = %s AND user_id = %s AND enrollment_id = %s
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (module_id, user_id, enrollment_id, limit),
                )
            else:
                cur.execute(
                    """SELECT * FROM ki_tutor_messages
                       WHERE module_id = %s AND user_id = %s AND enrollment_id IS NULL
                       ORDER BY created_at DESC
                       LIMIT %s""",
                    (module_id, user_id, limit),
                )
            rows = cur.fetchall()
    return list(reversed([dict(row) for row in rows]))


def get_ki_tutor_user_settings(module_id: int, user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_user_settings WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
    if row:
        return dict(row)
    return {"chat_lang": "de", "studio_enabled": True, "sprachtraining_active": False}


def upsert_ki_tutor_user_settings(
    module_id: int, user_id: int, chat_lang: str, studio_enabled: bool, sprachtraining_active: bool
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_user_settings (module_id, user_id, chat_lang, studio_enabled, sprachtraining_active)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (module_id, user_id)
                   DO UPDATE SET chat_lang = EXCLUDED.chat_lang,
                                 studio_enabled = EXCLUDED.studio_enabled,
                                 sprachtraining_active = EXCLUDED.sprachtraining_active""",
                (module_id, user_id, chat_lang, studio_enabled, sprachtraining_active),
            )
        conn.commit()


# --- KI Tutor: Notes ---

def get_ki_tutor_notes(module_id: int, user_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, content, created_at FROM ki_tutor_notes WHERE module_id = %s AND user_id = %s ORDER BY created_at DESC",
                (module_id, user_id),
            )
            return [dict(r) for r in cur.fetchall()]


def create_ki_tutor_note(module_id: int, user_id: int, content: str) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO ki_tutor_notes (module_id, user_id, content) VALUES (%s, %s, %s) RETURNING id, content, created_at",
                (module_id, user_id, content),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row


def delete_ki_tutor_note(note_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ki_tutor_notes WHERE id = %s AND user_id = %s",
                (note_id, user_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted


# --- KI Tutor: Paragraph Summaries ---

def update_ki_tutor_source_summaries_status(uuid: str, status: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_sources SET summaries_status = %s WHERE uuid = %s",
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
                f"""INSERT INTO ki_tutor_paragraph_summaries
                    (source_id, page_number, block_index, bbox_x0, bbox_y0, bbox_x1, bbox_y1, content, summary)
                    VALUES {', '.join(values)}""",
                params,
            )
        conn.commit()


def delete_paragraph_summaries_by_source(source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ki_tutor_paragraph_summaries WHERE source_id = %s",
                (source_id,),
            )
        conn.commit()


def get_paragraph_summaries_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_paragraph_summaries
                   WHERE source_id = %s
                   ORDER BY page_number, block_index""",
                (source_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


# --- KI Tutor: Mindmaps ---

def create_ki_tutor_mindmap(module_id: int, user_id: int, source_ids: list[int]) -> int:
    """Create a pending mindmap record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_mindmaps (module_id, user_id, source_ids, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, _json.dumps(source_ids)),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def update_ki_tutor_mindmap(mindmap_id: int, status: str, mindmap: dict | None = None, error: str | None = None) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_mindmaps
                   SET status = %s, mindmap = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, _json.dumps(mindmap) if mindmap else None, error, mindmap_id),
            )
        conn.commit()


def get_ki_tutor_mindmap(mindmap_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_mindmaps WHERE id = %s", (mindmap_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_latest_ki_tutor_mindmap(module_id: int, user_id: int) -> dict | None:
    """Get the most recent mindmap for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_mindmaps
                   WHERE module_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_all_ki_tutor_mindmaps(module_id: int, user_id: int) -> list[dict]:
    """Get all successful mindmaps for a module/user, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, created_at, mindmap
                   FROM ki_tutor_mindmaps
                   WHERE module_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def delete_ki_tutor_mindmap(mindmap_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_mindmaps WHERE id = %s", (mindmap_id,))
        conn.commit()


# --- KI Tutor: Presentations ---

def create_ki_tutor_presentation(module_id: int, user_id: int, source_id: int) -> int:
    """Create a pending presentation record, return its id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_presentations (module_id, user_id, source_id, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, source_id),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def update_ki_tutor_presentation(
    presentation_id: int,
    status: str,
    title: str | None = None,
    slides: list | None = None,
    pptx_path: str | None = None,
    presenton_id: str | None = None,
    error: str | None = None,
) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_presentations
                   SET status = %s, title = %s, slides = %s, pptx_path = %s,
                       presenton_id = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, title, _json.dumps(slides) if slides else None, pptx_path,
                 presenton_id, error, presentation_id),
            )
        conn.commit()


def get_ki_tutor_presentation(presentation_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_presentations WHERE id = %s", (presentation_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_latest_ki_tutor_presentation(module_id: int, user_id: int, source_id: int) -> dict | None:
    """Get the most recent presentation for a module/user/source."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_presentations
                   WHERE module_id = %s AND user_id = %s AND source_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id, source_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_presentations_by_module(module_id: int, user_id: int) -> list[dict]:
    """Get all presentations for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT p.*, s.filename as source_filename
                   FROM ki_tutor_presentations p
                   JOIN ki_tutor_sources s ON s.id = p.source_id
                   WHERE p.module_id = %s AND p.user_id = %s
                   ORDER BY p.created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def delete_ki_tutor_presentation(presentation_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_presentations WHERE id = %s", (presentation_id,))
        conn.commit()


# --- KI Tutor: Infographics ---

def create_ki_tutor_infographic(module_id: int, user_id: int, source_ids: list[int], style: str = "professional") -> int:
    """Create a pending infographic record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_infographics (module_id, user_id, source_ids, style, status)
                   VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, _json.dumps(source_ids), style),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def update_ki_tutor_infographic(
    infographic_id: int,
    status: str,
    title: str | None = None,
    layout_data: dict | None = None,
    error: str | None = None,
) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_infographics
                   SET status = %s, title = %s, layout_data = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, title, _json.dumps(layout_data) if layout_data else None, error, infographic_id),
            )
        conn.commit()


def get_ki_tutor_infographic(infographic_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_infographics WHERE id = %s", (infographic_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_latest_ki_tutor_infographic(module_id: int, user_id: int) -> dict | None:
    """Get the most recent infographic for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_infographics
                   WHERE module_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_infographics_by_module(module_id: int, user_id: int) -> list[dict]:
    """Get all successful infographics for a module/user (without image_data for listing)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, title, style, created_at
                   FROM ki_tutor_infographics
                   WHERE module_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def delete_ki_tutor_infographic(infographic_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_infographics WHERE id = %s", (infographic_id,))
        conn.commit()


# --- KI Tutor: Datentabellen ---

def create_ki_tutor_datentabelle(module_id: int, user_id: int, source_ids: list[int]) -> int:
    """Create a pending datentabelle record, return its id."""
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_datentabellen (module_id, user_id, source_ids, status)
                   VALUES (%s, %s, %s, 'pending') RETURNING id""",
                (module_id, user_id, _json.dumps(source_ids)),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def update_ki_tutor_datentabelle(
    datentabelle_id: int,
    status: str,
    title: str | None = None,
    table_data: dict | None = None,
    sources: list | None = None,
    error: str | None = None,
) -> None:
    import json as _json
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ki_tutor_datentabellen
                   SET status = %s, title = %s, table_data = %s, sources = %s, error = %s, updated_at = NOW()
                   WHERE id = %s""",
                (status, title,
                 _json.dumps(table_data) if table_data else None,
                 _json.dumps(sources) if sources else None,
                 error, datentabelle_id),
            )
        conn.commit()


def get_ki_tutor_datentabelle(datentabelle_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_datentabellen WHERE id = %s", (datentabelle_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_latest_ki_tutor_datentabelle(module_id: int, user_id: int) -> dict | None:
    """Get the most recent datentabelle for a module/user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT * FROM ki_tutor_datentabellen
                   WHERE module_id = %s AND user_id = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (module_id, user_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def get_ki_tutor_datentabellen_by_module(module_id: int, user_id: int) -> list[dict]:
    """Get all successful datentabellen for a module/user (without table_data for listing)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, status, title, sources, created_at
                   FROM ki_tutor_datentabellen
                   WHERE module_id = %s AND user_id = %s AND status = 'success'
                   ORDER BY created_at DESC""",
                (module_id, user_id),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def delete_ki_tutor_datentabelle(datentabelle_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_datentabellen WHERE id = %s", (datentabelle_id,))
        conn.commit()


# --- KI Tutor: Chunks by Source ---

def get_chunks_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, page_number, content, start_time, end_time
                   FROM ki_tutor_chunks
                   WHERE source_id = %s
                   ORDER BY page_number, id""",
                (source_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- KI Tutor: Glossary ---

def get_ki_tutor_glossary(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, term_de, term_en, definition, definition_en, example_sentence, example_sentence_en, page_number
                   FROM ki_tutor_glossary_entries
                   WHERE source_id = %s ORDER BY term_de""",
                (source_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_ki_tutor_glossary_by_module(module_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT g.id, g.term_de, g.term_en, g.definition, g.definition_en, g.example_sentence, g.example_sentence_en, g.page_number,
                          s.filename
                   FROM ki_tutor_glossary_entries g
                   JOIN ki_tutor_sources s ON s.id = g.source_id
                   WHERE s.module_id = %s
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
                f"""INSERT INTO ki_tutor_glossary_entries
                    (source_id, term_de, term_en, definition, definition_en, example_sentence, example_sentence_en, page_number)
                    VALUES {', '.join(values)}
                    RETURNING id, term_de, term_en, definition, definition_en, example_sentence, example_sentence_en, page_number""",
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
        return rows


def delete_ki_tutor_glossary(source_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_glossary_entries WHERE source_id = %s", (source_id,))
        conn.commit()


def delete_all_glossary_entries(module_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM ki_tutor_glossary_entries
                   WHERE source_id IN (SELECT id FROM ki_tutor_sources WHERE module_id = %s)""",
                (module_id,),
            )
            count = cur.rowcount
        conn.commit()
    return count


def delete_glossary_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_glossary_entries WHERE id = %s RETURNING id", (entry_id,))
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted


# ─── Exercise Sets ────────────────────────────────────────────────────────────


def create_exercise_set(
    module_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None, items: list[dict],
) -> dict:
    """Create an exercise set with its items. Returns the set with items."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_sets
                   (module_id, user_id, tool, title, mode, source_uuid, card_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready') RETURNING *""",
                (module_id, user_id, tool, title, mode, source_uuid, len(items)),
            )
            ex_set = dict(cur.fetchone())
            created_items = []
            for i, item in enumerate(items):
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                    (
                        ex_set["id"], i,
                        item["front"], item["back"], item.get("back_en"),
                        json.dumps(item.get("options")) if item.get("options") else None,
                        item.get("correct_idx"),
                        item.get("source_label"),
                        item.get("page_number"),
                        item.get("explanation"),
                        item.get("start_time"),
                    ),
                )
                created_items.append(dict(cur.fetchone()))
        conn.commit()
    ex_set["items"] = created_items
    return ex_set


def create_exercise_set_placeholder(
    module_id: int, user_id: int, tool: str, title: str,
    mode: str, source_uuid: str | None,
) -> dict:
    """Create a placeholder set with status='generating'. Returns the set."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_sets
                   (module_id, user_id, tool, title, mode, source_uuid, card_count, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 'generating') RETURNING *""",
                (module_id, user_id, tool, title, mode, source_uuid),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set


def finalize_exercise_set(set_id: int, title: str, items: list[dict]) -> dict:
    """Add items to a placeholder set and mark as ready."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i, item in enumerate(items):
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_items
                       (set_id, position, front, back, back_en, options, correct_idx,
                        source_label, page_number, explanation, start_time)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        set_id, i,
                        item["front"], item["back"], item.get("back_en"),
                        json.dumps(item.get("options")) if item.get("options") else None,
                        item.get("correct_idx"),
                        item.get("source_label"),
                        item.get("page_number"),
                        item.get("explanation"),
                        item.get("start_time"),
                    ),
                )
            cur.execute(
                """UPDATE ki_tutor_exercise_sets
                   SET status = 'ready', title = %s, card_count = %s
                   WHERE id = %s RETURNING *""",
                (title, len(items), set_id),
            )
            ex_set = dict(cur.fetchone())
        conn.commit()
    return ex_set


def fail_exercise_set(set_id: int) -> None:
    """Mark a set as failed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_exercise_sets SET status = 'failed' WHERE id = %s",
                (set_id,),
            )
        conn.commit()


def get_exercise_sets(module_id: int, user_id: int, tool: str | None = None) -> list[dict]:
    """List exercise sets for a user in a module with mastery info."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = "s.module_id = %s AND s.user_id = %s"
            params: list = [module_id, user_id]
            if tool:
                where += " AND s.tool = %s"
                params.append(tool)
            cur.execute(
                f"""SELECT s.*,
                           COALESCE(m.total_attempts, 0) AS total_attempts,
                           COALESCE(m.items_correct, 0) AS items_correct,
                           CASE WHEN s.card_count > 0
                                THEN ROUND(COALESCE(m.items_correct, 0)::numeric / s.card_count * 100)
                                ELSE 0 END AS progress_pct,
                           COALESCE(lr.last_run_correct, 0) AS last_run_correct
                    FROM ki_tutor_exercise_sets s
                    LEFT JOIN LATERAL (
                      SELECT COUNT(*) AS total_attempts,
                             COUNT(DISTINCT item_id) FILTER (WHERE correct) AS items_correct
                      FROM ki_tutor_exercise_progress p
                      WHERE p.set_id = s.id AND p.user_id = s.user_id
                    ) m ON true
                    LEFT JOIN LATERAL (
                      SELECT COUNT(DISTINCT item_id) FILTER (WHERE correct) AS last_run_correct
                      FROM ki_tutor_exercise_progress p
                      WHERE p.set_id = s.id AND p.user_id = s.user_id
                        AND s.last_run_start IS NOT NULL
                        AND p.answered_at >= s.last_run_start
                    ) lr ON true
                    WHERE {where}
                    ORDER BY s.created_at DESC""",
                params,
            )
            return [dict(r) for r in cur.fetchall()]


def get_exercise_set_with_items(set_id: int) -> dict | None:
    """Get a single set with all its items, enriching with chunk start_time where missing."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM ki_tutor_exercise_sets WHERE id = %s", (set_id,))
            ex_set = cur.fetchone()
            if not ex_set:
                return None
            ex_set = dict(ex_set)
            cur.execute(
                "SELECT * FROM ki_tutor_exercise_items WHERE set_id = %s ORDER BY position",
                (set_id,),
            )
            items = [dict(r) for r in cur.fetchall()]

            # Enrich items that have page_number but no start_time
            needs_time = [it for it in items if it.get("page_number") and it.get("start_time") is None and it.get("source_label")]
            if needs_time:
                # Build lookup: filename → source_id
                module_id = ex_set["module_id"]
                cur.execute("SELECT id, filename FROM ki_tutor_sources WHERE module_id = %s", (module_id,))
                src_map = {r["filename"]: r["id"] for r in cur.fetchall()}
                # Build lookup: (source_id, page_number) → start_time
                source_ids = list(src_map.values())
                if source_ids:
                    cur.execute(
                        "SELECT source_id, page_number, start_time FROM ki_tutor_chunks "
                        "WHERE source_id = ANY(%s) AND start_time IS NOT NULL",
                        (source_ids,),
                    )
                    time_map = {(r["source_id"], r["page_number"]): r["start_time"] for r in cur.fetchall()}
                    for it in needs_time:
                        sid = src_map.get(it["source_label"])
                        if sid:
                            st = time_map.get((sid, it["page_number"]))
                            if st is not None:
                                it["start_time"] = st

            ex_set["items"] = items
            return ex_set


def delete_exercise_set(set_id: int) -> bool:
    """Delete an exercise set and all related data."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ki_tutor_exercise_sets WHERE id = %s RETURNING id", (set_id,))
            deleted = cur.fetchone() is not None
        conn.commit()
    return deleted


def record_exercise_progress(set_id: int, item_id: int, user_id: int, correct: bool) -> None:
    """Record a single exercise answer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ki_tutor_exercise_progress
                   (set_id, item_id, user_id, correct) VALUES (%s, %s, %s, %s)""",
                (set_id, item_id, user_id, correct),
            )
        conn.commit()


def start_new_run(set_id: int) -> None:
    """Mark the start of a new exercise run."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ki_tutor_exercise_sets SET last_run_start = NOW() WHERE id = %s",
                (set_id,),
            )
        conn.commit()


def bulk_record_exercise_progress(set_id: int, user_id: int, results: list[dict]) -> None:
    """Record multiple exercise answers at once."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for r in results:
                cur.execute(
                    """INSERT INTO ki_tutor_exercise_progress
                       (set_id, item_id, user_id, correct) VALUES (%s, %s, %s, %s)""",
                    (set_id, r["item_id"], user_id, r["correct"]),
                )
        conn.commit()


# ─── Streak Tracking ──────────────────────────────────────────────────────────


def update_streak(module_id: int, user_id: int) -> dict:
    """Update streak for today (Berlin timezone). Returns current and max streak."""
    from datetime import timedelta, datetime
    today = datetime.now(_TZ_BERLIN).date()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_streaks WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    """INSERT INTO ki_tutor_streaks
                       (module_id, user_id, current_streak, max_streak, last_active_date)
                       VALUES (%s, %s, 1, 1, %s) RETURNING *""",
                    (module_id, user_id, today),
                )
                result = dict(cur.fetchone())
            else:
                row = dict(row)
                last = row["last_active_date"]
                if last == today:
                    result = row
                elif last == today - timedelta(days=1):
                    new_streak = row["current_streak"] + 1
                    new_max = max(row["max_streak"], new_streak)
                    cur.execute(
                        """UPDATE ki_tutor_streaks
                           SET current_streak = %s, max_streak = %s, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (new_streak, new_max, today, row["id"]),
                    )
                    result = dict(cur.fetchone())
                else:
                    cur.execute(
                        """UPDATE ki_tutor_streaks
                           SET current_streak = 1, last_active_date = %s
                           WHERE id = %s RETURNING *""",
                        (today, row["id"]),
                    )
                    result = dict(cur.fetchone())
        conn.commit()
    return result


def get_streak(module_id: int, user_id: int) -> dict:
    """Get current streak info."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM ki_tutor_streaks WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return {"current_streak": 0, "max_streak": 0, "last_active_date": None}
            return dict(row)


def get_glossary_count(module_id: int) -> int:
    """Get total glossary entry count for a module."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM ki_tutor_glossary_entries g
                   JOIN ki_tutor_sources s ON s.id = g.source_id
                   WHERE s.module_id = %s""",
                (module_id,),
            )
            return cur.fetchone()[0]


def get_student_stats(module_id: int, user_id: int) -> dict:
    """Aggregate personal learning stats for a student in a module."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Berlin")

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ── Streak ──
            cur.execute(
                "SELECT current_streak, max_streak, last_active_date "
                "FROM ki_tutor_streaks WHERE module_id = %s AND user_id = %s",
                (module_id, user_id),
            )
            streak_row = cur.fetchone()
            streak = dict(streak_row) if streak_row else {
                "current_streak": 0, "max_streak": 0, "last_active_date": None,
            }
            if streak["last_active_date"]:
                streak["last_active_date"] = str(streak["last_active_date"])

            # ── All exercise sets ──
            cur.execute(
                """SELECT s.id, s.tool, s.mode, s.title, s.card_count,
                          s.source_uuid, s.created_at,
                          COALESCE(m.total_attempts, 0) AS total_attempts,
                          COALESCE(m.total_correct, 0) AS total_correct
                   FROM ki_tutor_exercise_sets s
                   LEFT JOIN LATERAL (
                     SELECT COUNT(*) AS total_attempts,
                            COUNT(*) FILTER (WHERE p.correct) AS total_correct
                     FROM ki_tutor_exercise_progress p
                     WHERE p.set_id = s.id AND p.user_id = s.user_id
                   ) m ON true
                   WHERE s.module_id = %s AND s.user_id = %s AND s.status = 'ready'
                   ORDER BY s.created_at DESC""",
                (module_id, user_id),
            )
            sets = [dict(r) for r in cur.fetchall()]

            # ── Split by category: Lerntools (mode=quelle) vs Sprachtraining (mode=glossar) ──
            def _summarise(subset: list[dict]) -> dict:
                total_cards = sum(s["card_count"] for s in subset)
                total_attempts = sum(s["total_attempts"] for s in subset)
                total_correct = sum(s["total_correct"] for s in subset)
                return {
                    "total_sets": len(subset),
                    "total_cards": total_cards,
                    "total_attempts": total_attempts,
                    "total_correct": total_correct,
                    "accuracy": round(total_correct / total_attempts * 100) if total_attempts > 0 else 0,
                }

            lerntools_sets = [s for s in sets if s["mode"] == "quelle"]
            sprach_sets = [s for s in sets if s["mode"] == "glossar"]

            overview_all = _summarise(sets)
            overview_lerntools = _summarise(lerntools_sets)
            overview_sprach = _summarise(sprach_sets)

            # (by_tool removed — not displayed anymore)

            # ── Heatmap: activity per day per category (last 6 months, Berlin tz) ──
            from datetime import date, timedelta, datetime
            today = datetime.now(tz).date()

            def _build_heatmap(mode_filter: str | None) -> list[dict]:
                mode_clause = ""
                params: list = [user_id, module_id, user_id]
                if mode_filter:
                    mode_clause = " AND s2.mode = %s"
                    params.append(mode_filter)
                cur.execute(
                    f"""SELECT (ep.answered_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date AS day,
                              COUNT(ep.id) AS answers,
                              COUNT(ep.id) FILTER (WHERE ep.correct) AS correct,
                              COUNT(ep.id) FILTER (WHERE NOT ep.correct) AS wrong,
                              COUNT(DISTINCT ep.set_id) AS sets_practiced
                       FROM ki_tutor_exercise_progress ep
                       JOIN ki_tutor_exercise_sets s2 ON s2.id = ep.set_id
                       WHERE ep.user_id = %s
                         AND s2.module_id = %s AND s2.user_id = %s
                         {mode_clause}
                         AND ep.answered_at >= (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date - INTERVAL '179 days'
                       GROUP BY day ORDER BY day""",
                    params,
                )
                raw = {str(r["day"]): dict(r) for r in cur.fetchall()}
                result = []
                for i in range(179, -1, -1):
                    d = today - timedelta(days=i)
                    ds = str(d)
                    if ds in raw:
                        r = raw[ds]
                        result.append({
                            "day": ds,
                            "answers": r["answers"],
                            "correct": r["correct"],
                            "wrong": r["wrong"],
                            "sets_practiced": r["sets_practiced"],
                        })
                    else:
                        result.append({
                            "day": ds, "answers": 0, "correct": 0,
                            "wrong": 0, "sets_practiced": 0,
                        })
                return result

            heatmap = _build_heatmap(None)
            heatmap_lerntools = _build_heatmap("quelle")
            heatmap_sprachtraining = _build_heatmap("glossar")

            # ── Chat stats ──
            cur.execute(
                """SELECT COUNT(*) AS total,
                          COUNT(*) FILTER (
                            WHERE created_at >= (NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date
                          ) AS today
                   FROM ki_tutor_messages
                   WHERE module_id = %s AND user_id = %s AND role = 'user'""",
                (module_id, user_id),
            )
            chat_row = cur.fetchone()

            # ── First activity date ──
            cur.execute(
                """SELECT MIN(answered_at) AS first_activity
                   FROM ki_tutor_exercise_progress ep
                   JOIN ki_tutor_exercise_sets s ON s.id = ep.set_id
                   WHERE s.module_id = %s AND ep.user_id = %s""",
                (module_id, user_id),
            )
            first_row = cur.fetchone()
            first_activity = str(first_row["first_activity"].date()) if first_row and first_row["first_activity"] else None

            # ── Total active days ──
            active_days = sum(1 for d in heatmap if d["answers"] > 0)

    return {
        "streak": streak,
        "overview": overview_all,
        "lerntools": overview_lerntools,
        "sprachtraining": overview_sprach,
        "heatmap": heatmap,
        "lerntools_heatmap": heatmap_lerntools,
        "sprachtraining_heatmap": heatmap_sprachtraining,
        "chat": {"total": chat_row["total"], "today": chat_row["today"]},
        "first_activity": first_activity,
        "active_days": active_days,
        "today": str(today),
    }


def get_student_day_stats(module_id: int, user_id: int, day_str: str, category: str | None = None) -> dict:
    """Per-set breakdown for a specific day, optionally filtered by category."""
    mode_filter = None
    if category == "lerntools":
        mode_filter = "quelle"
    elif category == "sprachtraining":
        mode_filter = "glossar"

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            mode_clause = ""
            params: list = [module_id, user_id, day_str]
            if mode_filter:
                mode_clause = " AND s.mode = %s"
                params.append(mode_filter)
            cur.execute(
                f"""SELECT s.id AS set_id, s.tool, s.mode, s.title,
                          COUNT(ep.id) AS answers,
                          COUNT(ep.id) FILTER (WHERE ep.correct) AS correct,
                          COUNT(ep.id) FILTER (WHERE NOT ep.correct) AS wrong,
                          MIN(ep.answered_at) AS first_answer,
                          MAX(ep.answered_at) AS last_answer
                   FROM ki_tutor_exercise_progress ep
                   JOIN ki_tutor_exercise_sets s ON s.id = ep.set_id
                   WHERE s.module_id = %s AND ep.user_id = %s
                     AND (ep.answered_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date = %s::date
                     {mode_clause}
                   GROUP BY s.id ORDER BY MIN(ep.answered_at)""",
                params,
            )
            sets = []
            total_answers = 0
            total_correct = 0
            total_wrong = 0
            for r in cur.fetchall():
                row = dict(r)
                row["first_answer"] = (row["first_answer"].isoformat() + "Z") if row["first_answer"] else None
                row["last_answer"] = (row["last_answer"].isoformat() + "Z") if row["last_answer"] else None
                total_answers += row["answers"]
                total_correct += row["correct"]
                total_wrong += row["wrong"]
                sets.append(row)

            # Chat messages that day
            cur.execute(
                """SELECT COUNT(*) AS cnt
                   FROM ki_tutor_messages
                   WHERE module_id = %s AND user_id = %s AND role = 'user'
                     AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date = %s::date""",
                (module_id, user_id, day_str),
            )
            chat_count = cur.fetchone()["cnt"]

    return {
        "day": day_str,
        "sets": sets,
        "total_answers": total_answers,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "chat_count": chat_count,
    }


# ─── Admin: KI-Tutor Statistics ──────────────────────────────────────────────


def get_ki_tutor_admin_stats(days: int = 30, mode: str | None = None) -> dict:
    """Aggregated KI-Tutor statistics for the admin dashboard.

    mode: None = all, "quelle" = Lerntools only, "glossar" = Sprachtraining only.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            interval = f"{days} days"

            # Mode filter for exercise queries (requires JOIN with ki_tutor_exercise_sets as s)
            mode_filter = ""
            mode_params: tuple = ()
            if mode in ("quelle", "glossar"):
                mode_filter = " AND s.mode = %s"
                mode_params = (mode,)

            # ── 1. Summary ──
            cur.execute("SELECT COUNT(*) AS cnt FROM ki_tutor_modules")
            total_modules = cur.fetchone()["cnt"]

            cur.execute(
                f"""SELECT COUNT(DISTINCT p.user_id) AS cnt
                    FROM ki_tutor_exercise_progress p
                    JOIN ki_tutor_exercise_sets s ON s.id = p.set_id
                    WHERE p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                (interval, *mode_params),
            )
            active_students = cur.fetchone()["cnt"]

            cur.execute(
                f"""SELECT COUNT(*) AS cnt
                    FROM ki_tutor_exercise_progress p
                    JOIN ki_tutor_exercise_sets s ON s.id = p.set_id
                    WHERE p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                (interval, *mode_params),
            )
            total_answers = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT COUNT(*) AS cnt FROM ki_tutor_messages
                   WHERE role = 'user' AND created_at >= NOW() - INTERVAL %s""",
                (interval,),
            )
            total_chat_messages = cur.fetchone()["cnt"]

            # ── 2. Module list with dozent activity + enrolled students ──
            cur.execute(
                """SELECT m.id, m.uuid, m.title, m.is_active, m.user_id AS owner_id,
                          u.display_name AS owner_name, u.ldap_username AS owner_username,
                          (SELECT COUNT(*) FROM ki_tutor_enrollments e WHERE e.module_id = m.id) AS enrollment_count,
                          (SELECT COUNT(DISTINCT src.id) FROM ki_tutor_sources src WHERE src.module_id = m.id) AS source_count
                   FROM ki_tutor_modules m
                   JOIN users u ON m.user_id = u.id
                   ORDER BY m.created_at DESC""",
            )
            modules_raw = [dict(r) for r in cur.fetchall()]

            module_stats = []
            for m in modules_raw:
                mid = m["id"]
                owner_id = m["owner_id"]
                owner = m["owner_name"] or m["owner_username"] or "Unbekannt"

                # Dozent activity: chat messages sent by owner in this module
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM ki_tutor_messages
                       WHERE module_id = %s AND user_id = %s AND role = 'user'
                         AND created_at >= NOW() - INTERVAL %s""",
                    (mid, owner_id, interval),
                )
                dozent_messages = cur.fetchone()["cnt"]

                # Dozent activity: exercises answered by owner
                cur.execute(
                    f"""SELECT COUNT(p.id) AS attempts,
                               COUNT(p.id) FILTER (WHERE p.correct) AS correct_cnt
                        FROM ki_tutor_exercise_progress p
                        JOIN ki_tutor_exercise_sets s ON s.id = p.set_id
                        WHERE s.module_id = %s AND p.user_id = %s
                          AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                    (mid, owner_id, interval, *mode_params),
                )
                dozent_ex = cur.fetchone()

                # Total module exercise stats
                cur.execute(
                    f"""SELECT COUNT(p.id) AS total_answers,
                               COUNT(p.id) FILTER (WHERE p.correct) AS total_correct
                        FROM ki_tutor_exercise_progress p
                        JOIN ki_tutor_exercise_sets s ON s.id = p.set_id
                        WHERE s.module_id = %s AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                    (mid, interval, *mode_params),
                )
                ex_row = cur.fetchone()

                # Total chat in module
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM ki_tutor_messages
                       WHERE module_id = %s AND role = 'user'
                         AND created_at >= NOW() - INTERVAL %s""",
                    (mid, interval),
                )
                chat_cnt = cur.fetchone()["cnt"]

                # Enrolled students with their individual stats
                cur.execute(
                    """SELECT DISTINCT u.id AS user_id,
                              u.display_name, u.ldap_username
                       FROM ki_tutor_enrollments e
                       JOIN users u ON e.user_id = u.id
                       WHERE e.module_id = %s
                       ORDER BY u.display_name""",
                    (mid,),
                )
                enrolled = [dict(r) for r in cur.fetchall()]

                students = []
                for st in enrolled:
                    sid = st["user_id"]
                    # Student exercises in this module
                    cur.execute(
                        f"""SELECT COUNT(p.id) AS answers,
                                   COUNT(p.id) FILTER (WHERE p.correct) AS correct_cnt,
                                   COUNT(p.id) FILTER (WHERE s.mode = 'quelle') AS lerntools,
                                   COUNT(p.id) FILTER (WHERE s.mode = 'glossar') AS sprachtraining
                            FROM ki_tutor_exercise_progress p
                            JOIN ki_tutor_exercise_sets s ON s.id = p.set_id
                            WHERE s.module_id = %s AND p.user_id = %s
                              AND p.answered_at >= NOW() - INTERVAL %s{mode_filter}""",
                        (mid, sid, interval, *mode_params),
                    )
                    st_ex = cur.fetchone()

                    # Student chat messages in this module
                    cur.execute(
                        """SELECT COUNT(*) AS cnt FROM ki_tutor_messages
                           WHERE module_id = %s AND user_id = %s AND role = 'user'
                             AND created_at >= NOW() - INTERVAL %s""",
                        (mid, sid, interval),
                    )
                    st_chat = cur.fetchone()["cnt"]

                    students.append({
                        "name": st["display_name"] or st["ldap_username"] or "Unbekannt",
                        "answers": st_ex["answers"],
                        "correct": st_ex["correct_cnt"],
                        "accuracy": round(st_ex["correct_cnt"] / st_ex["answers"] * 100) if st_ex["answers"] > 0 else 0,
                        "lerntools": st_ex["lerntools"],
                        "sprachtraining": st_ex["sprachtraining"],
                        "chat_messages": st_chat,
                    })

                module_stats.append({
                    "module_uuid": m["uuid"],
                    "title": m["title"],
                    "owner": owner,
                    "is_active": m["is_active"],
                    "source_count": m["source_count"],
                    "enrollment_count": m["enrollment_count"],
                    "total_answers": ex_row["total_answers"],
                    "accuracy": round(ex_row["total_correct"] / ex_row["total_answers"] * 100) if ex_row["total_answers"] > 0 else 0,
                    "chat_messages": chat_cnt,
                    "dozent": {
                        "messages": dozent_messages,
                        "exercises": dozent_ex["attempts"],
                    },
                    "students": students,
                })

    return {
        "summary": {
            "total_modules": total_modules,
            "active_students": active_students,
            "total_answers": total_answers,
            "total_chat_messages": total_chat_messages,
        },
        "module_stats": module_stats,
        "days": days,
        "mode": mode,
    }


# ─── Dozent: Module Statistics ──────────────────────────────────────────────


def get_ki_tutor_module_stats(module_id: int) -> dict:
    """Statistics for a single module – used by the module owner (Dozent)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT user_id) AS cnt FROM ki_tutor_enrollments WHERE module_id = %s",
                (module_id,),
            )
            total_enrolled = cur.fetchone()["cnt"]

            cur.execute(
                """SELECT COUNT(DISTINCT user_id) AS cnt
                   FROM ki_tutor_messages
                   WHERE module_id = %s AND role = 'user'
                     AND created_at >= NOW() - INTERVAL '30 days'""",
                (module_id,),
            )
            active_30d = cur.fetchone()["cnt"]

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM ki_tutor_messages WHERE module_id = %s AND role = 'user'",
                (module_id,),
            )
            total_chat = cur.fetchone()["cnt"]

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM ki_tutor_exercise_sets WHERE module_id = %s",
                (module_id,),
            )
            total_sets = cur.fetchone()["cnt"]

    return {
        "overview": {
            "total_enrolled": total_enrolled,
            "active_30d": active_30d,
            "total_chat_messages": total_chat,
            "total_exercise_sets": total_sets,
        },
    }
