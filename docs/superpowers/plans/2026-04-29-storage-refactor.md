# Storage Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor S3 storage layer to stable, immutable-ID-based object keys (`users/{user_id}/jobs/{job_uuid}/…`, `users/{user_id}/aia/modules/{module_uuid}/…`, `tmp/pptx/…`) with no DB roundtrip for path resolution, batch operations, MinIO lifecycle for tmp, and dead-code removal.

**Architecture:** Replace `_job_folder_name(job_uuid)` (DB-driven) with pure functions over `(user_id, uuid)`. Caller passes `user_id` (always available from session/job-row). Unify `kia/` ↔ `aia/`. Move tmp cleanup from sync code to MinIO lifecycle policy. Drop `jobs.username` denormalized column.

**Tech Stack:** Python 3.11, FastAPI, boto3 (S3/MinIO), psycopg2 (PostgreSQL), Celery.

**Spec:** [docs/superpowers/specs/2026-04-29-storage-refactor-design.md](../specs/2026-04-29-storage-refactor-design.md)

**Test strategy:** No pytest infra in this repo (CLAUDE.md Item 9 open). Verification = backend boot smoke + manual E2E in Task 7. Each task ends with a quick syntax/import check.

**Commit policy (project rule from MEMORY.md):** Author NEVER commits without explicit user approval. Each task ends with `git status` and a wait-for-approval step, NOT a `git commit` directly.

**Backend reload:** Backend uses uvicorn `--reload` — Python file edits auto-reload, no container restart needed.

---

## File Map

| File | Role | Touched in Task |
|---|---|---|
| `backend/src/storage.py` | Storage API (rewrite) | 1, 2, 3 |
| `backend/src/core/db/schema.py` | DB schema (DROP username) | 4 |
| `backend/src/features/jobs/repository/_crud.py` | INSERT without username | 4 |
| `backend/src/features/jobs/repository/_crud.py` | `delete_job` returns user_id | 4 |
| `backend/src/services/screencast/generation.py` | `tts_audio/` → `render_cache/` | 5 |
| `backend/src/routes/screencast/render.py` | `clear_render_cache` signature | 5 |
| `backend/src/tasks/screencast_tasks/_render.py` | `clear_render_cache` signature | 5 |
| `backend/src/tasks/screencast_tasks/_demo.py` | `save_audio_cache` signature | 5 |
| `backend/src/tasks/screencast_tasks/_pipeline.py` | `save_audio_cache` signature | 5 |
| `backend/src/routes/screencast/audio.py` | resolve user_id, new signatures | 5 |
| `backend/src/features/ai_assistant/tasks/_helpers.py` | `_save_aia_output` rewrite | 6 |
| `backend/src/features/ai_assistant/routes/_helpers.py` | `_save_source_file` rewrite | 6 |
| 11 files (chat, glossary, messages, modules, popup, notes, exercises, stats, data_table, flashcards, mindmap) | Remove unused `save_file` import | 3 |
| `private/migrate-storage.md` | Bucket-wipe + DB-truncate doku | 7 |

---

## Task 1: New storage.py foundation — pure prefix helpers + batch + lifecycle

**Files:**
- Modify: `backend/src/storage.py` (top of file, after existing constants)

**Goal:** Add new pure-function API in parallel to existing code. Old API stays functional during this task — incremental migration in Task 2.

- [ ] **Step 1: Add prefix constants and pure functions**

Add after line 25 (`USE_S3 = bool(_S3_ENDPOINT)`):

