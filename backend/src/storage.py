import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from loguru import logger

from src.database import get_connection, update_job_result, delete_job

# --- Local storage paths ---
STORAGE_ROOT = Path("/app/storage")

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


# Derived artifacts (transcript, subtitles) live next to their source, sharing
# its key minus the extension. The naming rule belongs here, with every other
# key rule, so the next artifact type does not have to rediscover it.
#
# All three take the source's own key (or path), so callers never have to strip
# the extension themselves. Passing an already-stripped base works too.


def aia_source_base(file_path: str) -> str:
    """The source key without its extension: the stem every artifact hangs off."""
    return os.path.splitext(file_path)[0]


def aia_transcript_key(file_path: str) -> str:
    """Full transcript with timestamps, produced by Whisper."""
    return f"{aia_source_base(file_path)}_transcript.txt"


def aia_vtt_key(file_path: str, lang: str) -> str:
    """Subtitles for one language."""
    return f"{aia_source_base(file_path)}_transcript.{lang}.vtt"


def aia_transcript_prefix(file_path: str) -> str:
    """Prefix covering every transcript artifact of one source."""
    return f"{aia_source_base(file_path)}_transcript."


def tmp_pptx_key(file_id: str) -> str:
    """S3 key for a temporary PPTX (translate -> render handoff). Lifecycle: 24h."""
    return f"{TMP_PPTX_PREFIX}/{file_id}.pptx"


AIA_SPEECH_PREFIX = "aia/speech"


def aia_speech_key(fingerprint: str) -> str:
    """Key for one spoken example sentence.

    Deliberately NOT under ``users/``: the sound belongs to the sentence, not to a
    person, and every course shares it. Under a user prefix, deleting one account
    would take away a sound others are still listening to.

    The first two characters of the fingerprint fan the keys out over 256 folders.
    It is a SHA-256, so the spread is even, and no single listing ever has to walk
    hundreds of thousands of siblings.
    """
    return f"{AIA_SPEECH_PREFIX}/{fingerprint[:2]}/{fingerprint}.mp3"


