import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("/app/data/database.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ldap_username TEXT NOT NULL UNIQUE,
                display_name  TEXT NOT NULL,
                email         TEXT,
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Migration: add email column to existing databases
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Migration: drop old jobs table if it has the old schema (stored_filename column)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if cols and "stored_filename" in cols:
            conn.execute("DROP TABLE jobs")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                job_uuid          TEXT NOT NULL UNIQUE,
                user_id           INTEGER NOT NULL DEFAULT 0,
                tool              TEXT NOT NULL,
                original_filename TEXT NOT NULL DEFAULT '',
                input_path        TEXT,
                result_path       TEXT,
                result_filename   TEXT,
                status            TEXT NOT NULL DEFAULT 'pending',
                error_message     TEXT,
                progress          TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at        TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key        TEXT NOT NULL UNIQUE,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Auto-whitelist admin email so first login works without manual DB edits
        if admin_email and admin_email.strip():
            conn.execute(
                "INSERT OR IGNORE INTO whitelist (email) VALUES (?)",
                (admin_email.strip().lower(),),
            )

        conn.commit()


# --- Users ---

def get_user_by_username(ldap_username: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE ldap_username = ?", (ldap_username,)
        ).fetchone()


def create_user(ldap_username: str, display_name: str, email: str, active: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (ldap_username, display_name, email, active) VALUES (?, ?, ?, ?)",
            (ldap_username, display_name, email, active),
        )
        conn.commit()
        return cur.lastrowid


def update_user(user_id: int, display_name: str, email: str, active: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, email = ?, active = ? WHERE id = ?",
            (display_name, email, active, user_id),
        )
        conn.commit()


# --- Whitelist ---

def get_whitelist_emails() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT email FROM whitelist ORDER BY created_at").fetchall()
        return [row["email"] for row in rows]


def add_to_whitelist(email: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO whitelist (email) VALUES (?)", (email.strip().lower(),)
        )
        conn.commit()


def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM whitelist WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        conn.commit()


def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM whitelist WHERE LOWER(email) = LOWER(?)", (email.strip(),)
        ).fetchone()
        return row is not None


# --- Jobs ---

JOB_RETENTION_HOURS = 24


def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
) -> None:
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_uuid, user_id, tool, original_filename, input_path, expires_at),
        )
        conn.commit()


def get_job(job_uuid: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE job_uuid = ?", (job_uuid,)
        ).fetchone()


def update_job_status(
    job_uuid: str,
    status: str,
    error_message: str | None = None,
    progress: dict | None = None,
) -> None:
    progress_json = json.dumps(progress) if progress is not None else None
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, error_message = ?, progress = ?
            WHERE job_uuid = ?
            """,
            (status, error_message, progress_json, job_uuid),
        )
        conn.commit()


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET result_path = ?, result_filename = ? WHERE job_uuid = ?",
            (result_path, result_filename, job_uuid),
        )
        conn.commit()
