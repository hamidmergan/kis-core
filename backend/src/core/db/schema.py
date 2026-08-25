import os
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
from src.core.db.pool import get_connection


# Wie lange eine Wanderung auf eine Tabellensperre wartet, bevor sie aufgibt. Ohne das
# wartet ein ALTER TABLE unbegrenzt auf die Worker, die dieselbe Tabelle lesen, und ein
# Neustart bei laufenden Workern endet in einer Verklemmung: der Migrator will die
# Tabelle exklusiv, der Worker haelt sie lesend und will eine zweite. Postgres loest das
# auf, indem es einen von beiden abschiesst, und das war bisher der Start des Backends.
_MIGRATION_LOCK_TIMEOUT = "10s"
# So oft wird es erneut versucht. Jede Anweisung in init_db ist idempotent
# (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS), ein zweiter Anlauf ist also gefahrlos.
_MIGRATION_ATTEMPTS = 5

# Einmaliger Schritt, kein wiederholbarer. Siehe _reset_quiz_pool_once.
_QUIZ_POOL_RESET_KEY = "quiz_pool_true_false_reset_done"

# Dasselbe fuer die Grammatik. Siehe _reset_grammar_pool_once.
_GRAMMAR_POOL_RESET_KEY = "grammar_pool_task_line_reset_done"


def _reset_quiz_pool_once(cur) -> bool:
    """Den Quiz-Vorrat einmalig wegwerfen, weil Richtig/Falsch dazugekommen ist.

    Das Quiz zieht zuerst aus dem Vorrat, und die vorhandenen Zeilen kennen nur die zwei
    Ankreuz-Arten. Ohne diesen Schritt kaeme weiter das Alte heraus und die Aenderung
    waere unsichtbar.

    Zwei Dinge sind hier wichtig.

    Zurueckgeschrieben wird VOR dem Loeschen. Eine Aufgabe aus dem Vorrat wird nicht in
    den Satz kopiert, der Satz zeigt nur dorthin, und die Inhaltsspalten seiner Zeile
    sind leer. Ein blankes DELETE setzt den Verweis per ON DELETE SET NULL auf NULL und
    macht damit jeden fertigen Satz leer, der darauf zeigt. Dieselbe Reihenfolge macht
    ``clear_pool_for_source`` vor.

    Und er laeuft genau einmal. Anders als beim abgeschafften Hoerverstehen entstehen
    beim Quiz laufend neue Vorratszeilen, ein ungeschuetzter Schritt wuerde den Vorrat
    bei jedem Neustart des Backends wieder wegwerfen. Der Schluessel in ``settings``
    macht es wie die search_vector-Wanderung weiter unten in dieser Datei.

    Gibt zurueck, ob der Schritt gelaufen ist.
    """
    cur.execute("SELECT value FROM settings WHERE key = %s", (_QUIZ_POOL_RESET_KEY,))
    row = cur.fetchone()
    if row and row[0] == "true":
        return False
    cur.execute(
        """UPDATE aia_exercise_items i
              SET back = p.back, back_en = p.back_en, options = p.options,
                  correct_idx = p.correct_idx, explanation = p.explanation,
                  source_label = p.source_label, page_number = p.page_number,
                  start_time = p.start_time, sources = p.sources, extras = p.extras
             FROM aia_exercise_pool p
            WHERE i.pool_item_id = p.id AND p.tool = 'quiz'"""
    )
    cur.execute("DELETE FROM aia_exercise_pool WHERE tool = 'quiz'")
    cur.execute(
        """INSERT INTO settings (key, value) VALUES (%s, 'true')
           ON CONFLICT (key) DO UPDATE SET value = 'true'""",
        (_QUIZ_POOL_RESET_KEY,),
    )
    return True


def _reset_grammar_pool_once(cur) -> bool:
    """Den Grammatik-Vorrat einmalig wegwerfen, weil die Anweisungszeile neu ist.

    Die Anweisung ueber einer Aufgabe wird beim Erzeugen fest in den Aufgabentext
    geschrieben. Der Vorrat traegt damit die alte Fassung ("Setze den Satz ins
    Relativsatz.") in seinen Zeilen, und ein neuer Satz zieht zuerst aus dem Vorrat.
    Ohne diesen Schritt kaeme also weiter das Gemeldete heraus, obwohl der Code es
    laengst besser macht.

    Aufbau wie bei :func:`_reset_quiz_pool_once`: erst zurueckschreiben, dann loeschen,
    und genau einmal. Zum Zurueckschreiben siehe dort, die Gruende sind dieselben. Die
    Grammatik legt laufend neue Vorratszeilen an, ein ungeschuetzter Schritt wuerfe sie
    bei jedem Neustart des Backends weg.

    Fertige Saetze behalten ihre alte Anweisung. Das ist Absicht: sie sind bearbeitet,
    teils schon beantwortet, und ein Satz, dessen Aufgaben sich unter der Hand
    umformulieren, waere schlimmer als eine schiefe Zeile in einem alten Satz.

    Gibt zurueck, ob der Schritt gelaufen ist.
    """
    cur.execute("SELECT value FROM settings WHERE key = %s", (_GRAMMAR_POOL_RESET_KEY,))
    row = cur.fetchone()
    if row and row[0] == "true":
        return False
    cur.execute(
        """UPDATE aia_exercise_items i
              SET back = p.back, back_en = p.back_en, options = p.options,
                  correct_idx = p.correct_idx, explanation = p.explanation,
                  source_label = p.source_label, page_number = p.page_number,
                  start_time = p.start_time, sources = p.sources, extras = p.extras
             FROM aia_exercise_pool p
            WHERE i.pool_item_id = p.id AND p.tool = 'grammatik'"""
    )
    cur.execute("DELETE FROM aia_exercise_pool WHERE tool = 'grammatik'")
    cur.execute(
        """INSERT INTO settings (key, value) VALUES (%s, 'true')
           ON CONFLICT (key) DO UPDATE SET value = 'true'""",
        (_GRAMMAR_POOL_RESET_KEY,),
    )
    return True


def _table_exists(cur, table: str) -> bool:
    """Gibt es die Tabelle schon?

    Fuer Aufraeum-Schritte am Altbestand (UPDATE, DELETE), die eine Tabelle lesen,
    die weiter unten erst entsteht. Auf einer gewachsenen Datenbank ist sie laengst
    da und der Schritt laeuft; auf einer LEEREN gibt es nichts aufzuraeumen, und
    ohne diese Frage braeche der ganze Start ab. Eine neue Hochschule faengt immer
    mit einer leeren Datenbank an, dort zaehlt das.

    Nicht dasselbe wie eine Strukturaenderung: ein fehlendes ``ADD COLUMN`` wird
    auch auf einer frischen Datenbank gebraucht, das gehoert an die richtige
    Stelle gezogen statt uebersprungen.
    """
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",))
    return bool(cur.fetchone()[0])