def delete_prefix(prefix: str) -> int:
    """Delete every object whose key starts with ``prefix``. Returns the count.

    The prefix does not have to end at a slash. ``.../sources/abc`` also covers
    ``.../sources/abc_transcript.txt``, which is how a source and its derived
    artifacts are removed in one go.

    Local mode mirrors that: a prefix pointing at a directory is removed whole,
    otherwise every sibling file whose name starts with the prefix goes. An
    absolute path works too, because ``file_path`` holds one without S3.
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

    def _remove(path: Path) -> int:
        if path.is_dir():
            count = sum(1 for p in path.rglob("*") if p.is_file())
            shutil.rmtree(path, ignore_errors=True)
            return count
        if path.is_file():
            path.unlink(missing_ok=True)
            return 1
        return 0

    target = STORAGE_ROOT / prefix
    if target.is_dir():
        return _remove(target)
    return sum(_remove(match) for match in target.parent.glob(target.name + "*"))


def _local_path(key: str) -> Path:
    """Map an S3 key to a local filesystem path under STORAGE_ROOT."""
    return STORAGE_ROOT / key


# Every save_* below is one key expression plus one of these two. Keeping the
# backend switch in a single place means a change to it (a retry wrapper, a
# checksum, a content type) is one edit and not ten.


def _store_bytes(key: str, data: bytes) -> str:
    """Write ``data`` at ``key``. Returns the key (S3) or the path (local)."""
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def _store_from_path(key: str, local_path: str) -> str:
    """Copy a local file to ``key``, streaming. Returns the key (S3) or path (local).

    boto3 multiparts the upload itself, so a 500 MB recording never sits in the
    backend process. Use this for anything user-uploaded; :func:`_store_bytes`
    is fine only for small generated payloads.
    """
    if USE_S3:
        _s3().upload_file(local_path, _S3_BUCKET, key)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_path, path)
    return str(path)


def init_lifecycle_policy() -> None:
    """Configure bucket lifecycle: tmp/ expires after 1 day, backups/ after the
    configured retention.

    Both rules go out in ONE call because put_bucket_lifecycle_configuration
    REPLACES the whole configuration; sending only one rule would silently drop
    the other.

    The backups/ rule is a second line of defence only. The nightly task in
    tasks/backup_tasks.py prunes old dumps itself, because this call is
    logged-and-swallowed when the service user lacks s3:PutLifecycleConfiguration.
    """
    if not USE_S3:
        return
    from botocore.exceptions import ClientError
    from src.limits import (
            DB_BACKUP_KEEP_DAYS,
            DB_BACKUP_KEEP_MONTHS,
            DB_BACKUP_KEEP_WEEKS,
        )
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
                    },
                    # Getrennte Regeln pro Unterordner. Eine Regel auf "backups/"
                    # wuerde die Monatskopien nach wenigen Tagen mitloeschen und
                    # die Staffelung damit wertlos machen.
                    {
                        "ID": "backups-daily-expire",
                        "Filter": {"Prefix": "backups/daily/"},
                        "Expiration": {"Days": DB_BACKUP_KEEP_DAYS},
                        "Status": "Enabled",
                    },
                    {
                        "ID": "backups-weekly-expire",
                        "Filter": {"Prefix": "backups/weekly/"},
                        "Expiration": {"Days": DB_BACKUP_KEEP_WEEKS * 7 + 3},
                        "Status": "Enabled",
                    },
                    {
                        "ID": "backups-monthly-expire",
                        "Filter": {"Prefix": "backups/monthly/"},
                        "Expiration": {"Days": DB_BACKUP_KEEP_MONTHS * 31},
                        "Status": "Enabled",
                    },
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
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


# --- Generic file operations ---

def get_file(file_path: str) -> bytes:
    if USE_S3:
        resp = _s3().get_object(Bucket=_S3_BUCKET, Key=file_path)
        return resp["Body"].read()
    return Path(file_path).read_bytes()


def get_range(file_path: str, start: int, length: int) -> bytes:
    """Read up to ``length`` bytes from ``start`` of a stored object.

    HTTP Range for S3, ``seek`` locally. Returns fewer bytes near EOF, or ``b""`` if the
    range starts past EOF. Lets callers classify a large object (e.g. detect fragmented
    MP4 from its box headers) without downloading the whole body.
    """
    if USE_S3:
        from botocore.exceptions import ClientError
        end = start + length - 1
        try:
            resp = _s3().get_object(
                Bucket=_S3_BUCKET, Key=file_path, Range=f"bytes={start}-{end}"
            )
            return resp["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("InvalidRange", "416"):
                return b""
            raise
    with open(Path(file_path), "rb") as f:
        f.seek(start)
        return f.read(length)


def copy_key(src_path: str, dst_path: str) -> None:
    """Copy a stored object without pulling it through this process.

    S3 does the copy server-side, so a 1.5 GB backup does not travel over the
    network twice just to keep a monthly copy. Local mode falls back to a plain
    file copy.
    """
    if USE_S3:
        _s3().copy_object(
            Bucket=_S3_BUCKET,
            CopySource={"Bucket": _S3_BUCKET, "Key": src_path},
            Key=dst_path,
        )
    else:
        dst = Path(dst_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(src_path), dst)


def put_bytes(file_path: str, data: bytes) -> None:
    """Overwrite a stored object with ``data``. Counterpart to :func:`get_file`.

    For small generated payloads (a transcript, a VTT). Anything user-uploaded
    or multi-GB belongs in :func:`put_file`, which streams instead.
    """
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=file_path, Body=data)
        return
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def put_file(file_path: str, local_path: str) -> None:
    """Overwrite a stored object with the contents of a local file.

    Streamed (boto3 multipart for S3, ``shutil.copyfile`` locally) so it stays low-RAM
    even for multi-GB media. Used to write back a normalised/remuxed media file.
    """
    if USE_S3:
        _s3().upload_file(local_path, _S3_BUCKET, file_path)
    else:
        shutil.copyfile(local_path, Path(file_path))


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


def list_keys(prefix: str) -> list[str]:
    """List stored keys/paths that begin with ``prefix``, in one round trip.

    One ``list_objects_v2`` (S3) or one glob (local) instead of a HEAD probe per
    candidate file. Mirrors how :func:`file_exists` treats its argument: an S3
    key in S3 mode, a filesystem path in local mode.

    Same prefix rule as :func:`delete_prefix`: a prefix pointing at a directory
    covers everything below it, however deep, otherwise it covers the sibling
    files whose name starts with it. In S3 a prefix always did both, and local
    mode has to answer the same question the same way.
    """
    if USE_S3:
        keys: list[str] = []
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys
    target = STORAGE_ROOT / prefix
    treffer = target.rglob("*") if target.is_dir() else target.parent.glob(target.name + "*")
    return [str(f) for f in treffer if f.is_file()]


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


# --- AIA source file I/O ---
#
# Layout: users/{user_id}/aia/workspaces/{workspace_uuid}/sources/...
#   {source_uuid}{ext}, {source_uuid}_transcript.txt, {source_uuid}_transcript.de.vtt, ...


def save_aia_source_from_path(
    user_id: int, workspace_uuid: str, source_uuid: str, ext: str, local_path: str
) -> str:
    """Store an AIA source, streaming from a file on disk."""
    return _store_from_path(aia_source_key(user_id, workspace_uuid, source_uuid, ext), local_path)


# --- Job folder helpers ---
#
# Layout: users/{user_id}/jobs/{job_uuid}/...
#   input{ext}, output{ext}, result.json, meta.json, audio/slide_000.mp3, ...

# --- Job file I/O ---

def save_queue_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    return _store_bytes(f"{job_prefix(user_id, job_uuid)}/input{ext}", data)


def save_queue_file_from_path(user_id: int, job_uuid: str, ext: str, local_path: str) -> str:
    """Same as :func:`save_queue_file`, but takes a path instead of bytes."""
    return _store_from_path(f"{job_prefix(user_id, job_uuid)}/input{ext}", local_path)


def save_job_file_from_path(user_id: int, job_uuid: str, filename: str, local_path: str) -> str:
    """Like :func:`save_job_file`, but streams from a local file."""
    return _store_from_path(f"{job_prefix(user_id, job_uuid)}/{filename}", local_path)


def save_job_file(user_id: int, job_uuid: str, filename: str, data: bytes) -> str:
    """Save an arbitrary named file into the job's folder."""
    return _store_bytes(f"{job_prefix(user_id, job_uuid)}/{filename}", data)


