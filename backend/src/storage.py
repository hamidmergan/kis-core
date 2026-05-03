import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from loguru import logger

from src.database import get_connection, update_job_result, delete_job

# --- Local storage paths ---
STORAGE_ROOT = Path("/app/storage")
JOBS_DIR = STORAGE_ROOT / "jobs"

# --- S3 config (read once at import time) ---
_S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
_S3_BUCKET = os.environ.get("S3_BUCKET", "kis")
USE_S3 = bool(_S3_ENDPOINT)


# --- Object-key prefix helpers (pure, no DB) ---

TMP_PPTX_PREFIX = "tmp/pptx"


def job_prefix(user_id: int, job_uuid: str) -> str:
    """S3 prefix for a job: 'users/{user_id}/jobs/{job_uuid}'. No trailing slash."""
    return f"users/{user_id}/jobs/{job_uuid}"


def aia_workspace_prefix(user_id: int, workspace_uuid: str) -> str:
    """S3 prefix for an AIA workspace: 'users/{user_id}/aia/workspaces/{workspace_uuid}'. No trailing slash."""
    return f"users/{user_id}/aia/workspaces/{workspace_uuid}"


def aia_source_key(user_id: int, workspace_uuid: str, source_uuid: str, ext: str) -> str:
    """S3 key for an AIA source file. ext must include the leading dot (or be empty)."""
    return f"{aia_workspace_prefix(user_id, workspace_uuid)}/sources/{source_uuid}{ext}"


def aia_output_key(user_id: int, workspace_uuid: str, filename: str) -> str:
    """S3 key for an AIA workspace output file."""
    return f"{aia_workspace_prefix(user_id, workspace_uuid)}/outputs/{filename}"


def tmp_pptx_key(file_id: str) -> str:
    """S3 key for a temporary PPTX (translate -> render handoff). Lifecycle: 24h."""
    return f"{TMP_PPTX_PREFIX}/{file_id}.pptx"


def delete_prefix(prefix: str) -> int:
    """Delete every object under a prefix. Batches via delete_objects (1000 keys/call).

    Returns the number of objects deleted. For local mode: shutil.rmtree on the
    matching directory under STORAGE_ROOT.
    """
    if USE_S3:
        deleted = 0
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
            contents = page.get("Contents", [])
            if not contents:
                continue
            # delete_objects accepts up to 1000 keys per call; pages are already <=1000
            _s3().delete_objects(
                Bucket=_S3_BUCKET,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents], "Quiet": True},
            )
            deleted += len(contents)
        return deleted
    # Local mode: prefix maps to a directory under STORAGE_ROOT
    target = STORAGE_ROOT / prefix
    if target.exists():
        count = sum(1 for _ in target.rglob("*") if _.is_file())
        shutil.rmtree(target, ignore_errors=True)
        return count
    return 0


def _local_path(key: str) -> Path:
    """Map an S3 key to a local filesystem path under STORAGE_ROOT."""
    return STORAGE_ROOT / key


def init_lifecycle_policy() -> None:
    """Configure MinIO lifecycle: tmp/ objects expire after 1 day.

    Logged-and-swallowed if the service user lacks s3:PutLifecycleConfiguration;
    cleanup falls back to manual code paths in that case.
    """
    if not USE_S3:
        return
    from botocore.exceptions import ClientError
    try:
        _s3().put_bucket_lifecycle_configuration(
            Bucket=_S3_BUCKET,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "tmp-expire-1d",
                        "Filter": {"Prefix": "tmp/"},
                        "Expiration": {"Days": 1},
                        "Status": "Enabled",
                    }
                ]
            },
        )
    except ClientError as e:
        logger.warning(
            "Could not set bucket lifecycle policy (continuing without): {}", e
        )


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
    """Ensure storage is ready. For S3: create bucket + lifecycle. For local: create dirs."""
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            _s3().head_bucket(Bucket=_S3_BUCKET)
        except ClientError:
            _s3().create_bucket(Bucket=_S3_BUCKET)
        init_lifecycle_policy()
    else:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)


