import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from src.database import get_connection, update_job_result, delete_job

# --- Local storage paths ---
STORAGE_ROOT = Path("/app/storage")
JOBS_DIR = STORAGE_ROOT / "jobs"

# --- S3 config (read once at import time) ---
_S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
_S3_BUCKET = os.environ.get("S3_BUCKET", "kis")
USE_S3 = bool(_S3_ENDPOINT)


@lru_cache(maxsize=1)
def _s3():
    import boto3
    from botocore.client import Config
    return boto3.client(
        "s3",
        endpoint_url=_S3_ENDPOINT,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", ""),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", ""),
        config=Config(signature_version="s3v4"),
    )


def init_storage() -> None:
    """Ensure storage is ready. For S3: create bucket if missing. For local: create dirs."""
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            _s3().head_bucket(Bucket=_S3_BUCKET)
        except ClientError:
            _s3().create_bucket(Bucket=_S3_BUCKET)
    else:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)


# --- Generic file operations ---

def save_file(user_id: int, filename: str, data: bytes) -> str:
    stored_filename = f"{uuid.uuid4()}_{filename}"
    if USE_S3:
        key = f"users/{user_id}/{stored_filename}"
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    dest_dir = STORAGE_ROOT / str(user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / stored_filename
    file_path.write_bytes(data)
    return str(file_path)


def get_file(file_path: str) -> bytes:
    if USE_S3:
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=file_path)
        return resp["Body"].read()
    return Path(file_path).read_bytes()


def file_exists(file_path: str) -> bool:
    """Check whether a stored file actually exists (S3 HEAD or local stat).

    For S3: returns False ONLY on a genuine 404/NoSuchKey response.
    Any other error (network issue, S3 unavailable, permissions) returns True
    so that transient failures never accidentally trigger job deletion.
    """
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            _s3().head_object(Bucket=_S3_BUCKET, Key=file_path)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                return False
            # Server error, permission error, network issue — assume file exists
            return True
        except Exception:
            # Connection error, timeout, etc. — assume file exists
            return True
    return Path(file_path).exists()


def job_file_exists(job_uuid: str, filename: str) -> bool:
    """Check whether a specific file inside a job's folder still exists."""
    return file_exists(_job_key(job_uuid, filename))


def delete_file(file_path: str) -> None:
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=file_path)
        return
    path = Path(file_path)
    if path.exists():
        path.unlink()


# --- Job folder helpers ---
#
# Layout:
#   jobs/YYYY-MM-DD_HH-MM-SS_{uuid}/input{ext}
#   jobs/YYYY-MM-DD_HH-MM-SS_{uuid}/output{ext}
#   jobs/YYYY-MM-DD_HH-MM-SS_{uuid}/result.json
#   jobs/YYYY-MM-DD_HH-MM-SS_{uuid}/meta.json
#   jobs/YYYY-MM-DD_HH-MM-SS_{uuid}/audio/slide_000.mp3

def _job_folder_name(job_uuid: str) -> str:
    """Return the folder name for a job: 'YYYY-MM-DD_HH-MM-SS_{uuid}'."""
    import psycopg2.extras
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT created_at FROM jobs WHERE job_uuid = %s", (job_uuid,))
            row = cur.fetchone()
    if row and row["created_at"]:
        ts = row["created_at"]
        iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        date_part = iso[:10]
        time_part = iso[11:19].replace(":", "-")
        return f"{date_part}_{time_part}_{job_uuid}"
    return job_uuid  # fallback if job not yet in DB


def _job_key(job_uuid: str, filename: str) -> str:
    """S3 key for a file inside a job's folder."""
    return f"jobs/{_job_folder_name(job_uuid)}/{filename}"


def _job_dir(job_uuid: str) -> Path:
    """Local filesystem directory for a job."""
    return JOBS_DIR / _job_folder_name(job_uuid)


# --- Job file I/O ---

def save_queue_file(job_uuid: str, ext: str, data: bytes) -> str:
    key = _job_key(job_uuid, f"input{ext}")
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = _job_dir(job_uuid)
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"input{ext}"
    path.write_bytes(data)
    return str(path)