```python
# --- Object-key prefix helpers (pure, no DB) ---

TMP_PPTX_PREFIX = "tmp/pptx"


def job_prefix(user_id: int, job_uuid: str) -> str:
    """S3 prefix for a job: 'users/{user_id}/jobs/{job_uuid}'. No trailing slash."""
    return f"users/{user_id}/jobs/{job_uuid}"


def aia_module_prefix(user_id: int, module_uuid: str) -> str:
    """S3 prefix for an AIA module: 'users/{user_id}/aia/modules/{module_uuid}'. No trailing slash."""
    return f"users/{user_id}/aia/modules/{module_uuid}"


def aia_source_key(user_id: int, module_uuid: str, source_uuid: str, ext: str) -> str:
    """S3 key for an AIA source file. ext must include the leading dot (or be empty)."""
    return f"{aia_module_prefix(user_id, module_uuid)}/sources/{source_uuid}{ext}"


def aia_output_key(user_id: int, module_uuid: str, filename: str) -> str:
    """S3 key for an AIA module output file."""
    return f"{aia_module_prefix(user_id, module_uuid)}/outputs/{filename}"


def tmp_pptx_key(file_id: str) -> str:
    return f"{TMP_PPTX_PREFIX}/{file_id}.pptx"
```

- [ ] **Step 2: Add `delete_prefix` batch helper**

Add after the prefix helpers:

```python
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
```

- [ ] **Step 3: Add `init_lifecycle_policy`**

Add after `delete_prefix`:

```python
def init_lifecycle_policy() -> None:
    """Configure MinIO lifecycle: tmp/ objects expire after 1 day.

    Logged-and-swallowed if the service user lacks s3:PutLifecycleConfiguration —
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
        import logging
        logging.getLogger(__name__).warning(
            "Could not set bucket lifecycle policy (continuing without): %s", e
        )
```

- [ ] **Step 4: Wire `init_lifecycle_policy` into `init_storage`**

Modify `init_storage` (around line 51):

```python
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
```

- [ ] **Step 5: Smoke check — backend imports cleanly**

```bash
docker compose exec kis-backend python -c "from src.storage import job_prefix, aia_module_prefix, aia_source_key, aia_output_key, tmp_pptx_key, delete_prefix, init_lifecycle_policy; print(job_prefix(7, 'abc-123'))"
```
Expected output: `users/7/jobs/abc-123`

- [ ] **Step 6: Stage + ask user to commit**

```bash
git add backend/src/storage.py
git status
```
Wait for user approval before commit.

---

## Task 2: storage.py — migrate Job functions to (user_id, job_uuid) signature

**Files:**
- Modify: `backend/src/storage.py` (job-related functions, lines ~145–445)

**Goal:** Replace `_job_folder_name(job_uuid)` callers with `job_prefix(user_id, job_uuid)`. Add `user_id` parameter to all job-storage functions. Rename `clear_tts_audio_cache` → `clear_render_cache`. Parallelize `save_audio_cache`. Use `delete_prefix` for batch deletes.

- [ ] **Step 1: Delete old DB-driven path helpers**

Remove these functions entirely (lines ~168–193):
- `_job_folder_name(job_uuid)`
- `_job_key(job_uuid, filename)`
- `_job_dir(job_uuid)`

- [ ] **Step 2: Add a small private helper for local-mode dirs**

After the `delete_prefix` helper, add:

```python
def _local_path(key: str) -> Path:
    """Map an S3 key to a local filesystem path under STORAGE_ROOT."""
    return STORAGE_ROOT / key
```

- [ ] **Step 3: Migrate `job_file_exists`**

Replace (around line 145):

```python
def job_file_exists(user_id: int, job_uuid: str, filename: str) -> bool:
    """Check whether a specific file inside a job's folder still exists."""
    return file_exists(f"{job_prefix(user_id, job_uuid)}/{filename}")
```

- [ ] **Step 4: Migrate `save_queue_file`**

Replace (around line 198):

```python
def save_queue_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    key = f"{job_prefix(user_id, job_uuid)}/input{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)
```

- [ ] **Step 5: Migrate `save_job_file`**

```python
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
```

- [ ] **Step 6: Migrate `get_job_file`**

```python
def get_job_file(user_id: int, job_uuid: str, filename: str) -> bytes:
    """Read an arbitrary named file from a job's folder."""
    key = f"{job_prefix(user_id, job_uuid)}/{filename}"
    if USE_S3:
        return get_file(key)
    return _local_path(key).read_bytes()
```

- [ ] **Step 7: Migrate `save_result_file`**

```python
def save_result_file(user_id: int, job_uuid: str, ext: str, data: bytes) -> str:
    key = f"{job_prefix(user_id, job_uuid)}/output{ext}"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)
```

