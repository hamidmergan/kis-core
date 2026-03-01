import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from src.database import get_connection

# --- Local storage paths ---
STORAGE_ROOT = Path("/app/storage")
QUEUE_DIR = STORAGE_ROOT / "queue"
RESULTS_DIR = STORAGE_ROOT / "results"

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
        for d in (QUEUE_DIR, RESULTS_DIR):
            d.mkdir(parents=True, exist_ok=True)


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


def delete_file(file_path: str) -> None:
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=file_path)
        return
    path = Path(file_path)
    if path.exists():
        path.unlink()


# --- Job queue / result storage (per-job folder structure) ---
#
# Layout:
#   queue/{job_uuid}/input{ext}
#   results/{job_uuid}/output{ext}
#   results/{job_uuid}/result.json
#   results/{job_uuid}/meta.json
#   results/{job_uuid}/audio/slide_000.mp3

def save_queue_file(job_uuid: str, ext: str, data: bytes) -> str:
    key = f"queue/{job_uuid}/input{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = QUEUE_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"input{ext}"
    path.write_bytes(data)
    return str(path)


def save_job_file(job_uuid: str, filename: str, data: bytes) -> str:
    """Save an arbitrary named file into the job's result folder."""
    key = f"results/{job_uuid}/{filename}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = RESULTS_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / filename).write_bytes(data)
    return str(job_dir / filename)


def save_result_file(job_uuid: str, ext: str, data: bytes) -> str:
    key = f"results/{job_uuid}/output{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    job_dir = RESULTS_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"output{ext}"
    path.write_bytes(data)
    return str(path)


def save_result_json(job_uuid: str, data: dict) -> str:
    content = json.dumps(data).encode()
    key = f"results/{job_uuid}/result.json"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return key
    job_dir = RESULTS_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "result.json"
    path.write_bytes(content)
    return str(path)


def save_result_meta(job_uuid: str, data: dict) -> None:
    """Save a meta.json file for a job (subtitles, audio info, etc.)."""
    content = json.dumps(data).encode()
    key = f"results/{job_uuid}/meta.json"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return
    job_dir = RESULTS_DIR / job_uuid
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "meta.json").write_bytes(content)


def load_result_meta(job_uuid: str) -> dict | None:
    """Load the meta.json for a job. Returns None if not found."""
    key = f"results/{job_uuid}/meta.json"
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError:
            return None
    meta_path = RESULTS_DIR / job_uuid / "meta.json"
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


# --- Per-slide audio cache (stored under results/{job_uuid}/audio/) ---

def save_audio_cache(job_uuid: str, audio_files: list[bytes]) -> None:
    """Save per-slide MP3 files under the job's result folder."""
    if USE_S3:
        for i, data in enumerate(audio_files):
            key = f"results/{job_uuid}/audio/slide_{i:03d}.mp3"
            _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return
    audio_dir = RESULTS_DIR / job_uuid / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, data in enumerate(audio_files):
        (audio_dir / f"slide_{i:03d}.mp3").write_bytes(data)


def get_audio_slide(job_uuid: str, slide_index: int) -> bytes | None:
    if USE_S3:
        from botocore.exceptions import ClientError
        key = f"results/{job_uuid}/audio/slide_{slide_index:03d}.mp3"
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError:
            return None
    path = RESULTS_DIR / job_uuid / "audio" / f"slide_{slide_index:03d}.mp3"
    if path.exists():
        return path.read_bytes()
    return None


def get_audio_slide_count(job_uuid: str) -> int:
    if USE_S3:
        prefix = f"results/{job_uuid}/audio/"
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        return resp.get("KeyCount", 0)
    audio_dir = RESULTS_DIR / job_uuid / "audio"
    if not audio_dir.exists():
        return 0
    return len(list(audio_dir.glob("slide_*.mp3")))


# --- Per-job folder deletion ---

def delete_job_folder(job_uuid: str) -> None:
    """Delete all files for a job: queue/{uuid}/ and results/{uuid}/."""
    if USE_S3:
        for prefix in (f"queue/{job_uuid}/", f"results/{job_uuid}/"):
            paginator = _s3().get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    _s3().delete_object(Bucket=_S3_BUCKET, Key=obj["Key"])
    else:
        for folder in (QUEUE_DIR / job_uuid, RESULTS_DIR / job_uuid):
            shutil.rmtree(folder, ignore_errors=True)


# --- Cleanup ---

JOB_HISTORY_DAYS = 7


def cleanup_expired_files() -> int:
    """Phase 1: delete job folders for expired jobs but keep the DB record.
    Phase 2: purge DB records older than JOB_HISTORY_DAYS.
    """
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    cutoff_str = (now - timedelta(days=JOB_HISTORY_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    affected = 0

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, job_uuid FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_str,),
        ).fetchall()
        for row in rows:
            delete_job_folder(row["job_uuid"])
            conn.execute(
                "UPDATE jobs SET input_path = NULL, result_path = NULL, result_filename = NULL WHERE id = ?",
                (row["id"],),
            )
            affected += 1

        conn.execute(
            "DELETE FROM jobs WHERE created_at <= ?",
            (cutoff_str,),
        )
        conn.commit()

    return affected
