import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.database import get_connection

STORAGE_ROOT = Path("/app/storage")

# Shared directories (accessible by both backend and celery-worker containers)
QUEUE_DIR = STORAGE_ROOT / "queue"      # uploaded input files
RESULTS_DIR = STORAGE_ROOT / "results"  # output files (MP4, MP3, JSON)
AUDIO_DIR = STORAGE_ROOT / "audio"      # per-slide audio cache


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


# --- Job queue / result storage ---

def save_queue_file(job_uuid: str, ext: str, data: bytes) -> str:
    """Save an uploaded input file to the shared queue directory."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    path = QUEUE_DIR / f"{job_uuid}_input{ext}"
    path.write_bytes(data)
    return str(path)


def save_result_file(job_uuid: str, ext: str, data: bytes) -> str:
    """Save a job output file (MP4, MP3) to the shared results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_uuid}_output{ext}"
    path.write_bytes(data)
    return str(path)


def save_result_json(job_uuid: str, data: dict) -> str:
    """Save a JSON result (e.g. translate output) to the results directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{job_uuid}_result.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def load_result_json(result_path: str) -> dict:
    """Load a JSON result file."""
    return json.loads(Path(result_path).read_text(encoding="utf-8"))


# --- Per-slide audio cache (file-based, shared between backend and worker) ---

def save_audio_cache(audio_id: str, audio_files: list[bytes]) -> str:
    """Save per-slide MP3 bytes to /app/storage/audio/{audio_id}/."""
    audio_dir = AUDIO_DIR / audio_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, data in enumerate(audio_files):
        (audio_dir / f"slide_{i:03d}.mp3").write_bytes(data)
    return audio_id


def get_audio_slide(audio_id: str, slide_index: int) -> bytes | None:
    """Return MP3 bytes for a single slide, or None if not found."""
    path = AUDIO_DIR / audio_id / f"slide_{slide_index:03d}.mp3"
    if path.exists():
        return path.read_bytes()
    return None


def get_audio_slide_count(audio_id: str) -> int:
    """Return the number of cached audio slides for the given audio_id."""
    audio_dir = AUDIO_DIR / audio_id
    if not audio_dir.exists():
        return 0
    return len(list(audio_dir.glob("slide_*.mp3")))


# --- Cleanup ---

def cleanup_expired_files() -> int:
    """Delete files whose job's expires_at has passed.

    Returns the number of files deleted.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    deleted = 0

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, input_path, result_path FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        ).fetchall()

        for row in rows:
            for path_col in (row["input_path"], row["result_path"]):
                if path_col:
                    delete_file(path_col)
            conn.execute("DELETE FROM jobs WHERE id = ?", (row["id"],))
            deleted += 1

        conn.commit()

    return deleted