def get_job_file(user_id: int, job_uuid: str, filename: str) -> bytes:
    """Read an arbitrary named file from a job's folder."""
    key = f"{job_prefix(user_id, job_uuid)}/{filename}"
    if USE_S3:
        return get_file(key)
    return _local_path(key).read_bytes()


def save_result_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    return _store_bytes(f"{job_prefix(user_id, job_uuid)}/output{ext}", data)


def save_result_json(user_id: int, job_uuid: str, data: dict) -> str:
    key = f"{job_prefix(user_id, job_uuid)}/result.json"
    return _store_bytes(key, json.dumps(data).encode())


def save_result_meta(user_id: int, job_uuid: str, data: dict) -> None:
    """Save a meta.json file for a job (subtitles, audio info, etc.)."""
    key = f"{job_prefix(user_id, job_uuid)}/meta.json"
    _store_bytes(key, json.dumps(data).encode())


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


def _slide_number(key_or_name: str) -> int:
    """Slide index from ``slide_007.mp3``. Unparsable names sort to the front.

    Sorting these names as text would put ``slide_1000`` before ``slide_999``.
    Widening the padding instead would be worse: old jobs would keep the
    three-digit names and the two widths would mix.
    """
    name = key_or_name.rsplit("/", 1)[-1]
    digits = name[len("slide_"):].split(".", 1)[0]
    return int(digits) if digits.isdigit() else -1