- [ ] **Step 8: Migrate `save_result_json`, `save_result_meta`, `load_result_meta`**

```python
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
    content = json.dumps(data).encode()
    key = f"{job_prefix(user_id, job_uuid)}/meta.json"
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=content)
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def load_result_meta(user_id: int, job_uuid: str) -> dict | None:
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
```

- [ ] **Step 9: Migrate audio cache (parallelized writes)**

```python
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
    """Fetch all per-slide MP3s in parallel (S3) or sequentially (local)."""
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
```

- [ ] **Step 10: Migrate pptx_tmp helpers to use `TMP_PPTX_PREFIX`**

Replace block (around line 380–414):

```python
def save_pptx_tmp(file_id: str, data: bytes) -> None:
    key = tmp_pptx_key(file_id)
    if USE_S3:
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_pptx_tmp(file_id: str) -> bytes | None:
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
    key = tmp_pptx_key(file_id)
    if USE_S3:
        _s3().delete_object(Bucket=_S3_BUCKET, Key=key)
    else:
        _local_path(key).unlink(missing_ok=True)
```

Also delete the old constants `_PPTX_TMP_DIR` and `_PPTX_TMP_PREFIX` (now replaced by `TMP_PPTX_PREFIX`).

- [ ] **Step 11: Migrate `delete_job_folder` and rename `clear_tts_audio_cache` → `clear_render_cache`**

```python
def delete_job_folder(user_id: int, job_uuid: str) -> int:
    """Delete all files for a job. Returns number of objects deleted."""
    return delete_prefix(job_prefix(user_id, job_uuid))


def clear_render_cache(user_id: int, job_uuid: str) -> int:
    """Delete render-cache (TTS audio + alignments). Called before re-render."""
    return delete_prefix(f"{job_prefix(user_id, job_uuid)}/render_cache/")
```

- [ ] **Step 12: Update `save_result_and_evict` and `cleanup_expired_files` for new signatures**

```python
def save_result_and_evict(user_id: int, job_uuid: str, result_path: str, result_filename: str) -> None:
    """Save job result + delete oldest jobs that exceed MAX_RESULT_FILES."""
    evicted_uuids = update_job_result(job_uuid, result_path, result_filename)
    for uid_evicted in evicted_uuids:
        # update_job_result returns uuids; we need user_id per uuid for the new prefix.
        # Reuse delete_job which now returns user_id (Task 4).
        deleted = delete_job(uid_evicted)
        if deleted:
            delete_job_folder(deleted["user_id"], uid_evicted)


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
```

NOTE: `save_result_and_evict` depends on `delete_job` returning `user_id` (Task 4). Until Task 4 lands, this function's eviction branch will fail; the simple-success branch still works. Tasks 2 and 4 must both ship before re-rendering hits the eviction path.

- [ ] **Step 13: Smoke check — module imports + signatures**

```bash
docker compose exec kis-backend python -c "
from src.storage import (
  job_prefix, aia_module_prefix, save_queue_file, save_job_file, get_job_file,
  save_result_file, save_result_json, save_result_meta, load_result_meta,
  save_audio_cache, get_audio_slide, get_audio_slide_count, get_all_audio_slides,
  delete_job_folder, clear_render_cache, save_pptx_tmp, get_pptx_tmp, delete_pptx_tmp,
  job_file_exists, delete_prefix, save_result_and_evict, cleanup_expired_files,
)
import inspect
assert 'user_id' in inspect.signature(save_queue_file).parameters
assert 'user_id' in inspect.signature(clear_render_cache).parameters
print('signatures ok')
"
```
Expected: `signatures ok`

- [ ] **Step 14: Stage + ask user to commit**

```bash
git add backend/src/storage.py
git status
git diff --stat HEAD
```
Wait for user approval.

---

## Task 3: Remove dead code (`save_file` + 11 unused imports)