# --- Generic file operations ---

def get_file(file_path: str) -> bytes:
    if USE_S3:
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=file_path)
        return resp["Body"].read()
    return Path(file_path).read_bytes()


def stream_s3_object(file_path: str, range_header: str | None = None):
    """Stream an S3 object chunk-by-chunk, honouring an optional HTTP Range header.

    Returns (iterator, content_length, content_range_or_none).
    """
    kwargs: dict = {"Bucket": _S3_BUCKET, "Key": file_path}
    if range_header:
        kwargs["Range"] = range_header
    resp = _s3().get_object(**kwargs)
    body = resp["Body"]

    def iterator():
        try:
            for chunk in body.iter_chunks(chunk_size=64 * 1024):
                yield chunk
        finally:
            body.close()

    return iterator(), resp["ContentLength"], resp.get("ContentRange")


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
            # Server error, permission error, network issue - assume file exists
            return True
        except Exception:
            # Connection error, timeout, etc. - assume file exists
            return True
    return Path(file_path).exists()


def job_file_exists(user_id: int, job_uuid: str, filename: str) -> bool:
    """Check whether a specific file inside a job's folder still exists."""
    return file_exists(f"{job_prefix(user_id, job_uuid)}/{filename}")


def delete_file(file_path: str) -> None:
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=file_path)
        return
    path = Path(file_path)
    if path.exists():
        path.unlink()


# --- Job folder helpers ---
#
# Layout: users/{user_id}/jobs/{job_uuid}/...
#   input{ext}, output{ext}, result.json, meta.json, audio/slide_000.mp3, ...

# --- Job file I/O ---

def save_queue_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    key = f"{job_prefix(user_id, job_uuid)}/input{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def save_job_file(user_id: int, job_uuid: str, filename: str, data: bytes) -> str:
    """Save an arbitrary named file into the job's folder."""
    key = f"{job_prefix(user_id, job_uuid)}/{filename}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def get_job_file(user_id: int, job_uuid: str, filename: str) -> bytes:
    """Read an arbitrary named file from a job's folder."""
    key = f"{job_prefix(user_id, job_uuid)}/{filename}"
    if USE_S3:
        return get_file(key)
    return _local_path(key).read_bytes()


def save_result_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    key = f"{job_prefix(user_id, job_uuid)}/output{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def save_result_json(user_id: int, job_uuid: str, data: dict) -> str:
    content = json.dumps(data).encode()
    key = f"{job_prefix(user_id, job_uuid)}/result.json"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return str(path)


def save_result_meta(user_id: int, job_uuid: str, data: dict) -> None:
    """Save a meta.json file for a job (subtitles, audio info, etc.)."""
    content = json.dumps(data).encode()
    key = f"{job_prefix(user_id, job_uuid)}/meta.json"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def load_result_meta(user_id: int, job_uuid: str) -> dict | None:
    """Load the meta.json for a job. Returns None if not found."""
    key = f"{job_prefix(user_id, job_uuid)}/meta.json"
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return json.loads(resp["Body"].read())
        except ClientError:
            return None
    meta_path = _local_path(key)
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

def save_audio_cache(user_id: int, job_uuid: str, audio_files: list[bytes]) -> None:
    """Save per-slide MP3 files under the job's audio/ folder. S3 writes parallel."""
    base = f"{job_prefix(user_id, job_uuid)}/audio"
    if USE_S3:
        from concurrent.futures import ThreadPoolExecutor

        def _put(i_data: tuple[int, bytes]) -> None:
            i, data = i_data
            _s3().put_object(Bucket=_S3_BUCKET, Key=f"{base}/slide_{i:03d}.mp3", Body=data)

        if not audio_files:
            return
        with ThreadPoolExecutor(max_workers=min(len(audio_files), 10)) as pool:
            list(pool.map(_put, enumerate(audio_files)))
        return
    audio_dir = _local_path(base)
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, data in enumerate(audio_files):
        (audio_dir / f"slide_{i:03d}.mp3").write_bytes(data)