def save_audio_cache(user_id: int, job_uuid: str, audio_files: list[bytes | None]) -> None:
    """Save per-slide MP3 files under the job's audio/ folder. S3 writes parallel.

    ``None`` an einer Stelle heisst: diesen Platz nicht anfassen. Folien, die
    nicht im Screencast sind, behalten so ihren alten Ton.
    """
    base = f"{job_prefix(user_id, job_uuid)}/audio"
    zu_schreiben = [(i, d) for i, d in enumerate(audio_files) if d is not None]
    if not zu_schreiben:
        return
    if USE_S3:
        from concurrent.futures import ThreadPoolExecutor

        def _put(i_data: tuple[int, bytes]) -> None:
            i, data = i_data
            _s3().put_object(Bucket=_S3_BUCKET, Key=f"{base}/slide_{i:03d}.mp3", Body=data)

        with ThreadPoolExecutor(max_workers=min(len(zu_schreiben), 10)) as pool:
            list(pool.map(_put, zu_schreiben))
        return
    audio_dir = _local_path(base)
    audio_dir.mkdir(parents=True, exist_ok=True)
    for i, data in zu_schreiben:
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


def hat_audio_slide(user_id: int, job_uuid: str, slide_index: int) -> bool:
    """Leere Dateien gelten als kein Ton, sie stehen fuer Folien ohne Skript."""
    return bool(get_audio_slide(user_id, job_uuid, slide_index))


def get_audio_slide_count(user_id: int, job_uuid: str) -> int:
    prefix = f"{job_prefix(user_id, job_uuid)}/audio/"
    if USE_S3:
        # list_keys paginates; a plain KeyCount would cap a long deck at 1000.
        return len(list_keys(prefix))
    audio_dir = _local_path(prefix)
    if not audio_dir.exists():
        return 0
    return len(list(audio_dir.glob("slide_*.mp3")))


def audio_folien_mit_ton(user_id: int, job_uuid: str) -> set[int]:
    """Welche Folien Ton haben, in einer Abfrage statt einer je Folie."""
    prefix = f"{job_prefix(user_id, job_uuid)}/audio/"
    dabei: set[int] = set()
    if USE_S3:
        paginator = _s3().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Size"] > 0:
                    dabei.add(_slide_number(obj["Key"]))
        return dabei - {-1}
    audio_dir = _local_path(prefix)
    if not audio_dir.exists():
        return dabei
    for pfad in audio_dir.glob("slide_*.mp3"):
        if pfad.stat().st_size > 0:
            dabei.add(_slide_number(pfad.name))
    return dabei - {-1}


def get_all_audio_slides(user_id: int, job_uuid: str) -> list[tuple[str, bytes]]:
    """Fetch all per-slide MP3s in parallel (S3) or sequentially (local).

    Returns a list of (filename, data) tuples in slide order.
    """
    prefix = f"{job_prefix(user_id, job_uuid)}/audio/"
    if USE_S3:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        keys = [k for k in list_keys(prefix) if k.endswith(".mp3")]
        if not keys:
            return []

        def _fetch(key: str) -> tuple[str, bytes]:
            data = _s3().get_object(Bucket=_S3_BUCKET, Key=key)["Body"].read()
            return (key.split("/")[-1], data)

        # as_completed discards submission order, so the sort at the end is the
        # one that decides the result. Sorting the keys too would be wasted.
        with ThreadPoolExecutor(max_workers=min(len(keys), 10)) as pool:
            results = [f.result() for f in as_completed([pool.submit(_fetch, k) for k in keys])]
        return sorted(results, key=lambda x: _slide_number(x[0]))

    audio_dir = _local_path(prefix)
    if not audio_dir.exists():
        return []
    slides = sorted(audio_dir.glob("slide_*.mp3"), key=lambda p: _slide_number(p.name))
    return [(f.name, f.read_bytes()) for f in slides]


# --- PPTX temp storage (translate -> render handoff) ---
#
# Keyed by a random file_id UUID (not a job UUID).
# Layout: tmp/pptx/{file_id}.pptx (lifecycle: 24h via init_lifecycle_policy).


def save_pptx_tmp(file_id: str, data: bytes) -> None:
    """Save a temporary PPTX for the translate -> render handoff."""
    _store_bytes(tmp_pptx_key(file_id), data)


