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
            "INSERT OR IGNORE INTO whitelist (email) VALUES (?)", (email,)
        )
        conn.commit()


def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM whitelist WHERE email = ?", (email,))
        conn.commit()


def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM whitelist WHERE email = ?", (email,)
        ).fetchone()
        return row is not None