def save_job_file(job_uuid: str, filename: str, data: bytes) -> str:
    """Save an arbitrary named file into the job's folder."""
    key = _job_key(job_uuid, filename)
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = _job_dir(job_uuid)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / filename).write_bytes(data)
    return str(job_dir / filename)


def get_job_file(job_uuid: str, filename: str) -> bytes:
    """Read an arbitrary named file from a job's folder."""
    if USE_S3:
        return get_file(_job_key(job_uuid, filename))
    return (_job_dir(job_uuid) / filename).read_bytes()


def save_result_file(job_uuid: str, ext: str, data: bytes) -> str:
    key = _job_key(job_uuid, f"output{ext}")
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = _job_dir(job_uuid)
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"output{ext}"
    path.write_bytes(data)
    return str(path)


def save_result_json(job_uuid: str, data: dict) -> str:
    content = json.dumps(data).encode()
    key = _job_key(job_uuid, "result.json")
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return key
    job_dir = _job_dir(job_uuid)
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "result.json"
    path.write_bytes(content)
    return str(path)


def save_result_meta(job_uuid: str, data: dict) -> None:
    """Save a meta.json file for a job (subtitles, audio info, etc.)."""
    content = json.dumps(data).encode()
    key = _job_key(job_uuid, "meta.json")
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return
    job_dir = _job_dir(job_uuid)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "meta.json").write_bytes(content)


def load_result_meta(job_uuid: str) -> dict | None:
    """Load the meta.json for a job. Returns None if not found."""
    key = _job_key(job_uuid, "meta.json")
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError:
            return None
    meta_path = _job_dir(job_uuid) / "meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


@contextmanager
def open_input_file(input_path: str, suffix: str = ""):
    """Yields a local filesystem path for the input file.
    With S3: downloads to a temp file (auto-deleted after). With local: yields path directly.
    """
    if USE_S3:
        data = _s3().get_object(Bucket=_S3_BUCKET, Key=input_path)["Body"].read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            yield tmp_path
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        yield input_path


def load_result_json(result_path: str) -> dict:
    if USE_S3:
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=result_path)
        return json.loads(resp["Body"].read())
    return json.loads(Path(result_path).read_text(encoding="utf-8"))


# --- Per-slide audio cache ---

def save_audio_cache(job_uuid: str, audio_files: list[bytes]) -> None:
    """Save per-slide MP3 files under the job's folder."""
    if USE_S3:
        for i, data in enumerate(audio_files):
            key = _job_key(job_uuid, f"audio/slide_{i:03d}.mp3")
            _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return
    audio_dir = _job_dir(job_uuid) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, data in enumerate(audio_files):
        (audio_dir / f"slide_{i:03d}.mp3").write_bytes(data)


def get_audio_slide(job_uuid: str, slide_index: int) -> bytes | None:
    if USE_S3:
        from botocore.exceptions import ClientError
        key = _job_key(job_uuid, f"audio/slide_{slide_index:03d}.mp3")
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError:
            return None
    path = _job_dir(job_uuid) / "audio" / f"slide_{slide_index:03d}.mp3"
    if path.exists():
        return path.read_bytes()
    return None


def get_audio_slide_count(job_uuid: str) -> int:
    if USE_S3:
        prefix = _job_key(job_uuid, "audio/")
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        return resp.get("KeyCount", 0)
    audio_dir = _job_dir(job_uuid) / "audio"
    if not audio_dir.exists():
        return 0
    return len(list(audio_dir.glob("slide_*.mp3")))