**Files:**
- Modify: `backend/src/storage.py` (delete `save_file`, line ~65)
- Modify: 11 import lines in:
  - `backend/src/features/ai_assistant/routes/chat.py:29`
  - `backend/src/features/ai_assistant/routes/glossary.py:30`
  - `backend/src/features/ai_assistant/routes/messages.py:27`
  - `backend/src/features/ai_assistant/routes/modules.py:27`
  - `backend/src/features/ai_assistant/routes/popup.py:27`
  - `backend/src/features/ai_assistant/routes/notes.py:27`
  - `backend/src/features/ai_assistant/routes/language_training/exercises.py:30`
  - `backend/src/features/ai_assistant/routes/language_training/stats.py:28`
  - `backend/src/features/ai_assistant/routes/studio/data_table.py:29`
  - `backend/src/features/ai_assistant/routes/studio/flashcards.py:29`
  - `backend/src/features/ai_assistant/routes/studio/mindmap.py:29`

- [ ] **Step 1: Delete `save_file` function from storage.py**

Remove lines 65–75 entirely (the `def save_file(user_id: int, ...)` block).

- [ ] **Step 2: Remove `save_file` from each import**

For each of the 11 files, the import looks like:
```python
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
```
Change to:
```python
from src.storage import USE_S3, delete_file, file_exists, get_file
```

Use `Edit` per file (the line is identical across the 11 files, but each Edit must target one file).

- [ ] **Step 3: Verify no remaining references**

```bash
docker compose exec kis-backend python -c "import src.storage; assert not hasattr(src.storage, 'save_file'), 'still defined'; print('removed')"
grep -rn "save_file" backend/src/ || echo "no references"
```
Expected: `removed` and `no references`.

- [ ] **Step 4: Stage + ask user to commit**

```bash
git add -u backend/src/storage.py backend/src/features/ai_assistant/
git status
```
Wait for user approval.

---

## Task 4: DB schema cleanup — drop `jobs.username`, update `_crud.py`

**Files:**
- Modify: `backend/src/core/db/schema.py` (around line 150)
- Modify: `backend/src/features/jobs/repository/_crud.py` (lines 9–27 for `create_job`, lines 59–72 for `delete_job`)

**Goal:** Drop the denormalized `username` column from `jobs`. UI/Stats already JOIN `users.ldap_username`. Make `delete_job` return `user_id` for storage cleanup.

- [ ] **Step 1: Add idempotent DROP migration to `schema.py`**

In `init_db()`, after the existing `ALTER TABLE jobs ADD COLUMN IF NOT EXISTS username` (line 150), append a DROP. The ADD line should be removed entirely; the DROP runs idempotently:

Replace line 150:
```python
cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT 'unknown'")
```
With:
```python
cur.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS username")
```

- [ ] **Step 2: Remove `username` from CREATE TABLE block**

The original `CREATE TABLE IF NOT EXISTS jobs` block in `schema.py` (lines 126–148) does NOT include `username` in the CREATE itself (only the ALTER added it). So no change to the CREATE block. Confirm:

```bash
grep -n "username" backend/src/core/db/schema.py
```
Expected: only the new DROP line should reference `username` after this task.

- [ ] **Step 3: Update `create_job` in `_crud.py`**

Replace the function body:

```python
def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (job_uuid, user_id, tool, original_filename, input_path, expires_at),
            )
        conn.commit()
```

- [ ] **Step 4: Update `delete_job` to return `user_id`**

Replace the function body (around lines 59–72):

```python
def delete_job(job_uuid: str) -> dict | None:
    """Delete a job record and return its user_id + file paths for cleanup."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT user_id, input_path, result_path, celery_task_id FROM jobs WHERE job_uuid = %s",
                (job_uuid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("DELETE FROM jobs WHERE job_uuid = %s", (job_uuid,))
        conn.commit()
        return dict(row)
```

- [ ] **Step 5: Find and remove `username=` arguments at all `create_job` callers**

```bash
grep -rn "create_job(" backend/src/ | grep -v "_crud.py"
```