def get_audio_slide(user_id: int, job_uuid: str, slide_index: int) -> bytes | None:
    key = f"{job_prefix(user_id, job_uuid)}/audio/slide_{slide_index:03d}.mp3"
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError:
            return None
    path = _local_path(key)
    return path.read_bytes() if path.exists() else None


def get_audio_slide_count(user_id: int, job_uuid: str) -> int:
    prefix = f"{job_prefix(user_id, job_uuid)}/audio/"
    if USE_S3:
        resp = _s3().list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        return resp.get("KeyCount", 0)
    audio_dir = _local_path(prefix)
    if not audio_dir.exists():
        return 0
    return len(list(audio_dir.glob("slide_*.mp3")))


def get_all_audio_slides(user_id: int, job_uuid: str) -> list[tuple[str, bytes]]:
    """Fetch all per-slide MP3s in parallel (S3) or sequentially (local).

    Returns a sorted list of (filename, data) tuples.
    """
    prefix = f"{job_prefix(user_id, job_uuid)}/audio/"
    if USE_S3:
        from concurrent.futures import ThreadPoolExecutor, as_completed
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

    audio_dir = _local_path(prefix)
    if not audio_dir.exists():
        return []
    return [(f.name, f.read_bytes()) for f in sorted(audio_dir.glob("slide_*.mp3"))]


# --- PPTX temp storage (translate -> render handoff) ---
#
# Keyed by a random file_id UUID (not a job UUID).
# Layout: tmp/pptx/{file_id}.pptx (lifecycle: 24h via init_lifecycle_policy).


def save_pptx_tmp(file_id: str, data: bytes) -> None:
    """Save a temporary PPTX for the translate -> render handoff."""
    key = tmp_pptx_key(file_id)
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_pptx_tmp(file_id: str) -> bytes | None:
    """Load a temporary PPTX. Returns None if not found or expired."""
    key = tmp_pptx_key(file_id)
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError:
            return None
    path = _local_path(key)
    return path.read_bytes() if path.exists() else None


def delete_pptx_tmp(file_id: str) -> None:
    """Delete a temporary PPTX after render is complete."""
    key = tmp_pptx_key(file_id)
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=key)
    else:
        _local_path(key).unlink(missing_ok=True)


# --- Per-job folder deletion ---

def delete_job_folder(user_id: int, job_uuid: str) -> int:
    """Delete all files for a job. Returns number of objects deleted."""
    return delete_prefix(job_prefix(user_id, job_uuid))


def clear_render_cache(user_id: int, job_uuid: str) -> int:
    """Delete render-cache (TTS audio + alignments). Called before re-render."""
    return delete_prefix(f"{job_prefix(user_id, job_uuid)}/render_cache/")


# --- Result saving with eviction ---

def save_result_and_evict(user_id: int, job_uuid: str, result_path: str, result_filename: str) -> None:
    """Save job result + delete oldest jobs that exceed MAX_RESULT_FILES."""
    evicted_uuids = update_job_result(job_uuid, result_path, result_filename)
    for uid_evicted in evicted_uuids:
        # update_job_result returns uuids; delete_job (after Task 4) returns the row including user_id.
        deleted = delete_job(uid_evicted)
        if deleted:
            delete_job_folder(deleted["user_id"], uid_evicted)


# --- Cleanup ---

def cleanup_expired_files() -> int:
    """Delete storage folders + DB records for all expired jobs."""
    import psycopg2.extras
    affected = 0
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT job_uuid, user_id FROM jobs WHERE expires_at IS NOT NULL AND expires_at <= NOW()",
            )
            rows = cur.fetchall()
            for row in rows:
                delete_job_folder(row["user_id"], row["job_uuid"])
                cur.execute("DELETE FROM jobs WHERE job_uuid = %s", (row["job_uuid"],))
                affected += 1
        conn.commit()
    return affected