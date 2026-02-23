import sqlite3
from pathlib import Path

DB_PATH = Path("/app/data/database.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ldap_username TEXT NOT NULL UNIQUE,
                display_name  TEXT NOT NULL,
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           INTEGER NOT NULL REFERENCES users(id),
                tool              TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename   TEXT NOT NULL,
                file_path         TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'pending'
                                  CHECK(status IN ('pending', 'processing', 'done', 'error')),
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
        conn.commit()
