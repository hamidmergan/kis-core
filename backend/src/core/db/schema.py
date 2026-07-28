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
            # pg_trgm powers the typo-tolerant keyword anchor in hybrid_search_chunks:
            # a misspelled query word ("authoren") still matches a similar word in the
            # text ("Autoren") via trigram word-similarity, so the answer-bearing chunk
            # is still retrieved. Language-agnostic (character trigrams, no word lists).
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

            # Migration: rename legacy table prefixes to aia_*. All entries are
            # idempotent (no-op on fresh DBs and on already-migrated DBs).
            for old, new in [
                # Stage 1: very old ki_tutor_* tables migrate straight to aia_*.
                ("ki_tutor_modules", "aia_modules"),
                ("ki_tutor_access_links", "aia_access_links"),
                ("ki_tutor_enrollments", "aia_enrollments"),
                ("ki_tutor_sources", "aia_sources"),
                ("ki_tutor_chunks", "aia_chunks"),
                ("ki_tutor_mindmaps", "aia_mindmaps"),
                ("ki_tutor_data_tables", "aia_data_tables"),
                ("ki_tutor_messages", "aia_messages"),
                ("ki_tutor_user_settings", "aia_user_settings"),
                ("ki_tutor_notes", "aia_notes"),
                ("ki_tutor_glossary_entries", "aia_glossary_entries"),
                ("ki_tutor_exercise_sets", "aia_exercise_sets"),
                ("ki_tutor_exercise_items", "aia_exercise_items"),
                ("ki_tutor_exercise_progress", "aia_exercise_progress"),
                ("ki_tutor_streaks", "aia_streaks"),
                # Stage 2: intermediate kia_* tables migrate to aia_*.
                ("kia_modules", "aia_modules"),
                ("kia_access_links", "aia_access_links"),
                ("kia_enrollments", "aia_enrollments"),
                ("kia_sources", "aia_sources"),
                ("kia_chunks", "aia_chunks"),
                ("kia_mindmaps", "aia_mindmaps"),
                ("kia_data_tables", "aia_data_tables"),
                ("kia_messages", "aia_messages"),
                ("kia_user_settings", "aia_user_settings"),
                ("kia_notes", "aia_notes"),
                ("kia_glossary_entries", "aia_glossary_entries"),
                ("kia_exercise_sets", "aia_exercise_sets"),
                ("kia_exercise_items", "aia_exercise_items"),
                ("kia_exercise_progress", "aia_exercise_progress"),
                ("kia_streaks", "aia_streaks"),
                ("kia_schedule_entries", "aia_schedule_entries"),
                ("kia_schedule_processed_sources", "aia_schedule_processed_sources"),
                ("kia_schedule_jobs", "aia_schedule_jobs"),
                ("kia_llm_usage_log", "aia_llm_usage_log"),
                # Stage 3: rename German "zeitplan" tables (any prefix that survived) to schedule.
                ("kia_zeitplan_entries", "aia_schedule_entries"),
                ("kia_zeitplan_jobs", "aia_schedule_jobs"),
                ("kia_zeitplan_processed_sources", "aia_schedule_processed_sources"),
                # Stage 4: rename aia_module* tables to aia_workspace* (consistency with frontend /workspace route).
                ("aia_modules", "aia_workspaces"),
            ]:
                cur.execute(
                    "SELECT to_regclass(%s) IS NOT NULL AND to_regclass(%s) IS NULL",
                    (f"public.{old}", f"public.{new}"),
                )
                if cur.fetchone()[0]:
                    cur.execute(f"ALTER TABLE {old} RENAME TO {new}")

            # Rename legacy zeitplan indices to schedule (idempotent).
            for old_idx, new_idx in [
                ("idx_zeitplan_module_user", "idx_schedule_workspace_user"),
                ("idx_zeitplan_due_date", "idx_schedule_due_date"),
                ("idx_zeitplan_jobs_module_user", "idx_schedule_jobs_workspace_user"),
                # Stage 4: schedule indices use workspace_user instead of module_user.
                ("idx_schedule_module_user", "idx_schedule_workspace_user"),
                ("idx_schedule_jobs_module_user", "idx_schedule_jobs_workspace_user"),
                ("idx_exercise_sets_module_user", "idx_exercise_sets_workspace_user"),
            ]:
                cur.execute(
                    "SELECT to_regclass(%s) IS NOT NULL AND to_regclass(%s) IS NULL",
                    (f"public.{old_idx}", f"public.{new_idx}"),
                )
                if cur.fetchone()[0]:
                    cur.execute(f"ALTER INDEX {old_idx} RENAME TO {new_idx}")

            # Stage 4: rename module_id columns to workspace_id in dependent tables (idempotent).
            for table in (
                "aia_access_links",
                "aia_enrollments",
                "aia_sources",
                "aia_mindmaps",
                "aia_data_tables",
                "aia_messages",
                "aia_user_settings",
                "aia_notes",
                "aia_exercise_sets",
                "aia_streaks",
                "aia_schedule_entries",
                "aia_schedule_processed_sources",
                "aia_schedule_jobs",
            ):
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                      AND column_name = 'module_id'
                    """,
                    (table,),
                )
                if cur.fetchone():
                    cur.execute(f"ALTER TABLE {table} RENAME COLUMN module_id TO workspace_id")

            # Stage 4: rename unique constraints that referenced module_id (idempotent).
            for table, old_constraint, new_constraint in [
                ("aia_enrollments", "aia_enrollments_module_id_user_id_link_id_key",
                 "aia_enrollments_workspace_id_user_id_link_id_key"),
                ("aia_user_settings", "aia_user_settings_module_id_user_id_key",
                 "aia_user_settings_workspace_id_user_id_key"),
                ("aia_streaks", "aia_streaks_module_id_user_id_key",
                 "aia_streaks_workspace_id_user_id_key"),
            ]:
                cur.execute(
                    "SELECT 1 FROM pg_constraint WHERE conname = %s",
                    (old_constraint,),
                )
                if cur.fetchone():
                    cur.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old_constraint} TO {new_constraint}")

            # Rename legacy German column "sprachtraining_active" to "language_training_active" (idempotent).
            cur.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'aia_user_settings'
                  AND column_name = 'sprachtraining_active'
                """
            )
            if cur.fetchone():
                cur.execute(
                    "ALTER TABLE aia_user_settings RENAME COLUMN sprachtraining_active TO language_training_active"
                )

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
            # Chat block after burst-limit trigger (survives backend restart, unlike Redis counter).
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS chat_blocked_until TIMESTAMP WITH TIME ZONE")
            # UI locale preference (DE default, EN supported). Cookie + URL prefix are authoritative
            # for unauthenticated requests; this column is the cross-device source of truth after login.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS locale TEXT NOT NULL DEFAULT 'de' CHECK (locale IN ('de', 'en'))")
            # Language level diagnosis (one-time self-assessment for Fachsprachentrainer).
            # All three columns nullable: NULL means "diagnosis not yet completed".
            # The full CEFR ladder A1..C2. An earlier version collapsed everything
            # above B1 into "B1+"; the scale now runs the whole ladder so the
            # adaptive chat can pitch every level, not only "needs support" vs not.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_level TEXT CHECK (language_level IN ('A1','A2','B1','B2','C1','C2'))")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_level_set_at TIMESTAMP WITH TIME ZONE")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_level_skill_scores JSONB")
            # Migration: the outcome set grew from the four A1..B1+ values back to
            # the full ladder. The inline CHECK above only fires on fresh installs,
            # so rewrite the constraint on existing DBs. Any stored "B1+" (the old
            # "above B1") maps to B2, the lowest band it stood for, so the new CHECK
            # cannot fail validation.
            cur.execute("UPDATE users SET language_level = 'B2' WHERE language_level = 'B1+'")
            cur.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_language_level_check")
            cur.execute("ALTER TABLE users ADD CONSTRAINT users_language_level_check CHECK (language_level IN ('A1','A2','B1','B2','C1','C2'))")
            # === Role system migration ===
            # System roles: 'admin', 'staff', 'user' (fixed, code-defined permissions).
            # Custom roles live in the custom_roles table; users.custom_role_id is set
            # iff users.role = 'custom'. Existing legacy values are migrated:
            #   'lecturer' -> 'staff'
            #   'student'  -> 'user'
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_roles (
                    id            SERIAL PRIMARY KEY,
                    name          TEXT NOT NULL UNIQUE,
                    aia_access    TEXT NOT NULL DEFAULT 'none'
                                  CHECK (aia_access IN ('none','read','edit')),
                    allowed_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migrate the original boolean `allow_aia` to the tri-state `aia_access`
            # ('none'|'read'|'edit') introduced in commit c2a6bbd. DBs created before
            # that commit still carry the boolean column, so the role repository's
            # `SELECT ... aia_access ...` raised "column aia_access does not exist"
            # (a 500 on /api/admin/roles). Idempotent: the ADD is guarded by
            # IF NOT EXISTS, the data copy + drop only run while allow_aia survives.
            cur.execute(
                "ALTER TABLE custom_roles ADD COLUMN IF NOT EXISTS aia_access "
                "TEXT NOT NULL DEFAULT 'none' "
                "CHECK (aia_access IN ('none','read','edit'))"
            )
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'custom_roles'
                          AND column_name = 'allow_aia'
                    ) THEN
                        UPDATE custom_roles SET aia_access = 'read' WHERE allow_aia = TRUE;
                        ALTER TABLE custom_roles DROP COLUMN allow_aia;
                    END IF;
                END $$;
            """)
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_role_id INTEGER "
                "REFERENCES custom_roles(id) ON DELETE SET NULL"
            )
            # Migrate legacy role strings (idempotent).
            cur.execute("UPDATE users SET role = 'staff' WHERE role = 'lecturer'")
            cur.execute("UPDATE users SET role = 'user'  WHERE role = 'student'")
            # New default for the column going forward.
            cur.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'")
            # Constraint: role must be one of the four allowed values.
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'users_role_check'
                    ) THEN
                        ALTER TABLE users
                            ADD CONSTRAINT users_role_check
                            CHECK (role IN ('admin', 'staff', 'user', 'custom'));
                    END IF;
                END
                $$
            """)
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
            cur.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS username")
            # Locale at job-creation time, used by Celery workers (no HTTP context)
            # to localize error_message strings on timeout / provider failure.
            cur.execute(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS creator_locale TEXT NOT NULL DEFAULT 'de' "
                "CHECK (creator_locale IN ('de', 'en'))"
            )
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
            # Per-user terminology glossaries for the translation tool. The id is
            # a client-visible opaque string (uuid hex) generated server-side, so
            # the frontend Glossary.id stays a plain string. entries is a flat
            # {source_term: target_term} map. Deleting a user removes their
            # glossaries.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_glossaries (
                    id         TEXT PRIMARY KEY,
                    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name       TEXT NOT NULL,
                    entries    JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_glossaries_user "
                "ON user_glossaries(user_id, created_at)"
            )
            if admin_email and admin_email.strip():
                cur.execute(
                    "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                    (admin_email.strip().lower(),),
                )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_workspaces (
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
                    updated_at           TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_visited_at      TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: add last_visited_at; backfill existing rows from updated_at so initial sort is meaningful
            cur.execute("ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS last_visited_at TIMESTAMP")
            cur.execute("UPDATE aia_workspaces SET last_visited_at = COALESCE(updated_at, created_at, NOW()) WHERE last_visited_at IS NULL")
            cur.execute("ALTER TABLE aia_workspaces ALTER COLUMN last_visited_at SET NOT NULL")
            cur.execute("ALTER TABLE aia_workspaces ALTER COLUMN last_visited_at SET DEFAULT NOW()")
            # Per-workspace setting: EN transcript translation mode (off/auto/manual). Owner-controlled.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS transcript_translation_mode TEXT NOT NULL DEFAULT 'manual'"
            )
            # Per-workspace setting: default transcript view (source/target/both). Owner-controlled.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS transcript_default_lang TEXT NOT NULL DEFAULT 'both'"
            )
            # Per-workspace setting: the ONE language the owner translates transcripts into
            # (short ISO code, see i18n.TRANSCRIPT_LANGUAGES). Source is the Whisper-detected
            # media language; English is the default target.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS transcript_target_lang TEXT NOT NULL DEFAULT 'en'"
            )
            # Migrate legacy default-view values: the pill used to be language-specific
            # (de/en) but the target is now owner-chosen, so it became role-based.
            cur.execute("UPDATE aia_workspaces SET transcript_default_lang = 'source' WHERE transcript_default_lang = 'de'")
            cur.execute("UPDATE aia_workspaces SET transcript_default_lang = 'target' WHERE transcript_default_lang = 'en'")
            # Per-workspace setting: the language the CEFR chat diagnosis is held in
            # (short ISO code, see i18n.TRANSCRIPT_LANGUAGES). Independent of the
            # transcript target — a workspace can hold French sources while the
            # diagnosis stays in the language the course is taught in.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS diagnosis_language TEXT NOT NULL DEFAULT 'de'"
            )
            # Owner-managed pinned note shown above the sources list. Plain text + structured links.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS staff_note_text TEXT"
            )
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS staff_note_links JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
            # Legacy per-workspace summary toggle: summaries were removed entirely
            # (pgvector-only retrieval), so drop the now-meaningless column.
            cur.execute("ALTER TABLE aia_workspaces DROP COLUMN IF EXISTS summary_mode")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_access_links (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    code         TEXT NOT NULL UNIQUE,
                    expires_at   TIMESTAMP,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_enrollments (
                    id             SERIAL PRIMARY KEY,
                    workspace_id   INTEGER NOT NULL
                                     REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id        INTEGER NOT NULL,
                    link_id        INTEGER REFERENCES aia_access_links(id) ON DELETE SET NULL,
                    enrolled_until TIMESTAMP,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (workspace_id, user_id, link_id)
                )
            """)
            # Migration: add link_id column if table already existed without it
            cur.execute("ALTER TABLE aia_enrollments ADD COLUMN IF NOT EXISTS link_id INTEGER REFERENCES aia_access_links(id) ON DELETE SET NULL")
            # Migration: drop legacy unique constraints (both pre-link_id and pre-workspace_id versions)
            cur.execute("""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'aia_enrollments_module_id_user_id_key'
                    ) THEN
                        ALTER TABLE aia_enrollments
                            DROP CONSTRAINT aia_enrollments_module_id_user_id_key;
                    END IF;
                END $$
            """)
            cur.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'aia_enrollments_workspace_id_user_id_link_id_key'
                    ) THEN
                        ALTER TABLE aia_enrollments
                            ADD CONSTRAINT aia_enrollments_workspace_id_user_id_link_id_key
                            UNIQUE (workspace_id, user_id, link_id);
                    END IF;
                END $$
            """)
            # Migration: migrate existing enroll_code from workspaces to access_links
            cur.execute("""
                INSERT INTO aia_access_links (workspace_id, code, expires_at)
                SELECT id, enroll_code, enroll_code_expires
                FROM aia_workspaces
                WHERE enroll_code IS NOT NULL
                  AND enroll_code_expires IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM aia_access_links al
                      WHERE al.code = aia_workspaces.enroll_code
                  )
            """)
            # Migration: link existing enrollments to their access_links
            cur.execute("""
                UPDATE aia_enrollments e
                SET link_id = al.id
                FROM aia_access_links al
                JOIN aia_workspaces m ON m.id = al.workspace_id
                WHERE e.workspace_id = m.id
                  AND al.code = m.enroll_code
                  AND e.link_id IS NULL
            """)
            # Migration: allow NULL expires_at in access_links
            cur.execute("ALTER TABLE aia_access_links ALTER COLUMN expires_at DROP NOT NULL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_sources (
                    id              SERIAL PRIMARY KEY,
                    uuid            TEXT NOT NULL UNIQUE,
                    workspace_id    INTEGER NOT NULL
                                      REFERENCES aia_workspaces(id) ON DELETE CASCADE,
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
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS toc JSONB
            """)
            # Migration: add duration column for audio/video sources
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS duration REAL
            """)
            # Migration: add error_message column for failed sources
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS error_message TEXT
            """)
            # Migration: add language column (Whisper-detected source language, e.g. 'de', 'en')
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS language TEXT
            """)
            # Migration: fine-grained progress info during indexing. NULL when the
            # source is at rest (ready/failed/pending). JSON shape is
            # ``{"stage": str, "page": int?, "total": int?}`` so the UI can render
            # a stage label plus an optional page counter without inventing keys.
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS progress JSONB
            """)
            # Migration: per-source DOC SUMMARY (one compact summary built at ingest,
            # map-reduce over chunks). Used for GENERIC/overview answers. NULL until
            # built; a source is only set 'ready' once its summary exists.
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS summary TEXT
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_chunks (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES aia_sources(id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    content     TEXT NOT NULL,
                    embedding   vector,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: drop fixed-dimension constraint so any embedding model can be used
            cur.execute("""
                ALTER TABLE aia_chunks
                    ALTER COLUMN embedding TYPE vector
                    USING embedding::vector
            """)
            # Migration: add start_time/end_time for audio/video chunks
            cur.execute("""
                ALTER TABLE aia_chunks ADD COLUMN IF NOT EXISTS start_time REAL
            """)
            cur.execute("""
                ALTER TABLE aia_chunks ADD COLUMN IF NOT EXISTS end_time REAL
            """)
            # Hybrid Search: tsvector column for BM25-style keyword search
            cur.execute("""
                ALTER TABLE aia_chunks
                    ADD COLUMN IF NOT EXISTS search_vector tsvector
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_search
                ON aia_chunks USING gin(search_vector)
            """)
            # Trigram index on content for the fuzzy (typo-tolerant) keyword fallback
            # in hybrid_search_chunks — lets the `<%` word-similarity operator use an
            # index instead of scanning every chunk.
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_content_trgm
                ON aia_chunks USING gin(content gin_trgm_ops)
            """)
            # Migration: legacy page/paragraph summary TABLES were removed
            # (pgvector-only retrieval). NOTE: the per-source ``summary`` column is
            # BACK (added above) for the DOC SUMMARY feature (GENERIC answers) — do
            # NOT re-add a DROP for it. Idempotent.
            cur.execute("DROP TABLE IF EXISTS aia_page_summaries")
            cur.execute("DROP TABLE IF EXISTS aia_paragraph_summaries")
            cur.execute("ALTER TABLE aia_sources DROP COLUMN IF EXISTS summaries_status")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_mindmaps (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    source_ids   JSONB NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    mindmap      JSONB,
                    error        TEXT,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_data_tables (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    source_ids   JSONB NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    title        TEXT,
                    table_data   JSONB,
                    sources      JSONB,
                    error        TEXT,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # AIA-owned orchestration queue. Decouples AIA background work from the
            # global-tools `jobs` table (which is being split into its own project).
            # area = 'ingest' | 'studio'. status = 'queued' | 'running' | 'done' | 'failed'.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_jobs (
                    id             SERIAL PRIMARY KEY,
                    job_uuid       TEXT NOT NULL UNIQUE,
                    user_id        INTEGER NOT NULL,
                    area           TEXT NOT NULL,
                    task_name      TEXT NOT NULL,
                    payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status         TEXT NOT NULL DEFAULT 'queued',
                    celery_task_id TEXT,
                    error          TEXT,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    started_at     TIMESTAMP,
                    finished_at    TIMESTAMP
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_aia_jobs_area_status "
                "ON aia_jobs(area, status, created_at)"
            )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_messages (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    role         TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    source_pages JSONB,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Migration: add enrollment_id to messages for per-link scoping
            cur.execute("ALTER TABLE aia_messages ADD COLUMN IF NOT EXISTS enrollment_id INTEGER REFERENCES aia_enrollments(id) ON DELETE SET NULL")
            # Migration: add source_qmap (Q-number → source UUID mapping) to messages
            cur.execute("ALTER TABLE aia_messages ADD COLUMN IF NOT EXISTS source_qmap JSONB")
            # Migration: mark assistant messages whose stream was cancelled by the user
            cur.execute("ALTER TABLE aia_messages ADD COLUMN IF NOT EXISTS aborted BOOLEAN NOT NULL DEFAULT FALSE")
            # Migration: mark assistant messages whose stream died on an error. Kept
            # apart from `aborted` on purpose - the UI labels a cancelled turn
            # "stopped" and a failed one "failed" with a retry button, and calling a
            # provider outage a user cancellation would be a lie.
            cur.execute("ALTER TABLE aia_messages ADD COLUMN IF NOT EXISTS failed BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_user_settings (
                    id                   SERIAL PRIMARY KEY,
                    workspace_id         INTEGER NOT NULL
                                           REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id              INTEGER NOT NULL,
                    chat_lang            TEXT NOT NULL DEFAULT 'de',
                    studio_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
                    language_training_active BOOLEAN NOT NULL DEFAULT FALSE,
                    UNIQUE (workspace_id, user_id)
                )
            """)
            cur.execute("ALTER TABLE aia_user_settings ADD COLUMN IF NOT EXISTS studio_enabled BOOLEAN NOT NULL DEFAULT TRUE")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_notes (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    content      TEXT NOT NULL,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE aia_notes ADD COLUMN IF NOT EXISTS title TEXT")
            cur.execute("ALTER TABLE aia_notes ADD COLUMN IF NOT EXISTS source_uuids JSONB")
            cur.execute("ALTER TABLE aia_notes ADD COLUMN IF NOT EXISTS source_pages JSONB")
            cur.execute("ALTER TABLE aia_notes ADD COLUMN IF NOT EXISTS popup_selection JSONB")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_glossary_entries (
                    id               SERIAL PRIMARY KEY,
                    user_id          INTEGER NOT NULL,
                    source_id        INTEGER NOT NULL
                                       REFERENCES aia_sources(id) ON DELETE CASCADE,
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
            # Migration: add English columns to glossary
            cur.execute("ALTER TABLE aia_glossary_entries ADD COLUMN IF NOT EXISTS definition_en TEXT")
            cur.execute("ALTER TABLE aia_glossary_entries ADD COLUMN IF NOT EXISTS example_sentence_en TEXT")
            # Migration: dictionary base form (lemma) of the marked term, e.g. the
            # marked "läuft" carries base_form "laufen". Empty when the term is
            # already in its base form or cannot be lemmatised (phrase, loanword).
            cur.execute("ALTER TABLE aia_glossary_entries ADD COLUMN IF NOT EXISTS base_form TEXT")

            # ─── Glossary: back to a plain per-user glossary ──────────────────
            # The glossary used to be a workspace-shared pool (aia_glossary_entries)
            # with an M:N per-user pick list (aia_user_glossary_picks), fed by an
            # auto-extraction task. That is gone: the glossary is now built only
            # via the PDF popup action bar, one private glossary per user. This
            # one-time reset drops the pool machinery and discards the old shared
            # entries. Guarded so it fires only while old structures still exist —
            # afterwards every condition is false, so it never truncates again.
            cur.execute("""
                SELECT
                  to_regclass('public.aia_user_glossary_picks') IS NOT NULL
                  OR EXISTS (SELECT 1 FROM information_schema.columns
                             WHERE table_schema = 'public'
                               AND table_name = 'aia_glossary_entries'
                               AND column_name = 'chunk_id')
                  OR NOT EXISTS (SELECT 1 FROM information_schema.columns
                                 WHERE table_schema = 'public'
                                   AND table_name = 'aia_glossary_entries'
                                   AND column_name = 'user_id')
            """)
            if cur.fetchone()[0]:
                cur.execute("DROP TABLE IF EXISTS aia_user_glossary_picks CASCADE")
                cur.execute("TRUNCATE aia_glossary_entries")
                cur.execute("ALTER TABLE aia_glossary_entries DROP COLUMN IF EXISTS chunk_id")
                cur.execute("ALTER TABLE aia_glossary_entries ADD COLUMN IF NOT EXISTS user_id INTEGER")
                cur.execute("ALTER TABLE aia_glossary_entries ALTER COLUMN user_id SET NOT NULL")
                cur.execute("ALTER TABLE aia_chunks DROP COLUMN IF EXISTS glossary_processed")
                cur.execute("DROP INDEX IF EXISTS idx_glossary_source_chunk")
                cur.execute("DROP INDEX IF EXISTS idx_glossary_source")

            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_glossary_user_source "
                "ON aia_glossary_entries(user_id, source_id)"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_glossary_user_source_term "
                "ON aia_glossary_entries(user_id, source_id, lower(term_de))"
            )
            # ─── Exercise Sets ──────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_exercise_sets (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    tool         TEXT NOT NULL,
                    title        TEXT NOT NULL,
                    mode         TEXT NOT NULL DEFAULT 'glossary',
                    source_uuid  TEXT,
                    card_count   INTEGER NOT NULL DEFAULT 0,
                    status       TEXT NOT NULL DEFAULT 'generating',
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_exercise_items (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES aia_exercise_sets(id) ON DELETE CASCADE,
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
            cur.execute("ALTER TABLE aia_exercise_items ADD COLUMN IF NOT EXISTS sources JSONB")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_exercise_progress (
                    id          SERIAL PRIMARY KEY,
                    set_id      INTEGER NOT NULL
                                  REFERENCES aia_exercise_sets(id) ON DELETE CASCADE,
                    item_id     INTEGER NOT NULL
                                  REFERENCES aia_exercise_items(id) ON DELETE CASCADE,
                    user_id     INTEGER NOT NULL,
                    correct     BOOLEAN NOT NULL,
                    answered_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # ─── Learner Profile (adaptive weakness tracking) ────
            # Weaknesses are scoped to a workspace: a term learned as difficult in one
            # module must not bleed into another, where it may mean something else or
            # nothing at all.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_learner_weakness (
                    id            SERIAL PRIMARY KEY,
                    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    workspace_id  INTEGER NOT NULL REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    category      TEXT NOT NULL,
                    key_norm      TEXT NOT NULL,
                    label         TEXT NOT NULL,
                    source_id     INTEGER REFERENCES aia_sources(id) ON DELETE SET NULL,
                    weight        REAL NOT NULL DEFAULT 0,
                    hit_count     INTEGER NOT NULL DEFAULT 0,
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # Migration for pre-workspace installs: the old table had no workspace_id
            # and a user-wide unique key. There is no workspace to backfill onto, so
            # old rows are dropped (a clean, per-workspace start) and the unique key is
            # rebuilt to include the workspace.
            cur.execute(
                "ALTER TABLE aia_learner_weakness ADD COLUMN IF NOT EXISTS "
                "workspace_id INTEGER REFERENCES aia_workspaces(id) ON DELETE CASCADE"
            )
            cur.execute("DELETE FROM aia_learner_weakness WHERE workspace_id IS NULL")
            cur.execute("ALTER TABLE aia_learner_weakness ALTER COLUMN workspace_id SET NOT NULL")
            cur.execute(
                "ALTER TABLE aia_learner_weakness DROP CONSTRAINT IF EXISTS "
                "aia_learner_weakness_user_id_category_key_norm_key"
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_learner_weakness_ws "
                "ON aia_learner_weakness(user_id, workspace_id, category, key_norm)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_learner_weakness_user "
                "ON aia_learner_weakness(user_id, last_seen_at)"
            )
            # Global per-user off-switch for weakness tracking, on by default.
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "learning_profile_enabled BOOLEAN NOT NULL DEFAULT TRUE"
            )
            # ─── Streak Tracking ────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_streaks (
                    id              SERIAL PRIMARY KEY,
                    workspace_id    INTEGER NOT NULL
                                      REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id         INTEGER NOT NULL,
                    current_streak  INTEGER NOT NULL DEFAULT 0,
                    max_streak      INTEGER NOT NULL DEFAULT 0,
                    last_active_date DATE,
                    UNIQUE (workspace_id, user_id)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_sets_workspace_user
                ON aia_exercise_sets(workspace_id, user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_items_set
                ON aia_exercise_items(set_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_exercise_progress_set_user
                ON aia_exercise_progress(set_id, user_id)
            """)
            # Migration: add status column if table existed before
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ready'")
            # Migration: add start_time for audio/video exercise items
            cur.execute("ALTER TABLE aia_exercise_items ADD COLUMN IF NOT EXISTS start_time REAL")
            # Migration: add back_en for bilingual flashcards
            cur.execute("ALTER TABLE aia_exercise_items ADD COLUMN IF NOT EXISTS back_en TEXT")
            # Migration: add extras JSONB for Flashcards structured fields (word_parts etc.)
            cur.execute("ALTER TABLE aia_exercise_items ADD COLUMN IF NOT EXISTS extras JSONB")
            # Migration: last_run_start for tracking exercise run boundaries
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS last_run_start TIMESTAMP")
            # Migration: drop legacy mastery columns if they exist
            for col in ("correct_streak", "total_attempts", "total_correct"):
                cur.execute(f"ALTER TABLE aia_exercise_items DROP COLUMN IF EXISTS {col}")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_schedule_entries (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    type         TEXT NOT NULL CHECK (type IN ('deadline', 'termin')),
                    title        TEXT NOT NULL,
                    description  TEXT,
                    due_date     DATE,
                    due_time     TIME,
                    is_optional  BOOLEAN NOT NULL DEFAULT FALSE,
                    is_checked   BOOLEAN NOT NULL DEFAULT FALSE,
                    checked_at   TIMESTAMP,
                    origin       TEXT NOT NULL CHECK (origin IN ('llm', 'manual')),
                    source_refs  JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE aia_schedule_entries ADD COLUMN IF NOT EXISTS source_refs JSONB NOT NULL DEFAULT '[]'::jsonb")
            # Drop legacy columns (were single-position; replaced by source_refs array)
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS source_ids")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS raw_quote")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS page_number")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS start_time")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_workspace_user
                ON aia_schedule_entries(workspace_id, user_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_due_date
                ON aia_schedule_entries(workspace_id, user_id, due_date)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_schedule_processed_sources (
                    workspace_id  INTEGER NOT NULL
                                    REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id       INTEGER NOT NULL,
                    source_id     INTEGER NOT NULL
                                    REFERENCES aia_sources(id) ON DELETE CASCADE,
                    processed_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (workspace_id, user_id, source_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_schedule_jobs (
                    id            SERIAL PRIMARY KEY,
                    workspace_id  INTEGER NOT NULL
                                    REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id       INTEGER NOT NULL,
                    source_uuids  JSONB NOT NULL DEFAULT '[]'::jsonb,
                    status        TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'running', 'success', 'failed')),
                    error         TEXT,
                    added_count   INTEGER NOT NULL DEFAULT 0,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedule_jobs_workspace_user
                ON aia_schedule_jobs(workspace_id, user_id)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_schedule_source_extractions (
                    source_id        INTEGER PRIMARY KEY
                                       REFERENCES aia_sources(id) ON DELETE CASCADE,
                    candidates       JSONB NOT NULL,
                    classifications  JSONB NOT NULL,
                    extracted_at     TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            # ─── AI Providers ─────────────────────────────────────────────────
            # Provider-centric admin model: each row is an endpoint the admin
            # registered (Name + Protocol + URL + Key). Capabilities are filled
            # by probe (openai_compat) or by protocol definition (deepl/docling).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    id             SERIAL PRIMARY KEY,
                    name           TEXT NOT NULL UNIQUE,
                    protocol       TEXT NOT NULL,
                    base_url       TEXT NOT NULL,
                    api_key        TEXT,
                    capabilities   JSONB NOT NULL DEFAULT '[]'::jsonb,
                    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
                    last_probed_at TIMESTAMP WITH TIME ZONE,
                    probe_status   TEXT,
                    probe_error    TEXT,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_providers_protocol
                ON providers(protocol)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_providers_enabled
                ON providers(enabled) WHERE enabled = TRUE
            """)
            # Migration: add voices column (provider-specific voice catalogue)
            cur.execute("""
                ALTER TABLE providers
                ADD COLUMN IF NOT EXISTS voices JSONB NOT NULL DEFAULT '[]'::jsonb
            """)

            # ─── Feature Routes ───────────────────────────────────────────────
            # One row per feature (chat, embedding, ocr, ...). Maps a feature to
            # a chosen provider + model. user_choices is the multi-pill list of
            # provider IDs the user may pick from in the tool UI (used for tts,
            # doc_translate). Unset feature row means the feature is
            # unconfigured and not available.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feature_routes (
                    id              SERIAL PRIMARY KEY,
                    feature         TEXT NOT NULL UNIQUE,
                    provider_id     INTEGER REFERENCES providers(id) ON DELETE SET NULL,
                    model_name      TEXT,
                    user_choices    JSONB NOT NULL DEFAULT '[]'::jsonb,
                    provider_models JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE feature_routes
                ADD COLUMN IF NOT EXISTS provider_models JSONB NOT NULL DEFAULT '{}'::jsonb
            """)
            # Die Route screencast_translate ist entfallen. Der Screencast hat
            # sein Modell immer aus doc_translate gelesen, die Zeile im Admin
            # wirkte also nie und führte in die Irre. Beide Werkzeuge übersetzen
            # dieselben Dateien, eine Einstellung reicht. Idempotent.
            cur.execute("DELETE FROM feature_routes WHERE feature = 'screencast_translate'")

            # ─── LLM Usage Log ────────────────────────────────────────────────
            # One row per request: for daily alerts (anomaly detection) and
            # admin visibility. Token columns are nullable - Langfuse has
            # the exact truth, here "best effort" from response.usage is enough.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_llm_usage_log (
                    id          BIGSERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    ts          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    endpoint    VARCHAR(64) NOT NULL,
                    provider    VARCHAR(32),
                    model       VARCHAR(128),
                    tokens_in   INTEGER,
                    tokens_out  INTEGER,
                    duration_ms INTEGER,
                    status      VARCHAR(16) NOT NULL DEFAULT 'ok'
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_log_user_ts
                ON aia_llm_usage_log(user_id, ts DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_usage_log_ts
                ON aia_llm_usage_log(ts DESC)
            """)
        conn.commit()

    # Backfill / migrate tsvector (separate transaction).
    # Switched from 'german' to 'simple' tokenizer so non-German content
    # (English, Turkish, Spanish slides/transcripts) also gets useful keyword
    # search hits. Vector search still handles semantic matches; the keyword
    # side just needs language-agnostic exact-token matching.
    from loguru import logger as _log
    with get_connection() as conn:
        with conn.cursor() as cur:
            migration_key = "search_vector_simple_migration_done"
            cur.execute("SELECT value FROM settings WHERE key = %s", (migration_key,))
            row = cur.fetchone()
            already_migrated = bool(row and row[0] == "true")

            cur.execute("SELECT COUNT(*) FROM aia_chunks WHERE search_vector IS NULL")
            null_count = cur.fetchone()[0]

            if not already_migrated:
                _log.info("Rewriting search_vector with 'simple' tokenizer for ALL chunks...")
                cur.execute("UPDATE aia_chunks SET search_vector = to_tsvector('simple', content)")
                cur.execute(
                    """INSERT INTO settings (key, value) VALUES (%s, 'true')
                       ON CONFLICT (key) DO UPDATE SET value = 'true'""",
                    (migration_key,),
                )
                _log.info("search_vector simple-migration done.")
            elif null_count > 0:
                _log.info("Backfilling search_vector for {} chunks...", null_count)
                cur.execute("""
                    UPDATE aia_chunks
                    SET search_vector = to_tsvector('simple', content)
                    WHERE search_vector IS NULL
                """)
                _log.info("search_vector backfill done.")
            else:
                _log.info("search_vector: all chunks already populated.")

        conn.commit()

    # hnsw ANN index for vector search (own transaction, so a long build stays out of the
    # schema transaction and a failure cannot roll schema setup back). Built on the
    # halfvec(2560) form of embedding: 2560-dim exceeds pgvector's 2000-dim vector-index
    # limit, halfvec allows up to 4000. PARTIAL on vector_dims=2560 so a future different-dim
    # model neither breaks inserts nor is wrongly returned (see chunks._vector_search_sql,
    # which queries in the same form). SET LOCAL keeps the build tuning off the pooled
    # connection: parallel index build shares memory via DSM in /dev/shm (only 64MB in a
    # Docker container -> "could not resize shared memory segment"), so parallel maintenance
    # is disabled. IF NOT EXISTS = built once; on an existing prod DB prefer a manual
    # CREATE INDEX CONCURRENTLY off-hours before deploy so first startup does not block.
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SET LOCAL max_parallel_maintenance_workers = 0")
                cur.execute("SET LOCAL maintenance_work_mem = '256MB'")
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
                    ON aia_chunks USING hnsw ((embedding::halfvec(2560)) halfvec_cosine_ops)
                    WHERE vector_dims(embedding) = 2560
                """)
                conn.commit()
                _log.info("hnsw vector index ready (idx_chunks_embedding_hnsw).")
            except Exception as e:
                conn.rollback()
                _log.warning("hnsw vector index build skipped/failed (vector search falls back to scan): {}", e)


# --- Users ---