# --- Spoken example sentences (AIA flashcards + voice previews) ---
# Keyed by the fingerprint from repository/speech_cache.py, which owns the
# retention rule. There is no lifecycle rule here: expiry follows last use, not
# creation date, and only the database row knows when a sound was last heard.


def save_speech_audio(fingerprint: str, data: bytes) -> None:
    """Store the MP3 for one spoken sentence."""
    _store_bytes(aia_speech_key(fingerprint), data)


def get_speech_audio(fingerprint: str) -> bytes | None:
    """Load one spoken sentence. None means it is genuinely not there.

    A missing object and an unreachable store are different answers on purpose.
    The caller drops its database row when this returns None, so a network blip
    must raise instead: otherwise a moment of bad connectivity would throw away
    the whole cache.
    """
    key = aia_speech_key(fingerprint)
    if USE_S3:
        from botocore.exceptions import ClientError
        try:
            resp = _s3().get_object(Bucket=_S3_BUCKET, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") in ("404", "NoSuchKey"):
                return None
            raise
    path = _local_path(key)
    return path.read_bytes() if path.exists() else None


def delete_speech_audio(fingerprints) -> None:
    """Delete the sounds for the given fingerprints. Used by the nightly cleanup."""
    keys = [aia_speech_key(f) for f in fingerprints]
    if not keys:
        # S3 rejects delete_objects with an empty list, and most nights are empty.
        return
    if USE_S3:
        # delete_objects takes at most 1000 keys per call.
        for i in range(0, len(keys), 1000):
            _s3().delete_objects(
                Bucket=_S3_BUCKET,
                Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]], "Quiet": True},
            )
        return
    for key in keys:
        _local_path(key).unlink(missing_ok=True)


# --- Folder deletion ---

def delete_job_folder(user_id: int, job_uuid: str) -> int:
    """Delete all files for a job. Returns number of objects deleted."""
    return delete_prefix(job_prefix(user_id, job_uuid))


def clear_render_cache(user_id: int, job_uuid: str) -> int:
    """Delete render-cache (TTS audio + alignments). Called before re-render."""
    return delete_prefix(f"{job_prefix(user_id, job_uuid)}/render_cache/")


def clear_audio_cache(user_id: int, job_uuid: str) -> int:
    """Loescht den fertigen Ton. Noetig, sobald Folien oder Skripte ersetzt werden."""
    return delete_prefix(f"{job_prefix(user_id, job_uuid)}/audio/")


def delete_aia_source_files(file_path: str) -> int:
    """Delete an AIA source together with everything derived from it.

    Transcript and subtitles are siblings of the source file, so deleting the
    source alone would leave the full text of a recording in the bucket with
    no row pointing at it. Safe as a prefix because source uuids are
    ``uuid4().hex``, all 32 characters: no source name can be a prefix of
    another, so this never reaches into a sibling source.
    """
    return delete_prefix(aia_source_base(file_path))


def delete_aia_workspace_folder(user_id: int, workspace_uuid: str) -> int:
    """Delete an AIA workspace with all its sources and derived artifacts."""
    return delete_prefix(aia_workspace_prefix(user_id, workspace_uuid))


# --- Result saving with eviction ---

def evict_jobs_over_cap(user_id: int) -> int:
    """Alles ueber dem Vorrat aus dem Admin loeschen, Zeile und Ordner.

    Einzige Aufbewahrungsregel, seit die Frist von sieben Tagen raus ist. Zaehlt
    alle Jobs eines Nutzers, also auch Fehlschlaege, die frueher nur die Frist
    entsorgt hat.
    """
    from src.database import get_jobs_for_user_newest_first, select_jobs_to_evict

    entfernt = 0
    for job in select_jobs_to_evict(get_jobs_for_user_newest_first(user_id)):
        geloescht = delete_job(job["job_uuid"])
        if geloescht:
            delete_job_folder(geloescht["user_id"], job["job_uuid"])
            entfernt += 1
    return entfernt


def save_result_and_evict(user_id: int, job_uuid: str, result_path: str, result_filename: str) -> None:
    """Save job result + delete oldest jobs beyond the configured cap."""
    update_job_result(job_uuid, result_path, result_filename)
    evict_jobs_over_cap(user_id)


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
