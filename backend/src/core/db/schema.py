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


def init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Migration: rename legacy ki_tutor_* tables -> kia_* (no-op on fresh DBs)
            for old, new in [
                ("ki_tutor_modules", "kia_modules"),
                ("ki_tutor_access_links", "kia_access_links"),
                ("ki_tutor_enrollments", "kia_enrollments"),
                ("ki_tutor_sources", "kia_sources"),
                ("ki_tutor_chunks", "kia_chunks"),
                ("ki_tutor_paragraph_summaries", "kia_paragraph_summaries"),
                ("ki_tutor_mindmaps", "kia_mindmaps"),
                ("ki_tutor_datentabellen", "kia_datentabellen"),
                ("ki_tutor_messages", "kia_messages"),
                ("ki_tutor_user_settings", "kia_user_settings"),
                ("ki_tutor_notes", "kia_notes"),
                ("ki_tutor_glossary_entries", "kia_glossary_entries"),
                ("ki_tutor_exercise_sets", "kia_exercise_sets"),
                ("ki_tutor_exercise_items", "kia_exercise_items"),
                ("ki_tutor_exercise_progress", "kia_exercise_progress"),
                ("ki_tutor_streaks", "kia_streaks"),
            ]:
                cur.execute(
                    "SELECT to_regclass(%s) IS NOT NULL AND to_regclass(%s) IS NULL",
                    (f"public.{old}", f"public.{new}"),
                )
                if cur.fetchone()[0]:
                    cur.execute(f"ALTER TABLE {old} RENAME TO {new}")

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
                CREATE TABLE IF NOT EXISTS kia_modules (
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
                CREATE TABLE IF NOT EXISTS kia_access_links (
                    id         SERIAL PRIMARY KEY,
                    module_id  INTEGER NOT NULL
                                 REFERENCES kia_modules(id) ON DELETE CASCADE,
                    code       TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_enrollments (
                    id             SERIAL PRIMARY KEY,
                    module_id      INTEGER NOT NULL
                                     REFERENCES kia_modules(id) ON DELETE CASCADE,
                    user_id        INTEGER NOT NULL,
                    link_id        INTEGER REFERENCES kia_access_links(id) ON DELETE SET NULL,
                    enrolled_until TIMESTAMP,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (module_id, user_id, link_id)
                )
            """)
            # Migration: add link_id column if table already existed without it
            cur.execute("ALTER TABLE kia_enrollments ADD COLUMN IF NOT EXISTS link_id INTEGER REFERENCES kia_access_links(id) ON DELETE SET NULL")
            # Migration: drop old unique constraint and add new one with link_id
            cur.execute("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'kia_enrollments_module_id_user_id_key'
                    ) THEN
                        ALTER TABLE kia_enrollments
                            DROP CONSTRAINT kia_enrollments_module_id_user_id_key;
                    END IF;
                END $$
            """)
            cur.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'kia_enrollments_module_id_user_id_link_id_key'
                    ) THEN
                        ALTER TABLE kia_enrollments
                            ADD CONSTRAINT kia_enrollments_module_id_user_id_link_id_key
                            UNIQUE (module_id, user_id, link_id);
                    END IF;
                END $$
            """)
            # Migration: migrate existing enroll_code from modules to access_links
            cur.execute("""
                INSERT INTO kia_access_links (module_id, code, expires_at)
                SELECT id, enroll_code, enroll_code_expires
                FROM kia_modules
                WHERE enroll_code IS NOT NULL
                  AND enroll_code_expires IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM kia_access_links al
                      WHERE al.code = kia_modules.enroll_code
                  )
            """)
            # Migration: link existing enrollments to their access_links
            cur.execute("""
                UPDATE kia_enrollments e
                SET link_id = al.id
                FROM kia_access_links al
                JOIN kia_modules m ON m.id = al.module_id
                WHERE e.module_id = m.id
                  AND al.code = m.enroll_code
                  AND e.link_id IS NULL
            """)
            # Migration: allow NULL expires_at in access_links
            cur.execute("ALTER TABLE kia_access_links ALTER COLUMN expires_at DROP NOT NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_sources (
                    id              SERIAL PRIMARY KEY,
                    uuid            TEXT NOT NULL UNIQUE,
                    module_id       INTEGER NOT NULL
                                      REFERENCES kia_modules(id) ON DELETE CASCADE,
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
                ALTER TABLE kia_sources ADD COLUMN IF NOT EXISTS toc JSONB
            """)
            # Migration: add summaries_status column if missing
            cur.execute("""
                ALTER TABLE kia_sources ADD COLUMN IF NOT EXISTS summaries_status TEXT NOT NULL DEFAULT 'none'
            """)
            # Migration: add duration column for audio/video sources
            cur.execute("""
                ALTER TABLE kia_sources ADD COLUMN IF NOT EXISTS duration REAL
            """)
            # Migration: add error_message column for failed sources
            cur.execute("""
                ALTER TABLE kia_sources ADD COLUMN IF NOT EXISTS error_message TEXT
            """)
            # Migration: add language column (Whisper-detected source language, e.g. 'de', 'en')
            cur.execute("""
                ALTER TABLE kia_sources ADD COLUMN IF NOT EXISTS language TEXT
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_chunks (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES kia_sources(id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    content     TEXT NOT NULL,
                    embedding   vector,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: drop fixed-dimension constraint so any embedding model can be used
            cur.execute("""
                ALTER TABLE kia_chunks
                    ALTER COLUMN embedding TYPE vector
                    USING embedding::vector
            """)
            # Migration: add start_time/end_time for audio/video chunks
            cur.execute("""
                ALTER TABLE kia_chunks ADD COLUMN IF NOT EXISTS start_time REAL
            """)
            cur.execute("""
                ALTER TABLE kia_chunks ADD COLUMN IF NOT EXISTS end_time REAL
            """)
            # Hybrid Search: tsvector column for BM25-style keyword search
            cur.execute("""
                ALTER TABLE kia_chunks
                    ADD COLUMN IF NOT EXISTS search_vector tsvector
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_search
                ON kia_chunks USING gin(search_vector)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_paragraph_summaries (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES kia_sources(id) ON DELETE CASCADE,
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
                CREATE TABLE IF NOT EXISTS kia_mindmaps (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES kia_modules(id) ON DELETE CASCADE,
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
                CREATE TABLE IF NOT EXISTS kia_datentabellen (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES kia_modules(id) ON DELETE CASCADE,
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
                CREATE TABLE IF NOT EXISTS kia_messages (
                    id           SERIAL PRIMARY KEY,
                    module_id    INTEGER NOT NULL
                                   REFERENCES kia_modules(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    role         TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    source_pages JSONB,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: add enrollment_id to messages for per-link scoping
            cur.execute("ALTER TABLE kia_messages ADD COLUMN IF NOT EXISTS enrollment_id INTEGER REFERENCES kia_enrollments(id) ON DELETE SET NULL")
            # Migration: add source_qmap (Q-number → source UUID mapping) to messages
            cur.execute("ALTER TABLE kia_messages ADD COLUMN IF NOT EXISTS source_qmap JSONB")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_user_settings (
                    id                   SERIAL PRIMARY KEY,
                    module_id            INTEGER NOT NULL
                                           REFERENCES kia_modules(id) ON DELETE CASCADE,
                    user_id              INTEGER NOT NULL,
                    chat_lang            TEXT NOT NULL DEFAULT 'de',
                    studio_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
                    sprachtraining_active BOOLEAN NOT NULL DEFAULT FALSE,
                    UNIQUE (module_id, user_id)
                )
            """)
            cur.execute("ALTER TABLE kia_user_settings ADD COLUMN IF NOT EXISTS studio_enabled BOOLEAN NOT NULL DEFAULT TRUE")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_notes (
                    id         SERIAL PRIMARY KEY,
                    module_id  INTEGER NOT NULL
                                 REFERENCES kia_modules(id) ON DELETE CASCADE,
                    user_id    INTEGER NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE kia_notes ADD COLUMN IF NOT EXISTS title TEXT")
            cur.execute("ALTER TABLE kia_notes ADD COLUMN IF NOT EXISTS source_uuids JSONB")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_glossary_entries (
                    id               SERIAL PRIMARY KEY,
                    source_id        INTEGER NOT NULL
                                       REFERENCES kia_sources(id) ON DELETE CASCADE,
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
                ON kia_glossary_entries(source_id)
            """)
            # Migration: add English columns to glossary
            cur.execute("ALTER TABLE kia_glossary_entries ADD COLUMN IF NOT EXISTS definition_en TEXT")
            cur.execute("ALTER TABLE kia_glossary_entries ADD COLUMN IF NOT EXISTS example_sentence_en TEXT")
            # ─── Exercise Sets ──────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_exercise_sets (
                    id          SERIAL PRIMARY KEY,
                    module_id   INTEGER NOT NULL
                                  REFERENCES kia_modules(id) ON DELETE CASCADE,
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
                CREATE TABLE IF NOT EXISTS kia_exercise_items (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES kia_exercise_sets(id) ON DELETE CASCADE,
                    position    INTEGER NOT NULL DEFAULT 0,
                    front       TEXT NOT NULL,
                    back        TEXT NOT NULL,
                    options     JSONB,
                    correct_idx INTEGER,
                    source_label TEXT,
                    page_number INTEGER,
                    explanation TEXT,
                    start_time  REAL,
                    sources     JSONB
                )
            """)
            # Migration: add sources JSONB to exercise_items
            cur.execute("ALTER TABLE kia_exercise_items ADD COLUMN IF NOT EXISTS sources JSONB")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_exercise_progress (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES kia_exercise_sets(id) ON DELETE CASCADE,
                    item_id     INTEGER NOT NULL
                                  REFERENCES kia_exercise_items(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    correct     BOOLEAN NOT NULL,
                    answered_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # ─── Streak Tracking ────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kia_streaks (
                    id              SERIAL PRIMARY KEY,
                    module_id       INTEGER NOT NULL
                                      REFERENCES kia_modules(id) ON DELETE CASCADE,
                    user_id         INTEGER NOT NULL,
                    current_streak  INTEGER NOT NULL DEFAULT 0,
                    max_streak      INTEGER NOT NULL DEFAULT 0,
                    last_active_date DATE,
                    UNIQUE (module_id, user_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_sets_module_user
                ON kia_exercise_sets(module_id, user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_items_set
                ON kia_exercise_items(set_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_progress_set_user
                ON kia_exercise_progress(set_id, user_id)
            """)
            # Migration: add status column if table existed before
            cur.execute("ALTER TABLE kia_exercise_sets ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ready'")
            # Migration: add start_time for audio/video exercise items
            cur.execute("ALTER TABLE kia_exercise_items ADD COLUMN IF NOT EXISTS start_time REAL")
            # Migration: add back_en for bilingual flashcards
            cur.execute("ALTER TABLE kia_exercise_items ADD COLUMN IF NOT EXISTS back_en TEXT")
            # Migration: add extras JSONB for Lernkarten structured fields (word_parts etc.)
            cur.execute("ALTER TABLE kia_exercise_items ADD COLUMN IF NOT EXISTS extras JSONB")
            # Migration: last_run_start for tracking exercise run boundaries
            cur.execute("ALTER TABLE kia_exercise_sets ADD COLUMN IF NOT EXISTS last_run_start TIMESTAMP")
            # Migration: drop legacy mastery columns if they exist
            for col in ("correct_streak", "total_attempts", "total_correct"):
                cur.execute(f"ALTER TABLE kia_exercise_items DROP COLUMN IF EXISTS {col}")
        conn.commit()

    # Backfill tsvector for existing chunks (separate transaction)
    from loguru import logger as _log
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kia_chunks WHERE search_vector IS NULL")
            null_count = cur.fetchone()[0]
            if null_count > 0:
                _log.info("Backfilling search_vector for {} chunks...", null_count)
                cur.execute("""
                    UPDATE kia_chunks
                    SET search_vector = to_tsvector('german', content)
                    WHERE search_vector IS NULL
                """)
                _log.info("search_vector backfill done.")
            else:
                _log.info("search_vector: all chunks already populated.")

            # Embedding-Provider mutex: different models have different vector
            # dimensions, so only one may be active at a time. KISSKI has priority,
            # then mylab, then ollama.
            cur.execute("""
                SELECT key, value FROM settings
                WHERE key IN ('kisski_embedding_enabled', 'mylab_embedding_enabled', 'ollama_embedding_enabled')
            """)
            emb = {row[0]: row[1].lower() for row in cur.fetchall()}
            active = [k for k, v in emb.items() if v == "true"]
            if len(active) > 1:
                winner = "kisski_embedding_enabled" if "kisski_embedding_enabled" in active \
                    else ("mylab_embedding_enabled" if "mylab_embedding_enabled" in active else active[0])
                for k in active:
                    if k == winner:
                        continue
                    cur.execute("""
                        INSERT INTO settings (key, value) VALUES (%s, 'false')
                        ON CONFLICT (key) DO UPDATE SET value = 'false', updated_at = NOW()
                    """, (k,))
                _log.warning("Embedding mutex violated — kept {} active, disabled others.", winner)
        conn.commit()


# --- Users ---