For each match: if it passes a `username=` kwarg, remove that argument (positional `username` callers don't exist — the param had a default).

Example diff (typical caller):
```python
# Before
create_job(job_uuid=uid, user_id=user["id"], tool="screencast", ..., username=user["ldap_username"])
# After
create_job(job_uuid=uid, user_id=user["id"], tool="screencast", ...)
```

- [ ] **Step 6: Update the `update_job_result` docstring**

In `_crud.py` lines 136–141, the docstring references `_job_folder_name()` which no longer exists. Replace:

```python
def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> list[str]:
    """Save job result. Returns job_uuids that exceed MAX_RESULT_FILES and must be evicted.

    Use storage.save_result_and_evict() which fetches user_id via delete_job() before
    deleting the storage folder.
    """
```

- [ ] **Step 7: Smoke check — schema applies, create_job signature**

```bash
docker compose restart kis-backend  # picks up schema.py init_db on startup
docker compose logs kis-backend --tail 30 | grep -E "init_db|ERROR"
```
Expected: clean startup, no errors. Then verify column gone:
```bash
docker compose exec kis-postgres psql -U kis -d kis -c "\d jobs" | grep -i username || echo "column dropped"
```
Expected: `column dropped`.

- [ ] **Step 8: Stage + ask user to commit**

```bash
git add -u backend/src/core/db/schema.py backend/src/features/jobs/repository/_crud.py
git status
```
Wait for user approval.

---

## Task 5: Screencast caller migration (signatures + render_cache rename)

**Files:**
- Modify: `backend/src/services/screencast/generation.py` (lines 76, 79, 110, 112)
- Modify: `backend/src/routes/screencast/render.py` (around line 11, 74)
- Modify: `backend/src/tasks/screencast_tasks/_render.py` (lines 10, 66)
- Modify: `backend/src/tasks/screencast_tasks/_demo.py` (lines 15, 134)
- Modify: `backend/src/tasks/screencast_tasks/_pipeline.py` (lines 15, 181)
- Modify: `backend/src/routes/screencast/audio.py` (full file)

- [ ] **Step 1: Rename `tts_audio/` → `render_cache/` in `generation.py`**

In `backend/src/services/screencast/generation.py`, replace the four references:
- Line 76: `f"tts_audio/slide_{i:03d}.mp3"` → `f"render_cache/slide_{i:03d}.mp3"`
- Line 79: `f"tts_audio/slide_{i:03d}_align.json"` → `f"render_cache/slide_{i:03d}_align.json"`
- Line 110: same change
- Line 112: same change

Also: this file calls `get_job_file(job_uuid, ...)` and `save_job_file(job_uuid, ...)` — these now need `user_id`. Trace the function signature: the function that wraps these calls receives `job_uuid`. Add `user_id: int` to that function's signature (find it via `grep`):

```bash
grep -n "def.*job_uuid" backend/src/services/screencast/generation.py
```

For the function that wraps the get/save calls, add `user_id: int` parameter, then update:
- `get_job_file(job_uuid, …)` → `get_job_file(user_id, job_uuid, …)`
- `save_job_file(job_uuid, …)` → `save_job_file(user_id, job_uuid, …)`

Then update that function's caller(s) (in `_demo.py`, `_pipeline.py`, `_render.py`) to pass `user_id`.

- [ ] **Step 2: Update `_render.py` (clear_render_cache)**

Edit `backend/src/tasks/screencast_tasks/_render.py`:

Line 10:
```python
from src.storage import clear_render_cache, save_result_and_evict
```

Line 66 (find the user_id from the job/translate_job_uuid context — read the function ~5 lines up to confirm `user_id` is available; if not, fetch via `get_job(translate_job_uuid)["user_id"]`):
```python
clear_render_cache(user_id, translate_job_uuid)
```

- [ ] **Step 3: Update `routes/screencast/render.py`**

Line 11:
```python
from src.storage import clear_render_cache, delete_job_folder, job_file_exists, save_job_file
```

Line 74 — context is a route handler that already authenticates the user. Use the authenticated `user["id"]`:
```python
clear_render_cache(user["id"], body.translate_job_uuid)
```

- [ ] **Step 4: Update `_demo.py` (save_audio_cache)**

Line 15 import block already imports `save_audio_cache`. Line 134:
```python
save_audio_cache(user_id, job_uuid, audio_bytes_list)
```

`user_id` must be in scope — read 20 lines up to confirm. Tasks receive `job_uuid`; resolve `user_id` once at the top of the task:
```python
from src.features.jobs.repository import get_job
job_row = get_job(job_uuid)
user_id = job_row["user_id"]
```

- [ ] **Step 5: Update `_pipeline.py` (save_audio_cache)**

Line 181:
```python
save_audio_cache(user_id, job_uuid, audio_bytes_list)
```
Same pattern as `_demo.py` — resolve `user_id` once at the top of the Celery task.

- [ ] **Step 6: Update `routes/screencast/audio.py` — resolve user_id from job**

Replace the file content:

```python
"""Audio-Download-Endpoints: Einzel-Slide-MP3 und ZIP-Bundle aller Folien."""

import zipfile
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.features.jobs.repository import get_job
from src.storage import get_all_audio_slides, get_audio_slide, get_audio_slide_count

router = APIRouter(tags=["screencast: audio"])


def _resolve_user_id(audio_id: str) -> int:
    job = get_job(audio_id)
    if not job:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    return job["user_id"]


@router.get("/screencast/audio/{audio_id}/zip")
async def download_all_slide_audio_zip(audio_id: str):
    user_id = _resolve_user_id(audio_id)
    slides = get_all_audio_slides(user_id, audio_id)
    if not slides:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")

    buf = BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for filename, data in slides:
            zf.writestr(filename, data)
    buf.seek(0)
    zip_bytes = buf.read()

    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={
            "Content-Length": str(len(zip_bytes)),
            "Content-Disposition": 'attachment; filename="folien_audio.zip"',
        },
    )


@router.get("/screencast/audio/{audio_id}/{slide_index}")
async def download_slide_audio(audio_id: str, slide_index: int):
    user_id = _resolve_user_id(audio_id)
    count = get_audio_slide_count(user_id, audio_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Audio nicht gefunden (abgelaufen oder ungültige ID)")
    if slide_index < 0 or slide_index >= count:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    audio_bytes = get_audio_slide(user_id, audio_id, slide_index)
    if audio_bytes is None:
        raise HTTPException(status_code=404, detail=f"Folie {slide_index + 1} nicht gefunden")

    filename = f"slide_{slide_index + 1:02d}.mp3"
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(len(audio_bytes)),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
```

- [ ] **Step 7: Find and update remaining storage callers in screencast_tasks/**

```bash
grep -rn "save_queue_file\|save_job_file\|get_job_file\|save_result_file\|save_result_json\|save_result_meta\|load_result_meta\|delete_job_folder\|job_file_exists\|save_result_and_evict" backend/src/tasks/screencast_tasks/ backend/src/routes/screencast/ backend/src/services/screencast/
```

For each match: ensure `user_id` is the first positional argument. Resolve `user_id` from `get_job(job_uuid)["user_id"]` once per task/handler.

- [ ] **Step 8: Smoke check — backend reloads cleanly**

```bash
docker compose logs kis-backend --tail 50 | grep -E "ERROR|TypeError|ImportError" || echo "clean"
```
Expected: `clean`.

- [ ] **Step 9: Stage + ask user to commit**

```bash
git add -u backend/src/services/screencast/ backend/src/routes/screencast/ backend/src/tasks/screencast_tasks/
git status
```
Wait for user approval.

---

## Task 6: AIA caller migration (kia → aia, new prefixes)

**Files:**
- Modify: `backend/src/features/ai_assistant/tasks/_helpers.py` (lines 38–50)
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (lines 165–175)
- Modify: `backend/src/features/ai_assistant/routes/sources/_pdf.py` (line 210, line 248)

- [ ] **Step 1: Rewrite `_save_aia_output` in `tasks/_helpers.py`**

Replace lines 38–50:

```python
def _save_aia_output(user_id: int, module_uuid: str, filename: str, data: bytes) -> str:
    """Save an AIA output file (presentation, mindmap, etc.) under users/{user_id}/aia/."""
    from src.storage import USE_S3, aia_output_key
    key = aia_output_key(user_id, module_uuid, filename)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)
```

- [ ] **Step 2: Update callers of `_save_aia_output`**

```bash
grep -rn "_save_aia_output" backend/src/features/ai_assistant/
```

Each call site passes `username` today. Replace with `user_id` from the auth context (every AIA route already has `user["id"]`).

Example:
```python
# Before
_save_aia_output(user["ldap_username"], module_uuid, filename, data)
# After
_save_aia_output(user["id"], module_uuid, filename, data)
```

- [ ] **Step 3: Rewrite `_save_source_file` in `routes/_helpers.py`**

Replace lines 165–175:

```python
def _save_source_file(user_id: int, module_uuid: str, source_uuid: str, ext: str, data: bytes) -> str:
    from src.storage import USE_S3, aia_source_key
    key = aia_source_key(user_id, module_uuid, source_uuid, ext)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    from src.storage import STORAGE_ROOT
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)
```

- [ ] **Step 4: Update callers of `_save_source_file`**

```bash
grep -rn "_save_source_file" backend/src/features/ai_assistant/
```

Each call passes `username` today; replace with `user_id`.

- [ ] **Step 5: Verify markdown sidecar in `_pdf.py` works**

Read `backend/src/features/ai_assistant/routes/sources/_pdf.py` line 210:
```python
md_path = str(Path(source["file_path"]).with_suffix(".md"))
```

This derives `.md` from `source["file_path"]`. After Task 6 Step 3, `file_path` is the new `aia_source_key(...)` like `users/7/aia/modules/abc/sources/xyz.pdf`. `Path(...).with_suffix(".md")` produces `users/7/aia/modules/abc/sources/xyz.md` — correct, no change needed.

Confirm the line doesn't need an edit:
```bash
grep -n "with_suffix" backend/src/features/ai_assistant/routes/sources/_pdf.py
```

- [ ] **Step 6: Verify `_streaming.py` and `_helpers.py` (transcript paths)**

```bash
grep -n "base_key\|_transcript" backend/src/features/ai_assistant/routes/sources/_streaming.py backend/src/features/ai_assistant/routes/_helpers.py backend/src/features/ai_assistant/tasks/ingestion.py
```

Each one derives transcript keys from `source["file_path"]` via `rsplit(".", 1)[0]`. Same logic works for the new `users/{user_id}/aia/...` prefix. No change needed.

- [ ] **Step 7: Smoke check — AIA imports + a route hit**

```bash
docker compose exec kis-backend python -c "
from src.features.ai_assistant.routes._helpers import _save_source_file
from src.features.ai_assistant.tasks._helpers import _save_aia_output
import inspect
assert 'user_id' in inspect.signature(_save_source_file).parameters
assert 'user_id' in inspect.signature(_save_aia_output).parameters
print('aia migrated')
"
```
Expected: `aia migrated`.

- [ ] **Step 8: Stage + ask user to commit**

```bash
git add -u backend/src/features/ai_assistant/
git status
```
Wait for user approval.

---

## Task 7: Wipe + manual E2E verification

**Files:**
- Create: `private/migrate-storage.md` (gitignored docs)

- [ ] **Step 1: Create wipe documentation**

Write to `private/migrate-storage.md`:

```markdown
# Storage Refactor — Wipe & Verification

Branch: `refactor/storage`. Bucket + DB are wiped before the new code goes live.

## 1. Stop backend + workers

\`\`\`bash
docker compose stop kis-backend kis-celery-worker
\`\`\`

## 2. Wipe MinIO bucket

\`\`\`bash
docker compose exec kis-minio mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
docker compose exec kis-minio mc rm --recursive --force local/kis
\`\`\`

(Bucket itself is recreated by `init_storage()` on next backend start.)

## 3. Truncate DB tables

\`\`\`bash
docker compose exec kis-postgres psql -U kis -d kis -c "TRUNCATE jobs, aia_sources, aia_modules CASCADE;"
\`\`\`

CASCADE cleans all FK-dependent tables (chunks, summaries, mindmaps, glossary, exercises, schedules, etc).

## 4. Restart backend (applies DB-DROP migration + lifecycle policy)

\`\`\`bash
docker compose start kis-backend kis-celery-worker
docker compose logs kis-backend --tail 50 | grep -E "init_db|lifecycle|ERROR"
\`\`\`

Expected: clean startup, lifecycle policy applied (or warning logged if MinIO permission missing).

## 5. Verify column dropped

\`\`\`bash
docker compose exec kis-postgres psql -U kis -d kis -c "\\d jobs" | grep -i username
\`\`\`
Expected: empty output (column gone).
```

- [ ] **Step 2: Run the wipe (user-driven, when ready)**

User executes the steps in `private/migrate-storage.md`. Confirm with:
```bash
docker compose exec kis-postgres psql -U kis -d kis -c "SELECT COUNT(*) FROM jobs;"
docker compose exec kis-minio mc ls local/kis/ || echo "empty"
```
Expected: `0` jobs, empty bucket.

- [ ] **Step 3: E2E — Screencast (translate → render → audio)**

Manually in browser (frontend on `http://localhost:3000`):
1. Login as test user
2. Upload a small PPTX → trigger translate → wait for "awaiting_user"
3. Edit a script → render → wait for completion
4. Download single-slide MP3 + ZIP bundle → both play
5. Verify keys: `docker compose exec kis-minio mc ls local/kis/users/{your_user_id}/jobs/ --recursive`
   Expected: `input.pptx`, `output.mp4`, `result.json`, `meta.json`, `audio/slide_NNN.mp3`, `render_cache/slide_NNN.mp3`

- [ ] **Step 4: E2E — AIA module (source upload → chat → output)**

1. Create new AIA module
2. Upload PDF source → wait for ingestion
3. Verify keys: `docker compose exec kis-minio mc ls local/kis/users/{your_user_id}/aia/modules/{module_uuid}/ --recursive`
   Expected: `sources/{source_uuid}.pdf`, `sources/{source_uuid}.md`, `sources/{source_uuid}_transcript.*` (for video/audio)
4. Send chat message — answer references the source
5. Generate a flashcard set → output appears under `outputs/`

- [ ] **Step 5: E2E — Re-render clears render_cache**

1. Re-render the same screencast job
2. Before re-render starts: `mc ls local/kis/users/{uid}/jobs/{job_uuid}/render_cache/` should show old slides
3. After re-render starts: `render_cache/` is empty (briefly), then refills as TTS synthesizes
4. Confirm `clear_render_cache` was called (logs)

- [ ] **Step 6: E2E — pptx_tmp lifecycle + delete_pptx_tmp**

1. Trigger a translate flow (writes `tmp/pptx/{file_id}.pptx`)
2. Verify in MinIO: `mc ls local/kis/tmp/pptx/`
3. After render completes (which calls `delete_pptx_tmp`): file is gone
4. Lifecycle rule active: `mc ilm ls local/kis` should list `tmp-expire-1d`

- [ ] **Step 7: Stage + ask user to commit**

```bash
git add private/migrate-storage.md
git status
```
Wait for user approval. After commit: feature branch is ready for PR review.

---

## Self-Review checklist (executed by plan author after writing this plan)

- [x] Spec coverage: every Goal in the spec maps to at least one task above
  - G1 stable keys → Task 1 (prefix helpers) + Task 5/6 (callers)
  - G2 pure path → Task 1 (no DB call) + Task 2 (signature change)
  - G3 consistent layout → Task 1 (prefixes) + Task 5/6 (rename kia→aia, tts_audio→render_cache)
  - G4 batch perf → Task 1 (delete_prefix) + Task 2 (parallel save_audio_cache)
  - G5 aia naming → Task 6
  - G6 lifecycle → Task 1 (init_lifecycle_policy)
  - G7 dead code → Task 3
- [x] Placeholder scan: no TBD/TODO; every step has concrete code or command
- [x] Type consistency: all signatures use `user_id: int, job_uuid: str`; `clear_render_cache` consistent across Task 1/2/5; `aia_source_key`/`aia_output_key` defined in Task 1, used in Task 6
- [x] Commit policy: every task ends with "Stage + ask user to commit", honoring MEMORY.md `feedback_no_autocommit`