def get_all_audio_slides(job_uuid: str) -> list[tuple[str, bytes]]:
    """Fetch all per-slide MP3s in parallel (S3) or sequentially (local).

    Returns a sorted list of (filename, data) tuples.
    """
    if USE_S3:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        prefix = _job_key(job_uuid, "audio/")
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        keys = sorted(obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(".mp3"))
        if not keys:
            return []

        def _fetch(key: str) -> tuple[str, bytes]:
            data = _s3().get_object(Bucket=_S3_BUCKET, Key=key)["Body"].read()
            return (key.split("/")[-1], data)

        results: list[tuple[str, bytes]] = []
        with ThreadPoolExecutor(max_workers=min(len(keys), 10)) as pool:
            futures = {pool.submit(_fetch, key): key for key in keys}
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda x: x[0])

    audio_dir = _job_dir(job_uuid) / "audio"
    if not audio_dir.exists():
        return []
    return [(f.name, f.read_bytes()) for f in sorted(audio_dir.glob("slide_*.mp3"))]


# --- PPTX temp storage (translate → render handoff) ---
#
# Keyed by a random file_id UUID (not a job UUID).
# S3: pptx_tmp/{file_id}.pptx  |  local: /app/storage/screencast_tmp/{file_id}.pptx

_PPTX_TMP_DIR = STORAGE_ROOT / "screencast_tmp"
_PPTX_TMP_PREFIX = "pptx_tmp"


def save_pptx_tmp(file_id: str, data: bytes) -> None:
    """Save a temporary PPTX for the translate→render handoff."""
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=f"{_PPTX_TMP_PREFIX}/{file_id}.pptx", Body=data)
    else:
        _PPTX_TMP_DIR.mkdir(parents=True, exist_ok=True)
        (_PPTX_TMP_DIR / f"{file_id}.pptx").write_bytes(data)


def get_pptx_tmp(file_id: str) -> bytes | None:
    """Load a temporary PPTX. Returns None if not found or expired."""
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=f"{_PPTX_TMP_PREFIX}/{file_id}.pptx")
            return resp["Body"].read()
        except ClientError:
            return None
    path = _PPTX_TMP_DIR / f"{file_id}.pptx"
    return path.read_bytes() if path.exists() else None


def delete_pptx_tmp(file_id: str) -> None:
    """Delete a temporary PPTX after render is complete."""
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=f"{_PPTX_TMP_PREFIX}/{file_id}.pptx")
    else:
        (_PPTX_TMP_DIR / f"{file_id}.pptx").unlink(missing_ok=True)


# --- Per-job folder deletion ---

def delete_job_folder(job_uuid: str) -> None:
    """Delete all files for a job."""
    if USE_S3:
        prefix = f"jobs/{_job_folder_name(job_uuid)}/"
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                _s3().delete_object(Bucket=_S3_BUCKET, Key=obj["Key"])
    else:
        shutil.rmtree(_job_dir(job_uuid), ignore_errors=True)


def clear_tts_audio_cache(job_uuid: str) -> None:
    """Delete all cached TTS audio files for a job (tts_audio/ subfolder).

    Called before re-rendering so the crash-recovery mechanism does not reuse
    stale audio from a previous render when the user has changed the scripts.
    """
    if USE_S3:
        prefix = f"jobs/{_job_folder_name(job_uuid)}/tts_audio/"
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                _s3().delete_object(Bucket=_S3_BUCKET, Key=obj["Key"])
    else:
        tts_dir = _job_dir(job_uuid) / "tts_audio"
        shutil.rmtree(tts_dir, ignore_errors=True)


# --- Result saving with eviction ---

def save_result_and_evict(job_uuid: str, result_path: str, result_filename: str) -> None:
    """Save job result and delete the oldest jobs that exceed MAX_RESULT_FILES.

    Evicted jobs are fully removed — storage folder first (while DB record still
    exists so _job_folder_name can resolve the path), then the DB record.
    """
    evicted_uuids = update_job_result(job_uuid, result_path, result_filename)
    for uuid in evicted_uuids:
        delete_job_folder(uuid)
        delete_job(uuid)


# --- Cleanup ---

def cleanup_expired_files() -> int:
    """Delete storage folders and DB records for all expired jobs."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    affected = 0

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT job_uuid FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_str,),
        ).fetchall()
        for row in rows:
            delete_job_folder(row["job_uuid"])
            conn.execute("DELETE FROM jobs WHERE job_uuid = ?", (row["job_uuid"],))
            affected += 1
        conn.commit()

    return affected