def init_db(admin_email: Optional[str] = None) -> None:
    """Schema anlegen und wandern. Wiederholt sich bei Sperrkonflikten.

    Gemessen am 2026-08-08: ein Neustart des Backends waehrend die Celery-Worker liefen
    endete mit ``DeadlockDetected`` beim ALTER TABLE, und danach mit
    ``Application startup failed. Exiting.`` Das Backend kam nicht mehr hoch. Eine
    begrenzte Wartezeit plus Wiederholung macht daraus eine Verzoegerung von Sekunden.
    """
    from loguru import logger

    letzter: Exception | None = None
    for versuch in range(1, _MIGRATION_ATTEMPTS + 1):
        try:
            _init_db(admin_email)
            if versuch > 1:
                logger.info("Datenbank-Wanderung im {}. Anlauf durch", versuch)
            return
        except (psycopg2.errors.DeadlockDetected, psycopg2.errors.LockNotAvailable) as e:
            letzter = e
            logger.warning(
                "Datenbank-Wanderung: Sperrkonflikt im {}. Anlauf, neuer Versuch in {}s "
                "({})", versuch, versuch, type(e).__name__,
            )
            import time
            time.sleep(versuch)
    raise letzter  # type: ignore[misc]


def _init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Begrenzt jede einzelne Sperre in dieser Sitzung, siehe oben.
            cur.execute(f"SET lock_timeout = '{_MIGRATION_LOCK_TIMEOUT}'")
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
            # Both columns nullable: NULL means "diagnosis not yet completed".
            # The full CEFR ladder A1..C2. An earlier version collapsed everything
            # above B1 into "B1+"; the scale now runs the whole ladder so the
            # adaptive chat can pitch every level, not only "needs support" vs not.
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_level TEXT CHECK (language_level IN ('A1','A2','B1','B2','C1','C2'))")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language_level_set_at TIMESTAMP WITH TIME ZONE")
            # Migration: the five per-skill scores are gone. Only the result screen
            # ever showed them, and a model that forgot one failed the whole grading
            # turn and cost a repair call, so the column goes with them.
            cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS language_level_skill_scores")
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
            # Eine eigene Rolle ist ein Name und eine Liste von Rechte-Schluesseln
            # aus src/permissions_registry.py. Vorher waren es zwei Sonderfelder
            # (aia_access, allowed_tools), die nur zwei der drei Rechtegruppen
            # abbilden konnten und den Adminbereich gar nicht.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_roles (
                    id            SERIAL PRIMARY KEY,
                    name          TEXT NOT NULL UNIQUE,
                    permissions   JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "ALTER TABLE custom_roles ADD COLUMN IF NOT EXISTS permissions "
                "JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
            # Zwei Umzuege hintereinander, beide laufen nur auf alten Datenbanken
            # und beide sind daran erkennbar, dass die jeweils alte Spalte noch da
            # ist. Auf einer frischen Datenbank passiert hier nichts.
            #
            # Erst der alte Umzug aus Commit c2a6bbd: aus dem Ja-Nein-Feld
            # `allow_aia` wurde das dreiwertige `aia_access`. Ohne diesen Schritt
            # verloere eine sehr alte Datenbank ihre Zugriffsstufe.
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'custom_roles'
                          AND column_name = 'allow_aia'
                    ) THEN
                        ALTER TABLE custom_roles ADD COLUMN IF NOT EXISTS aia_access
                            TEXT NOT NULL DEFAULT 'none';
                        UPDATE custom_roles SET aia_access = 'read' WHERE allow_aia = TRUE;
                        ALTER TABLE custom_roles DROP COLUMN allow_aia;
                    END IF;
                END $$;
            """)
            # Dann der neue: aus aia_access und allowed_tools werden Schluessel.
            # 'edit' war die einzige Stufe, die wirklich mehr erlaubt hat, naemlich
            # eigene Workspaces. Lesen ueber einen geteilten Link hatte ohnehin
            # jeder. Danach fallen beide Spalten weg, denn zwei Wahrheiten ueber
            # dasselbe Recht waeren schlimmer als ein Umzug.
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'custom_roles'
                          AND column_name = 'allowed_tools'
                    ) THEN
                        UPDATE custom_roles SET permissions = (
                            SELECT COALESCE(jsonb_agg(k), '[]'::jsonb) FROM (
                                SELECT 'aia.use'::text AS k
                                UNION ALL
                                SELECT 'aia.workspace.create'
                                    WHERE COALESCE(custom_roles.aia_access, '') = 'edit'
                                UNION ALL
                                SELECT 'tools.' || value
                                    FROM jsonb_array_elements_text(custom_roles.allowed_tools)
                            ) AS m
                        )
                        WHERE permissions = '[]'::jsonb;
                        ALTER TABLE custom_roles DROP COLUMN allowed_tools;
                        ALTER TABLE custom_roles DROP COLUMN IF EXISTS aia_access;
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
            # Einladungen sind der Zugang ohne SSO und verschwinden mit ihm wieder.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS invites (
                    id             SERIAL PRIMARY KEY,
                    token          TEXT NOT NULL UNIQUE,
                    email          TEXT NOT NULL,
                    uid            TEXT NOT NULL,
                    role           TEXT NOT NULL DEFAULT 'user',
                    custom_role_id INTEGER,
                    created_by     INTEGER,
                    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
                    expires_at     TIMESTAMP NOT NULL,
                    used_at        TIMESTAMP
                )
            """)
            # Wer eingeladen hat, darf verschwinden, die Einladung bleibt.
            cur.execute("ALTER TABLE invites ALTER COLUMN created_by DROP NOT NULL")
            cur.execute("CREATE INDEX IF NOT EXISTS invites_email_idx ON invites (LOWER(email))")
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

            # Der Zaehler fuer die Statistik.
            #
            # Warum eine eigene Tabelle: aus `jobs` faellt pro Nutzer alles ueber
            # dem Vorrat wieder heraus (siehe jobs/repository/_retention.py). Eine
            # Statistik "ueber die ganze Zeit" waere damit keine, sondern eine
            # ueber die Reste. Hier wird jeder Auftrag beim Abschluss genau einmal
            # hochgezaehlt und nie wieder geloescht.
            #
            # Eine Zeile fasst Tag, Stunde, Werkzeug und Ausgang zusammen. Daraus
            # faellt alles heraus, was der Statistikbereich braucht: Verlauf je
            # Monat, Wochentag mal Stunde, Erfolgsquote je Werkzeug. Die Stunde
            # steht in Ortszeit, weil die Frage "wann ist was los" eine Frage nach
            # dem Arbeitstag ist und nicht nach UTC.
            #
            # Groesse: hoechstens 24 * 9 Werkzeuge * 2 Ausgaenge Zeilen am Tag,
            # in echt ein Bruchteil davon, weil die meisten Felder leer bleiben.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS job_counts (
                    day       DATE     NOT NULL,
                    hour      SMALLINT NOT NULL,
                    tool      TEXT     NOT NULL,
                    status    TEXT     NOT NULL,
                    runs      INTEGER  NOT NULL DEFAULT 0,
                    seconds   BIGINT   NOT NULL DEFAULT 0,
                    PRIMARY KEY (day, hour, tool, status)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_counts_day
                ON job_counts(day)
            """)

            # Wer wann da war. Eine Zeile je Nutzer und Stunde, mehr nicht:
            # daraus faellt "wie viele waren an dem Tag da" genauso heraus wie
            # die Verteilung ueber den Tag, und die Bindung ueber die Zahl der
            # Tage mit Anwesenheit.
            #
            # Warum nicht aus den Auftraegen ableiten: wer nur Uebungen macht
            # oder ein PDF liest, startet nie einen Auftrag und waere unsichtbar.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_presence (
                    user_id INTEGER  NOT NULL,
                    day     DATE     NOT NULL,
                    hour    SMALLINT NOT NULL,
                    PRIMARY KEY (user_id, day, hour)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_presence_day
                ON user_presence(day)
            """)

            # Einmalig nachtragen, was noch in `jobs` steht. Das holt die
            # Geschichte nicht zurueck, die die Aufbewahrung schon entfernt hat,
            # aber es startet nicht bei null. Laeuft genau einmal: ein zweiter
            # Lauf wuerde alles doppelt zaehlen, deshalb der Merker.
            # `settings` entsteht erst weiter unten. Auf einer leeren Datenbank
            # gibt es ohnehin nichts nachzutragen, dann faellt der Block aus.
            if _table_exists(cur, "settings"):
                cur.execute("SELECT value FROM settings WHERE key = 'job_counts_backfill_done'")
                nachtragen = not cur.fetchone()
            else:
                nachtragen = False
            if nachtragen:
                cur.execute("""
                    INSERT INTO job_counts (day, hour, tool, status, runs, seconds)
                    SELECT (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date,
                           EXTRACT(HOUR FROM (completed_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')),
                           tool, status, COUNT(*),
                           COALESCE(SUM(GREATEST(0, EXTRACT(EPOCH FROM (completed_at - COALESCE(
                               CASE WHEN tool IN ('screencast_render', 'screencast_translate')
                                    THEN render_started_at END,
                               started_at, completed_at)))))::bigint, 0)
                    FROM jobs
                    WHERE status IN ('success', 'failed') AND completed_at IS NOT NULL
                    GROUP BY 1, 2, tool, status
                    ON CONFLICT (day, hour, tool, status) DO NOTHING
                """)
                cur.execute(
                    """INSERT INTO settings (key, value) VALUES ('job_counts_backfill_done', 'true')
                       ON CONFLICT (key) DO UPDATE SET value = 'true'"""
                )

            # Dasselbe fuer die Zeile beim Anlegen. Sie kam spaeter dazu, und
            # ohne sie faehrt die Statistik nur die Auftraege, die einen
            # Endzustand erreicht haben. Ebenfalls genau einmal.
            if _table_exists(cur, "settings"):
                cur.execute("SELECT value FROM settings WHERE key = 'job_counts_started_backfill_done'")
                nachtragen = not cur.fetchone()
            else:
                nachtragen = False
            if nachtragen:
                cur.execute("""
                    INSERT INTO job_counts (day, hour, tool, status, runs, seconds)
                    SELECT (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date,
                           EXTRACT(HOUR FROM (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')),
                           tool, 'started', COUNT(*), 0
                    FROM jobs
                    GROUP BY 1, 2, tool
                    ON CONFLICT (day, hour, tool, status) DO NOTHING
                """)
                cur.execute(
                    """INSERT INTO settings (key, value) VALUES ('job_counts_started_backfill_done', 'true')
                       ON CONFLICT (key) DO UPDATE SET value = 'true'"""
                )
            cur.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS username")
            # Locale at job-creation time, used by Celery workers (no HTTP context)
            # to localize error_message strings on timeout / provider failure.
            cur.execute(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS creator_locale TEXT NOT NULL DEFAULT 'de' "
                "CHECK (creator_locale IN ('de', 'en'))"
            )
            # Migration: die Frist von sieben Tagen ist raus, es zaehlt nur noch der
            # Vorrat der letzten Auftraege. Ohne dieses Zuruecksetzen behielten alle
            # Bestandsjobs ihr altes Ablaufdatum und waeren trotzdem verschwunden.
            # Die Spalte bleibt stehen, sie wird nur nicht mehr befuellt.
            cur.execute("UPDATE jobs SET expires_at = NULL WHERE expires_at IS NOT NULL")
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
            # Per-workspace setting: the ONE language the owner translates transcripts into
            # (short ISO code, see i18n.TRANSCRIPT_LANGUAGES). Source is the Whisper-detected
            # media language; English is the default target.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS transcript_target_lang TEXT NOT NULL DEFAULT 'en'"
            )
            # Per-workspace setting: the language the CEFR chat diagnosis is held in
            # (short ISO code, see i18n.TRANSCRIPT_LANGUAGES). Independent of the
            # transcript target — a workspace can hold French sources while the
            # diagnosis stays in the language the course is taught in.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS diagnosis_language TEXT NOT NULL DEFAULT 'de'"
            )
            # Per-workspace setting: whether the Sprachtrainer (flashcards, vocabulary
            # cloze, grammar exercise) is offered here at all. The owner decides
            # this once for everyone; it used to be a per-reader checkbox, which meant
            # a course could not rely on the trainer being there. Off by default, and
            # only effective while the system-wide switch is on (see _common settings).
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS language_training_active BOOLEAN NOT NULL DEFAULT FALSE"
            )
            # Owner-managed pinned note shown above the sources list. Plain text + structured links.
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS staff_note_text TEXT"
            )
            cur.execute(
                "ALTER TABLE aia_workspaces ADD COLUMN IF NOT EXISTS staff_note_links JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
            # Short-lived per-workspace filter for the grammar exercise catalogue.
            # Dropped again: the catalogue is the same everywhere and the learner
            # picks the type when creating a set, so there was nothing to configure.
            cur.execute("ALTER TABLE aia_workspaces DROP COLUMN IF EXISTS grammar_types")
            # Legacy per-workspace summary toggle: summaries were removed entirely
            # (pgvector-only retrieval), so drop the now-meaningless column.
            cur.execute("ALTER TABLE aia_workspaces DROP COLUMN IF EXISTS summary_mode")
            # Legacy transcript translation mode (off/auto/manual): translation now
            # always runs on click in the transcript panel, so there is nothing left
            # to configure.
            cur.execute("ALTER TABLE aia_workspaces DROP COLUMN IF EXISTS transcript_translation_mode")
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
                    role           TEXT NOT NULL DEFAULT 'student',
                    UNIQUE (workspace_id, user_id)
                )
            """)
            # Migration: add link_id column if table already existed without it
            cur.execute("ALTER TABLE aia_enrollments ADD COLUMN IF NOT EXISTS link_id INTEGER REFERENCES aia_access_links(id) ON DELETE SET NULL")
            # A member is either a learner or a tutor. Tutors manage the workspace
            # with the same rights as its owner, minus inviting: only the owner
            # decides who gets in and who becomes a tutor.
            #
            # The role sits on the enrollment, never on the link. A link that
            # granted full rights would be a credential that leaks by being
            # forwarded, and nobody could tell it had spread. Promotion instead
            # targets a named person the owner picked from the participant list.
            cur.execute(
                "ALTER TABLE aia_enrollments ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'student'"
            )
            cur.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'aia_enrollments_role_check'
                    ) THEN
                        ALTER TABLE aia_enrollments
                            ADD CONSTRAINT aia_enrollments_role_check
                            CHECK (role IN ('student', 'tutor'));
                    END IF;
                END $$
            """)
            # Links never carried a role in a released version; drop the short-lived column.
            cur.execute("ALTER TABLE aia_access_links DROP CONSTRAINT IF EXISTS aia_access_links_role_check")
            cur.execute("ALTER TABLE aia_access_links DROP COLUMN IF EXISTS role")
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
            # One enrollment per person and workspace. The rule used to include
            # link_id, which made it toothless: link_id is ON DELETE SET NULL, and
            # an empty value never equals another empty value, so a course that
            # replaced its link collected a second enrollment for the same person
            # and stood twice in their list.
            #
            # Existing duplicates are merged first, otherwise the rule could not be
            # put in place at all. The oldest enrollment stays, with its own expiry:
            # a later link must not silently extend an access that was meant to run
            # out. Its role wins if any of the merged rows was a tutor, because
            # rights belong to the person, and messages move along so no chat is
            # left hanging on a row that is about to disappear.
            cur.execute("""
                UPDATE aia_enrollments k
                SET role = 'tutor'
                FROM aia_enrollments t
                WHERE t.workspace_id = k.workspace_id
                  AND t.user_id = k.user_id
                  AND t.role = 'tutor'
                  AND k.role <> 'tutor'
            """)
            # aia_messages entsteht weiter unten. Auf einer leeren Datenbank gibt es
            # keine Nachrichten umzuhaengen, dort faellt der Schritt einfach weg.
            if _table_exists(cur, "aia_messages"):
                cur.execute("""
                    UPDATE aia_messages m
                    SET enrollment_id = behalten.id
                    FROM aia_enrollments e
                    JOIN (
                        SELECT DISTINCT ON (workspace_id, user_id) id, workspace_id, user_id
                        FROM aia_enrollments
                        ORDER BY workspace_id, user_id, created_at, id
                    ) behalten
                      ON behalten.workspace_id = e.workspace_id
                     AND behalten.user_id = e.user_id
                    WHERE m.enrollment_id = e.id
                      AND e.id <> behalten.id
                """)
            cur.execute("""
                DELETE FROM aia_enrollments e
                USING (
                    SELECT DISTINCT ON (workspace_id, user_id) id, workspace_id, user_id
                    FROM aia_enrollments
                    ORDER BY workspace_id, user_id, created_at, id
                ) behalten
                WHERE e.workspace_id = behalten.workspace_id
                  AND e.user_id = behalten.user_id
                  AND e.id <> behalten.id
            """)
            cur.execute(
                "ALTER TABLE aia_enrollments "
                "DROP CONSTRAINT IF EXISTS aia_enrollments_workspace_id_user_id_link_id_key"
            )
            cur.execute("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'aia_enrollments_workspace_id_user_id_key'
                    ) THEN
                        ALTER TABLE aia_enrollments
                            ADD CONSTRAINT aia_enrollments_workspace_id_user_id_key
                            UNIQUE (workspace_id, user_id);
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
            # Migration: how the text recognition (OCR) went for this source. NULL when
            # the document had no OCR candidate page at all, so there is nothing to
            # say about it. JSON shape is ``{"enabled": bool, "done": int, "open": [int]}``
            # where "open" lists the pages that carry no OCR text - because OCR was off,
            # because the service dropped them, or because the run gave up. A failed OCR
            # never fails the source any more, it only shows up here.
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS ocr_info JSONB
            """)
            # Migration: per-source DOC SUMMARY (one compact summary built at ingest,
            # map-reduce over chunks). Used for GENERIC/overview answers. NULL until
            # built; a source is only set 'ready' once its summary exists.
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS summary TEXT
            """)
            # Kapitel gliedern die Quellenliste eines Kursraums. Rein zur
            # Uebersicht: welche Quellen der Chat bekommt, entscheidet weiterhin
            # allein der Haken an der Datei.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_chapters (
                    id           SERIAL PRIMARY KEY,
                    uuid         TEXT NOT NULL UNIQUE,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    name         TEXT NOT NULL,
                    position     INTEGER NOT NULL DEFAULT 0,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_aia_chapters_workspace
                ON aia_chapters (workspace_id, position)
            """)
            # SET NULL statt CASCADE: ein geloeschtes Kapitel darf keine Quelle
            # mitnehmen, die Dateien rutschen zurueck nach "Ohne Kapitel".
            cur.execute("""
                ALTER TABLE aia_sources ADD COLUMN IF NOT EXISTS chapter_id INTEGER
                    REFERENCES aia_chapters(id) ON DELETE SET NULL
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
            # Quelle + Seite fuer die Beleg-Suche nach einer Chat-Antwort: die schraenkt
            # auf die Seiten ein, die das Modell wirklich gelesen hat (siehe
            # chunks._seen_pages_filter). Ohne diesen Index findet Postgres jene paar
            # Dutzend Zeilen nur ueber den vollen Durchlauf und der Filter bringt statt
            # 62 -> 6 ms nur 62 -> 40 ms je Antwortsatz. Die Spaltenreihenfolge zaehlt:
            # source_id steht vorn, weil eine Medienquelle OHNE Seitenbedingung gesucht
            # wird (dort belegt eine Zeitmarke, keine Seite).
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_source_page
                ON aia_chunks (source_id, page_number)
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
            # Zielsprache der Auswahlleisten-Übersetzung, je Person und Modul.
            # Englisch als Standard, weil das die Sprache ist, in die am
            # häufigsten übersetzt wird. Codes aus i18n.TRANSCRIPT_LANGUAGES.
            cur.execute("ALTER TABLE aia_user_settings ADD COLUMN IF NOT EXISTS popup_translate_lang TEXT NOT NULL DEFAULT 'en'")
            # Eigene Entscheidung je Person und Kurs, ob der freigegebene
            # Sprachtrainer angezeigt wird. Steht auch im CREATE TABLE, hier für
            # Datenbanken, die davor angelegt wurden.
            cur.execute("ALTER TABLE aia_user_settings ADD COLUMN IF NOT EXISTS language_training_active BOOLEAN NOT NULL DEFAULT FALSE")
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
            # Grammatikthemen. Steht VOR dem Vorrat, weil dessen `topic_id` hierher
            # zeigt: eine Fremdschluessel-Spalte laesst sich nicht auf eine Tabelle
            # legen, die es noch nicht gibt. Auf einer Datenbank, die die Tabelle schon
            # hatte, faellt die Reihenfolge nicht auf, auf einer aelteren bricht der
            # ganze Start ab. Regel, Beispiele und Grundstock stehen weiter unten, die
            # brauchen die Reihenfolge nicht.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_grammar_topics (
                    id           SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    name         TEXT NOT NULL,
                    created_by   INTEGER,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # ─── Exercise pool ──────────────────────────────────
            # Aufgaben werden nicht mehr bei jedem Klick neu erzeugt. Was einmal
            # entstanden ist, liegt hier und steht allen im Kursraum offen. Wer
            # Aufgaben anfordert, bekommt zuerst das, was schon da ist und was er
            # selbst noch nicht hatte; nur der Fehlbetrag kostet einen Modellaufruf.
            # Der Vorrat waechst als Nebenprodukt der Nutzung, es gibt keinen
            # Bau-Auftrag.
            #
            # Ein Vorrat je Quelle, Werkzeug UND Sprachniveau: dieselbe Sache fuer A1
            # und fuer C1 formuliert sind zwei verschiedene Aufgaben.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_exercise_pool (
                    id          SERIAL PRIMARY KEY,
                    source_id   INTEGER NOT NULL
                                  REFERENCES aia_sources(id) ON DELETE CASCADE,
                    tool        TEXT NOT NULL,
                    level       TEXT,
                    front       TEXT NOT NULL,
                    back        TEXT NOT NULL,
                    back_en     TEXT,
                    options     JSONB,
                    correct_idx INTEGER,
                    explanation TEXT,
                    source_label TEXT,
                    page_number INTEGER,
                    start_time  REAL,
                    sources     JSONB,
                    extras      JSONB,
                    fingerprint TEXT NOT NULL,
                    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Der Vorrat traegt dieselben Felder wie eine Aufgabe im Satz, damit ein
            # Verweis dorthin nichts verliert. Nachtraeglich ergaenzte Spalten stehen
            # hier, sonst bekommt sie eine bestehende Installation nie.
            cur.execute("ALTER TABLE aia_exercise_pool ADD COLUMN IF NOT EXISTS back_en TEXT")
            # Die Grammatik-Uebung haengt nicht nur an der Quelle, sondern am gewaehlten
            # Thema: aus demselben Text entsteht eine Passiv- oder eine Konjunktiv-Aufgabe.
            # Ihr Vorrat trennt deshalb zusaetzlich nach Thema. Bei allen anderen
            # Werkzeugen bleibt die Spalte leer.
            cur.execute(
                "ALTER TABLE aia_exercise_pool ADD COLUMN IF NOT EXISTS topic_id INTEGER "
                "REFERENCES aia_grammar_topics(id) ON DELETE CASCADE"
            )
            # Welche Darreichungsform eine Grammatik-Aufgabe hat: Umformen, Luecke
            # fuellen, Richtig oder falsch, Ankreuzen. Nur so kann der Vorrat eine
            # Formatauswahl bedienen, statt blind auszuliefern, was gerade daliegt.
            # Bei allen anderen Werkzeugen bleibt die Spalte leer. Altbestand hat sie
            # ebenfalls leer und faellt damit bei einer Auswahl durch den Filter, was
            # richtig ist: ausliefern wuerde die Auswahl brechen.
            cur.execute("ALTER TABLE aia_exercise_pool ADD COLUMN IF NOT EXISTS kind TEXT")
            # Zwei NULL gelten in Postgres nicht als gleich, ein gewoehnlicher
            # UNIQUE ueber `level` wuerde im niveaulosen Vorrat also jeden Doppler
            # durchlassen. COALESCE macht daraus einen vergleichbaren Wert.
            # Der alte Index kannte das Thema noch nicht und wuerde zwei Aufgaben zum
            # selben Satz aus verschiedenen Themen faelschlich als Doppler abweisen.
            cur.execute("DROP INDEX IF EXISTS uq_exercise_pool_item")
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_pool_entry "
                "ON aia_exercise_pool "
                "(source_id, tool, COALESCE(level, ''), COALESCE(topic_id, 0), fingerprint)"
            )
            cur.execute("DROP INDEX IF EXISTS idx_exercise_pool_lookup")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_exercise_pool_find "
                "ON aia_exercise_pool (source_id, tool, level, topic_id)"
            )
            # Ein Satz zeigt auf seine Vorratsaufgaben, statt sie zu kopieren. Alte
            # Zeilen tragen weiter ihren eigenen Inhalt und bleiben lesbar, deshalb
            # ist die Spalte nullable und es gibt keine Wanderung des Altbestands.
            cur.execute(
                "ALTER TABLE aia_exercise_items "
                "ADD COLUMN IF NOT EXISTS pool_item_id INTEGER "
                "REFERENCES aia_exercise_pool(id) ON DELETE SET NULL"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_exercise_items_pool "
                "ON aia_exercise_items (pool_item_id)"
            )
            # Das Hoer- und Leseverstehen wurde am 2026-08-10 abgeschafft. Der Code kennt
            # das Werkzeug nicht mehr, seine Zeilen aber schon: sie stuenden weiter in der
            # Statistik und in den letzten Aktivitaeten, ohne dass sich noch einer
            # aufschlagen liesse. Deshalb hier einmal weg.
            #
            # Die Saetze reissen ihre Aufgaben und den Fortschritt per ON DELETE CASCADE
            # mit. Idempotent: danach passt keine Zeile mehr.
            cur.execute("DELETE FROM aia_exercise_sets WHERE tool = 'hoerverstehen'")
            cur.execute("DELETE FROM aia_exercise_pool WHERE tool = 'hoerverstehen'")
            # ─── Vorrat fuer gesprochene Beispielsaetze ─────────
            # Ein Satz kostet vier bis fuenf Sekunden beim Anbieter. Ohne Vorrat zahlt
            # jede Person im Kurs diesen Preis erneut, und dieselbe Person nach jedem
            # Neuladen noch einmal.
            #
            # Der Schluessel ist der SATZ samt Stimme, Anbieter und Tempo, nicht die
            # Karte: zwei Karten mit demselben Beispielsatz teilen sich einen Ton, und
            # ein neu erzeugter Kartensatz greift auf das zu, was ein alter schon
            # gesprochen hat. Haengte er an der Kartennummer, waere er nach jeder
            # Neuerzeugung leer.
            #
            # Der Vorrat gilt fuer alle. Am Ton ist nichts persoenlich, und der Satz
            # steht ohnehin im gemeinsamen Kursmaterial.
            #
            # Der TON steht nicht hier, sondern im Speicher unter aia/speech/. Die
            # Zeile traegt nur, wann er zuletzt gehoert wurde. Genau dafuer wird sie
            # gebraucht: eine Aufbewahrungsregel im Bucket kennt nur das Erstelldatum
            # und wuerde den Satz wegwerfen, den ein Kurs jedes Semester wieder hoert.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_speech_cache (
                    fingerprint  TEXT PRIMARY KEY,
                    bytes        INTEGER NOT NULL,
                    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            # Frueher lagen die MP3s als BYTEA in der Zeile. Sie sind mit den Jahren in
            # jede Sicherung gewandert, obwohl an ihnen nichts wiederherzustellen ist:
            # was fehlt, spricht der Anbieter in fuenf Sekunden neu.
            #
            # Die Altzeilen zeigen nach dem Umzug auf keine Datei mehr und sind damit
            # wertlos. Sie gehen zusammen mit der Spalte, sonst laeuft jede von ihnen
            # noch einmal in einen Fehlgriff in den Speicher. Die Bedingung haelt das
            # auf den einen Start beschraenkt, an dem die Spalte faellt: unbedingt
            # geschrieben wuerde sie den Vorrat bei jedem Neustart leeren.
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_name = 'aia_speech_cache'
                                 AND column_name = 'audio') THEN
                        DELETE FROM aia_speech_cache;
                    END IF;
                END $$
            """)
            cur.execute("ALTER TABLE aia_speech_cache DROP COLUMN IF EXISTS audio")
            # Das naechtliche Aufraeumen sucht nach dem Zeitstempel, nicht nach dem
            # Schluessel.
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_speech_cache_last_used "
                "ON aia_speech_cache (last_used_at)"
            )
            # ─── Context sweep cursors ──────────────────────────
            # Where the last generation run stopped reading inside each of the
            # coverage blocks of ONE source. A source larger than the context budget
            # can never go in whole, so the run has to pick part of it; picking that
            # part at random meant some pages came up over and over while others were
            # structurally unreachable (measured on a 489-page PDF: page 1 appeared
            # once in 30 runs). The cursors turn that draw into a sweep: every run
            # continues where the last one stopped, so the document is covered
            # completely and in the fewest possible runs before anything repeats.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_context_cursors (
                    workspace_id INTEGER NOT NULL
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    source_id    INTEGER NOT NULL
                                   REFERENCES aia_sources(id) ON DELETE CASCADE,
                    tool         TEXT NOT NULL,
                    cursors      JSONB NOT NULL,
                    updated_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (workspace_id, source_id, tool)
                )
            """)
            # The standalone Lückentext tool is gone: its gap sentences were the same
            # multiple-choice exercise under a second name, and they sat in the language
            # area although the gap is a technical term and not a grammar form. The quiz
            # now produces both kinds, so old sets move there rather than being deleted.
            # The UI tells a gap item apart by the ___ marker in `front`, so nothing else
            # has to change for them to keep working.
            # Same for the removed Begriffe-Quiz: it was multiple choice over technical
            # terms, so its sets belong with the quiz rather than being orphaned by a
            # tile that no longer exists.
            cur.execute(
                "UPDATE aia_exercise_sets SET tool = 'quiz' "
                "WHERE tool IN ('lueckentext', 'vokabeltest')"
            )
            # Grammar exercises: a set carries the instruction and the worked example
            # pair, because those are shown once above the sentences instead of being
            # repeated on every item.
            # Grammatikthemen. Sie standen im Code, und ein neues kostete dort einen
            # Eintrag mit Regel, Musterpaar je Sprache und beim Ankreuz-Format noch drei
            # falschen Formen. Für zwei Themen tragbar, für dreissig nicht. Jetzt tippt
            # der Dozent einen Namen und die KI arbeitet den Rest aus.
            #
            # Zwei Tabellen, weil ein Thema nur ein Name ist, Regel und Beispiele aber
            # zusätzlich an der Sprache hängen: "Konjunktiv II" braucht auf Deutsch ein
            # anderes Beispiel als derselbe Kurs auf Englisch. Die Themen-Tabelle selbst
            # steht weiter oben, der Vorrat verweist schon auf sie.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_grammar_topic_specs (
                    id        SERIAL PRIMARY KEY,
                    topic_id  INTEGER NOT NULL
                                REFERENCES aia_grammar_topics(id) ON DELETE CASCADE,
                    language  TEXT NOT NULL,
                    rule      TEXT NOT NULL,
                    examples  JSONB NOT NULL DEFAULT '[]'::jsonb,
                    UNIQUE (topic_id, language)
                )
            """)
            # Die Anweisungszeile je Aufgabenformat, vom Modell formuliert statt aus
            # einer Schablone. Die Schablone setzte den Themennamen stur ein und traf
            # nur saechliche Einzahlwoerter: "Setze den Satz ins Perfekt." geht auf,
            # "Setze den Satz ins Nebensaetze." nicht. Bei acht echten Themen war die
            # Haelfte falsch. Beugung laesst sich nicht schablonisieren, und eine
            # deutsche Grammatikregel im Code braeche bei der naechsten Hochschule.
            # NULL heisst: noch nicht ausgearbeitet. Das wird beim naechsten Benutzen
            # nachgereicht, siehe derive_task_lines. Bis dahin greift die Schablone, die
            # den Namen inzwischen hinter einen Doppelpunkt setzt statt hinter "ins".
            cur.execute(
                "ALTER TABLE aia_grammar_topic_specs ADD COLUMN IF NOT EXISTS task_lines JSONB"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_grammar_topics_workspace "
                "ON aia_grammar_topics(workspace_id)"
            )
            # Grundstock für die Kurse, die es vor der Themen-Tabelle schon gab. Ohne
            # Ausarbeitung: die entsteht beim ersten Benutzen in der jeweiligen Sprache,
            # sonst kostete jeder Kurs acht Modell-Aufrufe, von denen die meisten nie
            # gebraucht werden.
            #
            # GENAU EINMAL, festgehalten in `settings` wie die search_vector-Migration
            # weiter unten. Vorher lief das bei jedem Start und hat jeden fehlenden der
            # acht Namen neu angelegt. Damit war ein gelöschtes "Perfekt" nach dem
            # nächsten Neustart wieder da, und das Entfernen von Themen wäre eine
            # Täuschung. Neue Kurse bekommen ihren Grundstock beim Anlegen über
            # `seed_grammar_topics`, nicht von hier.
            seed_key = "grammar_topics_seeded"
            cur.execute("SELECT value FROM settings WHERE key = %s", (seed_key,))
            row = cur.fetchone()
            if not (row and row[0] == "true"):
                cur.execute("""
                    INSERT INTO aia_grammar_topics (workspace_id, name, created_by)
                    SELECT w.id, s.name, w.user_id
                    FROM aia_workspaces w
                    CROSS JOIN (VALUES ('Passiv Präsens'), ('Passiv mit Modalverb'),
                                       ('Perfekt'), ('Präteritum'), ('Konjunktiv II'),
                                       ('Relativsätze'), ('Nebensätze'),
                                       ('Adjektivdeklination')) AS s(name)
                    WHERE NOT EXISTS (
                        SELECT 1 FROM aia_grammar_topics t
                        WHERE t.workspace_id = w.id AND t.name = s.name
                    )
                """)
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (%s, 'true') "
                    "ON CONFLICT (key) DO UPDATE SET value = 'true'",
                    (seed_key,),
                )
            # Die Textspalte zeigte auf einen Code-Eintrag, den es nicht mehr gibt. Kein
            # Bestandsschutz, wir sind auf dev: die alten Grammatik-Sets gehen mit.
            #
            # NUR EINMAL, nämlich solange die alte Spalte noch da ist. Ohne diese Klammer
            # lief das DELETE bei JEDEM Start und hat frisch erzeugte Sets gleich wieder
            # weggeräumt. Genau so passiert am 2026-08-05.
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'aia_exercise_sets' AND column_name = 'grammar_type'"
            )
            if cur.fetchone():
                cur.execute("DELETE FROM aia_exercise_sets WHERE tool = 'grammatik'")
                cur.execute("ALTER TABLE aia_exercise_sets DROP COLUMN grammar_type")
            cur.execute(
                "ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS grammar_topic_id "
                "INTEGER REFERENCES aia_grammar_topics(id) ON DELETE SET NULL"
            )
            # Die gewaehlten Aufgabenformate der Grammatik-Uebung, als JSON-Liste von
            # Kuerzeln. NULL heisst gemischt, also alle vier, und das ist der
            # Normalfall. Jeder Satz von vor dieser Spalte ist damit richtig
            # eingeordnet, ohne dass etwas gewandert werden muss.
            cur.execute(
                "ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS "
                "grammar_kinds JSONB"
            )
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS instruction TEXT")
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS pattern_front TEXT")
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS pattern_back TEXT")
            # Nur der Wortschatz-Lückentext aus Lernkarten füllt das. Es steht am Satz
            # und nicht nur im Auftrag, weil der Neuversuch eines fehlgeschlagenen
            # Satzes seine Einstellungen aus dieser Zeile liest.
            cur.execute(
                "ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS flashcard_set_id "
                "INTEGER REFERENCES aia_exercise_sets(id) ON DELETE SET NULL"
            )
            # Every source the set was generated from, in the order the learner picked
            # them. source_uuid only ever held the first one, so neither the count nor a
            # stable numbering for the citation chips was recoverable from the row.
            cur.execute("ALTER TABLE aia_exercise_sets DROP COLUMN IF EXISTS source_count")
            cur.execute(
                "ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS "
                "source_uuids JSONB NOT NULL DEFAULT '[]'::jsonb"
            )
            # Sets from before the column keep the one source that was recorded. The rest
            # of their selection is gone and cannot be reconstructed.
            cur.execute(
                "UPDATE aia_exercise_sets SET source_uuids = jsonb_build_array(source_uuid) "
                "WHERE source_uuid IS NOT NULL AND source_uuids = '[]'::jsonb"
            )
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
            # Die Statistik zeigt jeden Durchgang einzeln, dafuer traegt jede Antwort
            # die Nummer ihres Durchgangs. Antworten von vor der Spalte haben keine
            # und bleiben NULL, sie erscheinen als ein Durchgang je Tag.
            cur.execute(
                "ALTER TABLE aia_exercise_progress "
                "ADD COLUMN IF NOT EXISTS run_no INTEGER"
            )
            # The learner profile (per-user weakness tracking) was removed. Adaptivity
            # is the CEFR level and nothing else. Nothing creates or reads
            # aia_learner_weakness or users.learning_profile_enabled any more; both are
            # left in place on existing installs so no data disappears behind an
            # operator's back, and are dropped by hand when they decide to.
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
            # Welcher Glossarbegriff hinter dieser Aufgabe steckt. Nur im Glossar-Weg
            # gefuellt, sonst NULL. Ohne diese Spur laesst sich bei Karteikarten nicht
            # feststellen, welcher Begriff schon dran war: ihre Vorderseite ist eine
            # erzeugte Frage und lautet bei jedem Lauf anders.
            #
            # Der Begriff als Text und nicht die id des Glossareintrags. Ein geloeschter
            # und neu angelegter Eintrag bekaeme eine neue id, der Begriff bliebe aber
            # derselbe, und genau der ist gemeint.
            cur.execute(
                "ALTER TABLE aia_exercise_items ADD COLUMN IF NOT EXISTS glossary_term TEXT"
            )
            # Nachtragung fuer den Altbestand. Bei Lernkarten aus dem Glossar IST die
            # Vorderseite der Begriff, die lassen sich rueckwirkend fuellen. Karteikarten
            # von frueher fangen bei null an, ihre Vorderseite ist eine Frage und der
            # Begriff daraus nicht mehr zu erkennen.
            #
            # `IS NULL` macht den Befehl beim naechsten Start zu einer leeren Aenderung.
            # Auf einer frischen Datenbank trifft er auf keine Zeile, beide Tabellen
            # entstehen weiter oben, also braucht er keine Existenzpruefung.
            cur.execute("""
                UPDATE aia_exercise_items i SET glossary_term = i.front
                FROM aia_exercise_sets s
                WHERE i.set_id = s.id
                  AND s.mode = 'glossary' AND s.tool = 'flashcards'
                  AND i.glossary_term IS NULL AND i.front <> ''
            """)
            # Der Quiz-Vorrat kennt nur die zwei Ankreuz-Arten, seit dem 2026-08-10
            # stellt das Quiz auch Richtig/Falsch. Einmal leeren, sonst bleibt die
            # Aenderung unsichtbar.
            #
            # Der Schritt steht HIER und nicht oben beim abgeschafften Hoerverstehen,
            # obwohl er inhaltlich dorthin gehoert: er schreibt jede Inhaltsspalte
            # zurueck, und start_time, back_en und extras entstehen erst in den drei
            # Zeilen darueber. Auf einer leeren Datenbank brach init_db an genau dieser
            # Stelle ab, gefunden mit scripts/check_fresh_schema.sh.
            _reset_quiz_pool_once(cur)
            # Dieselbe Stelle und derselbe Grund fuer die Grammatik: die Anweisungszeile
            # steckt im Aufgabentext, der Vorrat traegt also die am 2026-08-12 gemeldete
            # Fassung, und ohne dieses Leeren bliebe die Korrektur unsichtbar.
            _reset_grammar_pool_once(cur)
            # The run boundary is gone. The progress ring counted only the answers
            # after this mark, and the browser set it when the learner answered the
            # first card of a session. Interrupting an exercise moved the mark into
            # the middle of the run, and everything answered before it stopped
            # counting. The ring now reads the last answer per card instead, which
            # needs no boundary at all.
            cur.execute("ALTER TABLE aia_exercise_sets DROP COLUMN IF EXISTS last_run_start")
            # Migration: the item count the learner asked for. card_count only says how
            # many were produced, which is 0 on a failed set, so a retry would silently
            # fall back to the default size instead of the one that was picked.
            cur.execute("ALTER TABLE aia_exercise_sets ADD COLUMN IF NOT EXISTS requested_count INTEGER")
            # Migration: drop legacy mastery columns if they exist
            for col in ("correct_streak", "total_attempts", "total_correct"):
                cur.execute(f"ALTER TABLE aia_exercise_items DROP COLUMN IF EXISTS {col}")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aia_schedule_entries (
                    id           SERIAL PRIMARY KEY,
                    -- NULL heisst: der Eintrag gehoert keinem Workspace, sondern nur dem Nutzer.
                    workspace_id INTEGER
                                   REFERENCES aia_workspaces(id) ON DELETE CASCADE,
                    user_id      INTEGER NOT NULL,
                    type         TEXT NOT NULL CHECK (type IN ('deadline', 'termin')),
                    title        TEXT NOT NULL,
                    description  TEXT,
                    due_date     DATE,
                    end_date     DATE,
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
            # Gesetzt heisst: der Termin geht bis zu diesem Tag.
            cur.execute("ALTER TABLE aia_schedule_entries ADD COLUMN IF NOT EXISTS end_date DATE")
            # Bestehende Datenbanken tragen workspace_id noch als NOT NULL.
            cur.execute("ALTER TABLE aia_schedule_entries ALTER COLUMN workspace_id DROP NOT NULL")
            # Wie genau steht das Datum in der Quelle: 'day' ist der Normalfall, 'month'
            # heisst, dort stand nur ein Monat ("im Juli 2026"). due_date traegt dann den
            # Monatsersten als Sortierpunkt, die Ansicht zeigt dafuer keine Tagesnummer.
            cur.execute("ALTER TABLE aia_schedule_entries ADD COLUMN IF NOT EXISTS date_precision TEXT NOT NULL DEFAULT 'day'")
            # Gesetzt heisst: der Termin geht an diesem Tag bis zu dieser Uhrzeit.
            cur.execute("ALTER TABLE aia_schedule_entries ADD COLUMN IF NOT EXISTS end_time TIME")
            # Gesetzt heisst: die Quelle nennt einen Anfang und ausdruecklich KEIN Ende
            # ("ab 15.09. freigeschaltet"). So ein Termin ist nie vorbei, die Ansicht
            # blendet ihn deshalb nie ab.
            cur.execute("ALTER TABLE aia_schedule_entries ADD COLUMN IF NOT EXISTS is_open_ended BOOLEAN NOT NULL DEFAULT FALSE")
            # Drop legacy columns (were single-position; replaced by source_refs array)
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS source_ids")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS raw_quote")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS page_number")
            cur.execute("ALTER TABLE aia_schedule_entries DROP COLUMN IF EXISTS start_time")
            # Bis hierhin trug eine Mindmap keinen eigenen Namen, die Liste zeigte den
            # Wurzelknoten aus dem JSON. Mit der Spalte kann sie umbenannt werden und
            # bekommt beim Erzeugen einen Titel aus ihrem Inhalt.
            cur.execute("ALTER TABLE aia_mindmaps ADD COLUMN IF NOT EXISTS title TEXT")
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

            # ─── Modellvermessung ─────────────────────────────────────────────
            # Was ein Modell vertraegt, einmal gemessen statt im Admin geraten:
            # Fenstergroesse in Token, ob es vor der Antwort denkt, und welcher
            # Schalter dieses Denken abstellt. Gemessen an 16 Modellen
            # reichen die Fenster von 20.080 bis 1.048.576 Token, eine feste
            # Zeichenzahl fuer alle kann es also gar nicht geben.
            #
            # source sagt, wie verlaesslich die Zahl ist: "gemessen" (Anbieter hat
            # sie genannt), "unbekannt" (er schweigt, dann steht dort 0 und es wird
            # nichts gedeckelt), "gelernt" (aus einer echten Absage im Betrieb
            # nachtraeglich korrigiert), "gesetzt" (der Admin hat sie eingetragen).
            cur.execute("""
                CREATE TABLE IF NOT EXISTS model_limits (
                    provider_id   INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
                    model_name    TEXT NOT NULL,
                    window_tokens INTEGER NOT NULL,
                    source        TEXT NOT NULL,
                    thinks        BOOLEAN NOT NULL DEFAULT FALSE,
                    think_off     TEXT NOT NULL DEFAULT '',
                    updated_at    TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (provider_id, model_name)
                )
            """)

            # Bis 20.08.2026 wurde ein schweigender Anbieter mit 32.768 Token geraten.
            # Die Zahl sah aus wie eine Messung, war aber keine. Idempotent.
            cur.execute("""
                UPDATE model_limits SET window_tokens = 0, source = 'unbekannt'
                 WHERE source = 'geraten'
            """)

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

