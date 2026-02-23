import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.database import get_connection

STORAGE_ROOT = Path("/app/storage")


def save_file(user_id: int, filename: str, data: bytes) -> str:
    """Save *data* under /app/storage/{user_id}/{uuid}_{filename}.

    Returns the full file path as a string.
    """
    dest_dir = STORAGE_ROOT / str(user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4()}_{filename}"
    file_path = dest_dir / stored_filename
    file_path.write_bytes(data)
    return str(file_path)


def get_file(file_path: str) -> bytes:
    """Return the raw bytes of the file at *file_path*."""
    return Path(file_path).read_bytes()


def delete_file(file_path: str) -> None:
    """Delete the file at *file_path* (no-op if it does not exist)."""
    path = Path(file_path)
    if path.exists():
        path.unlink()


def cleanup_expired_files() -> int:
    """Delete files whose job's expires_at has passed.

    Returns the number of files deleted.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    deleted = 0

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, file_path FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        ).fetchall()

        for row in rows:
            delete_file(row["file_path"])
            conn.execute("DELETE FROM jobs WHERE id = ?", (row["id"],))
            deleted += 1

        conn.commit()

    return deleted
