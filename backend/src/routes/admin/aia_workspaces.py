"""Admin endpoints: export / import / reindex an AIA workspace.

Use case: dev testing — wipe DB or experiment with state, then re-import a
previously exported workspace bundle to skip re-upload + re-embedding (no
LLM/embedding tokens burned).

Bundle layout (ZIP):
    manifest.json          — version, exported_at, embedding_model, fingerprint, counts, included extras
    workspace.json         — workspace row (without internal id/user_id)
    sources.json           — sources + chunks (with embeddings as float lists)
    files/<source_uuid><ext>            — original uploaded files
    files/<source_uuid>_transcript.*    — Whisper transcript + VTTs (always included for media)

Optional, opt-in via query flags on export, permissively read on import:
    glossary.json   — aia_glossary_entries (per source)
    summaries.json  — aia_paragraph_summaries (per source)
    notes.json      — aia_notes (per workspace + user; user_id reassigned to importer)
    schedule.json   — aia_schedule_entries (per workspace + user; user_id reassigned)
    studio.json     — aia_mindmaps + aia_data_tables + aia_exercise_sets/items

Import is permissive: even on embedding-model mismatch the bundle is loaded;
the workspace just lands in a "needs_reindex" state and the admin clicks the
reindex button to re-embed against the current provider.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg2.extras
import threading
from queue import Queue

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from src import database as db
from src.core.db.pool import get_connection
from src.dependencies import get_admin_user
from src.i18n import get_locale
from src.storage import (
    USE_S3,
    aia_source_key,
    get_file,
    STORAGE_ROOT,
)

router = APIRouter(tags=["admin: aia-workspaces"])

EXPORT_VERSION = 1


# ─── Helpers: workspace + chunks ────────────────────────────────────────────

def _workspace_export_dict(workspace: dict) -> dict:
    """Strip DB-internal fields from a workspace row for export."""
    keep = (
        "uuid", "title", "description", "is_active", "status",
        "embedding_model", "embedding_fingerprint",
        "transcript_translation_mode", "transcript_default_lang", "summary_mode",
    )
    return {k: workspace.get(k) for k in keep}


def _fetch_chunks_with_embeddings(source_id: int) -> list[dict]:
    """Read chunks + embeddings as JSON-friendly dicts. Embeddings come back as
    lists of floats; missing embeddings as None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT page_number, content, start_time, end_time,
                          embedding::text AS embedding_text
                   FROM aia_chunks
                   WHERE source_id = %s
                   ORDER BY COALESCE(start_time, 0), page_number, id""",
                (source_id,),
            )
            rows = cur.fetchall()

    out: list[dict] = []
    for row in rows:
        embedding = None
        if row["embedding_text"]:
            try:
                embedding = json.loads(row["embedding_text"])
            except json.JSONDecodeError:
                embedding = None
        out.append({
            "page_number": row["page_number"],
            "content": row["content"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "embedding": embedding,
        })
    return out


def _bulk_insert_chunks(source_id: int, chunks: list[dict]) -> int:
    """Insert chunks for a source. Embeddings are written as pgvector if present."""
    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for c in chunks:
                embedding = c.get("embedding")
                embedding_param = str(embedding) if embedding else None
                cur.execute(
                    """INSERT INTO aia_chunks
                       (source_id, page_number, content, embedding,
                        start_time, end_time, search_vector)
                       VALUES (%s, %s, %s, %s::vector, %s, %s,
                               to_tsvector('german', %s))""",
                    (
                        source_id, c["page_number"], c["content"], embedding_param,
                        c.get("start_time"), c.get("end_time"), c["content"],
                    ),
                )
                inserted += 1
        conn.commit()
    return inserted


def _save_imported_file(user_id: int, workspace_uuid: str, source_uuid: str,
                         ext: str, data: bytes) -> str:
    key = aia_source_key(user_id, workspace_uuid, source_uuid, ext)
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)


# ─── Helpers: transcript artifacts ──────────────────────────────────────────

def _list_transcript_artifacts(file_path_stored: str, source_uuid: str) -> list[tuple[str, str]]:
    """List storage keys for transcript artifacts that live next to a source file.

    Whisper writes <base>_transcript.txt and <base>_transcript.<lang>.vtt next
    to the source. Returns a list of (storage_key, archive_basename) tuples.
    """
    out: list[tuple[str, str]] = []
    if not file_path_stored:
        return out

    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        # S3 key looks like: users/.../sources/<source_uuid><ext>
        # → list the sources/ "folder" and filter for "<source_uuid>_transcript"
        prefix = file_path_stored.rsplit("/", 1)[0] + "/"
        try:
            paginator = _s3().get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=_S3_BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    name = key.rsplit("/", 1)[-1]
                    if name.startswith(f"{source_uuid}_transcript"):
                        out.append((key, name))
        except Exception as e:
            logger.warning("Transcript list (S3) failed for {}: {}", source_uuid, e)
        return out

    # Local mode: file_path_stored is an absolute path
    parent = Path(file_path_stored).parent
    if not parent.exists():
        return out
    for p in parent.iterdir():
        if p.is_file() and p.name.startswith(f"{source_uuid}_transcript"):
            out.append((str(p), p.name))
    return out


def _save_transcript_artifact(user_id: int, workspace_uuid: str, basename: str, data: bytes) -> str:
    """Place a transcript artifact next to where a source file would live."""
    # Sources directory key: users/{uid}/aia/workspaces/{workspace_uuid}/sources/{name}
    key = f"{aia_source_key(user_id, workspace_uuid, '', '').rsplit('/', 1)[0]}/{basename}"
    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=key, Body=data)
        return key
    dest = STORAGE_ROOT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(dest)


# ─── Helpers: optional extras ───────────────────────────────────────────────

def _fetch_glossary(source_id_to_uuid: dict[int, str]) -> list[dict]:
    if not source_id_to_uuid:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT source_id, term_de, term_en, definition, definition_en,
                          example_sentence, example_sentence_en, page_number
                   FROM aia_glossary_entries WHERE source_id = ANY(%s)
                   ORDER BY id""",
                (list(source_id_to_uuid.keys()),),
            )
            rows = cur.fetchall()
    return [
        {**{k: v for k, v in dict(r).items() if k != "source_id"},
         "source_uuid": source_id_to_uuid.get(r["source_id"])}
        for r in rows if source_id_to_uuid.get(r["source_id"])
    ]


def _fetch_paragraph_summaries(source_id_to_uuid: dict[int, str]) -> list[dict]:
    if not source_id_to_uuid:
        return []
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT source_id, page_number, block_index,
                          bbox_x0, bbox_y0, bbox_x1, bbox_y1, content, summary
                   FROM aia_paragraph_summaries WHERE source_id = ANY(%s)
                   ORDER BY id""",
                (list(source_id_to_uuid.keys()),),
            )
            rows = cur.fetchall()
    return [
        {**{k: v for k, v in dict(r).items() if k != "source_id"},
         "source_uuid": source_id_to_uuid.get(r["source_id"])}
        for r in rows if source_id_to_uuid.get(r["source_id"])
    ]


def _fetch_notes(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT title, content, source_uuids, source_pages, popup_selection
                   FROM aia_notes WHERE workspace_id = %s ORDER BY id""",
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def _fetch_schedule(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT type, title, description, due_date, due_time,
                          is_optional, is_checked, checked_at, origin, source_refs
                   FROM aia_schedule_entries WHERE workspace_id = %s ORDER BY id""",
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def _fetch_studio(workspace_id: int, source_id_to_uuid: dict[int, str]) -> dict:
    """mindmaps + data_tables + exercise_sets (with items). source_ids on
    mindmaps/data_tables are translated from internal IDs to UUIDs."""
    def _ids_to_uuids(ids):
        if not ids:
            return []
        return [source_id_to_uuid[i] for i in ids if i in source_id_to_uuid]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT source_ids, status, mindmap, error
                   FROM aia_mindmaps WHERE workspace_id = %s ORDER BY id""",
                (workspace_id,),
            )
            mindmaps = []
            for r in cur.fetchall():
                row = dict(r)
                ids = row["source_ids"] or []
                row["source_uuids"] = _ids_to_uuids(ids)
                row.pop("source_ids", None)
                mindmaps.append(row)

            cur.execute(
                """SELECT source_ids, status, title, table_data, sources, error
                   FROM aia_data_tables WHERE workspace_id = %s ORDER BY id""",
                (workspace_id,),
            )
            data_tables = []
            for r in cur.fetchall():
                row = dict(r)
                ids = row["source_ids"] or []
                row["source_uuids"] = _ids_to_uuids(ids)
                row.pop("source_ids", None)
                data_tables.append(row)

            cur.execute(
                """SELECT id, tool, title, mode, source_uuid, card_count, status, last_run_start
                   FROM aia_exercise_sets WHERE workspace_id = %s ORDER BY id""",
                (workspace_id,),
            )
            sets = [dict(r) for r in cur.fetchall()]
            set_ids = [s["id"] for s in sets]

            items_by_set: dict[int, list[dict]] = {sid: [] for sid in set_ids}
            if set_ids:
                cur.execute(
                    """SELECT set_id, position, front, back, options, correct_idx,
                              source_label, page_number, explanation, start_time,
                              sources, back_en, extras
                       FROM aia_exercise_items WHERE set_id = ANY(%s) ORDER BY set_id, position, id""",
                    (set_ids,),
                )
                for r in cur.fetchall():
                    row = dict(r)
                    items_by_set.setdefault(row["set_id"], []).append(
                        {k: v for k, v in row.items() if k != "set_id"}
                    )

    exercise_sets = []
    for s in sets:
        sid = s.pop("id")
        s["items"] = items_by_set.get(sid, [])
        exercise_sets.append(s)

    return {"mindmaps": mindmaps, "data_tables": data_tables, "exercise_sets": exercise_sets}


# ─── Insert helpers (import side) ───────────────────────────────────────────

def _insert_glossary(rows: list[dict], uuid_to_source_id: dict[str, int]) -> int:
    if not rows:
        return 0
    n = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for g in rows:
                sid = uuid_to_source_id.get(g.get("source_uuid"))
                if not sid:
                    continue
                cur.execute(
                    """INSERT INTO aia_glossary_entries
                       (source_id, term_de, term_en, definition, definition_en,
                        example_sentence, example_sentence_en, page_number)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (sid, g.get("term_de") or "", g.get("term_en") or "",
                     g.get("definition") or "", g.get("definition_en"),
                     g.get("example_sentence"), g.get("example_sentence_en"),
                     g.get("page_number")),
                )
                n += 1
        conn.commit()
    return n


def _insert_summaries(rows: list[dict], uuid_to_source_id: dict[str, int]) -> int:
    if not rows:
        return 0
    n = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for s in rows:
                sid = uuid_to_source_id.get(s.get("source_uuid"))
                if not sid:
                    continue
                cur.execute(
                    """INSERT INTO aia_paragraph_summaries
                       (source_id, page_number, block_index,
                        bbox_x0, bbox_y0, bbox_x1, bbox_y1, content, summary)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (sid, s.get("page_number"), s.get("block_index"),
                     s.get("bbox_x0"), s.get("bbox_y0"), s.get("bbox_x1"), s.get("bbox_y1"),
                     s.get("content") or "", s.get("summary") or ""),
                )
                n += 1
        conn.commit()
    return n


def _insert_notes(workspace_id: int, user_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0
    n = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for note in rows:
                cur.execute(
                    """INSERT INTO aia_notes
                       (workspace_id, user_id, title, content,
                        source_uuids, source_pages, popup_selection)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (workspace_id, user_id, note.get("title"), note.get("content") or "",
                     json.dumps(note["source_uuids"]) if note.get("source_uuids") is not None else None,
                     json.dumps(note["source_pages"]) if note.get("source_pages") is not None else None,
                     json.dumps(note["popup_selection"]) if note.get("popup_selection") is not None else None),
                )
                n += 1
        conn.commit()
    return n


def _insert_schedule(workspace_id: int, user_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0
    n = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for e in rows:
                cur.execute(
                    """INSERT INTO aia_schedule_entries
                       (workspace_id, user_id, type, title, description,
                        due_date, due_time, is_optional, is_checked, checked_at,
                        origin, source_refs)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (workspace_id, user_id, e.get("type"), e.get("title") or "",
                     e.get("description"), e.get("due_date"), e.get("due_time"),
                     bool(e.get("is_optional")), bool(e.get("is_checked")), e.get("checked_at"),
                     e.get("origin") or "manual",
                     json.dumps(e["source_refs"]) if e.get("source_refs") is not None else "[]"),
                )
                n += 1
        conn.commit()
    return n


def _insert_studio(workspace_id: int, user_id: int, payload: dict,
                    uuid_to_source_id: dict[str, int]) -> dict:
    counts = {"mindmaps": 0, "data_tables": 0, "exercise_sets": 0, "exercise_items": 0}

    def _uuids_to_ids(uuids):
        return [uuid_to_source_id[u] for u in (uuids or []) if u in uuid_to_source_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            for m in payload.get("mindmaps") or []:
                cur.execute(
                    """INSERT INTO aia_mindmaps
                       (workspace_id, user_id, source_ids, status, mindmap, error)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (workspace_id, user_id,
                     json.dumps(_uuids_to_ids(m.get("source_uuids"))),
                     m.get("status") or "ready",
                     json.dumps(m["mindmap"]) if m.get("mindmap") is not None else None,
                     m.get("error")),
                )
                counts["mindmaps"] += 1
            for d in payload.get("data_tables") or []:
                cur.execute(
                    """INSERT INTO aia_data_tables
                       (workspace_id, user_id, source_ids, status, title, table_data, sources, error)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (workspace_id, user_id,
                     json.dumps(_uuids_to_ids(d.get("source_uuids"))),
                     d.get("status") or "ready", d.get("title"),
                     json.dumps(d["table_data"]) if d.get("table_data") is not None else None,
                     json.dumps(d["sources"]) if d.get("sources") is not None else None,
                     d.get("error")),
                )
                counts["data_tables"] += 1
            for s in payload.get("exercise_sets") or []:
                cur.execute(
                    """INSERT INTO aia_exercise_sets
                       (workspace_id, user_id, tool, title, mode, source_uuid,
                        card_count, status, last_run_start)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    (workspace_id, user_id, s.get("tool") or "",
                     s.get("title") or "", s.get("mode") or "glossary",
                     s.get("source_uuid"), s.get("card_count") or 0,
                     s.get("status") or "ready", s.get("last_run_start")),
                )
                new_set_id = cur.fetchone()[0]
                counts["exercise_sets"] += 1
                for item in s.get("items") or []:
                    cur.execute(
                        """INSERT INTO aia_exercise_items
                           (set_id, position, front, back, options, correct_idx,
                            source_label, page_number, explanation, start_time,
                            sources, back_en, extras)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (new_set_id, item.get("position") or 0,
                         item.get("front") or "", item.get("back") or "",
                         json.dumps(item["options"]) if item.get("options") is not None else None,
                         item.get("correct_idx"), item.get("source_label"),
                         item.get("page_number"), item.get("explanation"),
                         item.get("start_time"),
                         json.dumps(item["sources"]) if item.get("sources") is not None else None,
                         item.get("back_en"),
                         json.dumps(item["extras"]) if item.get("extras") is not None else None),
                    )
                    counts["exercise_items"] += 1
        conn.commit()
    return counts


# ─── List ───────────────────────────────────────────────────────────────────

@router.get("/aia-workspaces")
async def list_workspaces(_admin=Depends(get_admin_user)):
    """Return all workspaces with owner + source count, for the admin export UI."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT m.uuid, m.title, m.is_active, m.embedding_fingerprint,
                          u.display_name AS owner,
                          (SELECT COUNT(*) FROM aia_sources s WHERE s.workspace_id = m.id) AS source_count,
                          (SELECT COUNT(*) FROM aia_chunks c JOIN aia_sources s ON s.id = c.source_id
                           WHERE s.workspace_id = m.id) AS chunk_count
                   FROM aia_workspaces m
                   LEFT JOIN users u ON u.id = m.user_id
                   ORDER BY m.title ASC"""
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ─── Export ─────────────────────────────────────────────────────────────────

@router.get("/aia-workspaces/{workspace_uuid}/export")
async def export_workspace(
    workspace_uuid: str,
    glossary: bool = False,
    notes: bool = False,
    schedule: bool = False,
    summaries: bool = False,
    studio: bool = False,
    _admin=Depends(get_admin_user),
):
    """Stream a ZIP bundle of one workspace.

    Always included: workspace meta, sources, chunks (+embeddings), original
    files, and any transcript artifacts (txt + VTTs) that live next to media
    sources — those are token-expensive (Whisper + DeepL/LLM translation).

    Optional via query flags (each maps to one extra JSON entry in the bundle):
        glossary, notes, schedule, summaries, studio
    """
    workspace = db.get_aia_workspace(workspace_uuid)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    sources = db.get_aia_sources_by_workspace(workspace["id"])
    source_id_to_uuid = {s["id"]: s["uuid"] for s in sources}

    sources_payload: list[dict] = []
    total_chunks = 0
    for s in sources:
        ext = os.path.splitext(s.get("filename") or "")[1] or ""
        chunks = _fetch_chunks_with_embeddings(s["id"])
        total_chunks += len(chunks)
        sources_payload.append({
            "uuid": s["uuid"],
            "filename": s["filename"],
            "file_type": s["file_type"],
            "file_ext": ext,
            "status": s["status"],
            "chunk_count": s.get("chunk_count") or 0,
            "embedding_model": s.get("embedding_model") or "",
            "toc": s.get("toc"),
            "summaries_status": s.get("summaries_status") or "none",
            "duration": s.get("duration"),
            "language": s.get("language"),
            "chunks": chunks,
        })

    extras_meta: list[str] = []
    extras_data: dict[str, object] = {}
    if glossary:
        extras_data["glossary"] = _fetch_glossary(source_id_to_uuid)
        extras_meta.append("glossary")
    if summaries:
        extras_data["summaries"] = _fetch_paragraph_summaries(source_id_to_uuid)
        extras_meta.append("summaries")
    if notes:
        extras_data["notes"] = _fetch_notes(workspace["id"])
        extras_meta.append("notes")
    if schedule:
        extras_data["schedule"] = _fetch_schedule(workspace["id"])
        extras_meta.append("schedule")
    if studio:
        extras_data["studio"] = _fetch_studio(workspace["id"], source_id_to_uuid)
        extras_meta.append("studio")

    manifest = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": workspace.get("embedding_model") or "",
        "embedding_fingerprint": workspace.get("embedding_fingerprint") or "",
        "source_count": len(sources_payload),
        "chunk_count": total_chunks,
        "extras": extras_meta,
    }

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in (workspace.get("title") or "workspace"))
    filename = f"aia-workspace-{safe_title}-{workspace_uuid[:8]}.zip"
    logger.info("Workspace export {}: {} sources, {} chunks, extras={} (streaming)",
                workspace_uuid, len(sources_payload), total_chunks, extras_meta)

    # Stream the ZIP body progressively while it is being built. A producer
    # thread writes ZipFile entries into a queue via a non-seekable wrapper;
    # the response generator yields each chunk to the client as it arrives.
    # Result: response headers (incl. Content-Disposition) leave immediately,
    # the browser shows its native download UI right away, and the body
    # trickles in while the server reads source files / DB rows.
    return StreamingResponse(
        _stream_workspace_zip(workspace, sources, sources_payload, extras_data, manifest, workspace_uuid),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stream_workspace_zip(workspace, sources, sources_payload, extras_data, manifest, workspace_uuid):
    """Yield raw bytes of a ZIP archive as it is being built in a worker thread."""
    sentinel = object()
    q: Queue = Queue(maxsize=4)
    error_holder: dict[str, BaseException] = {}

    class _StreamWriter:
        """Non-seekable file-like wrapper. zipfile detects seekable()=False and
        falls back to streaming-write mode (data descriptors after each entry,
        central directory at the end). All writes are pushed onto the queue."""
        def write(self, data):
            if data:
                q.put(bytes(data))
            return len(data)
        def flush(self):
            pass
        def seekable(self):
            return False
        def tell(self):
            raise OSError("stream is not seekable")
        def seek(self, *args, **kwargs):
            raise OSError("stream is not seekable")

    def _produce():
        try:
            writer = _StreamWriter()
            with zipfile.ZipFile(writer, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
                zf.writestr("workspace.json", json.dumps(_workspace_export_dict(workspace), indent=2, default=str))
                zf.writestr("sources.json", json.dumps(sources_payload, default=str))
                for name, payload in extras_data.items():
                    zf.writestr(f"{name}.json", json.dumps(payload, default=str))

                for s in sources:
                    ext = os.path.splitext(s.get("filename") or "")[1] or ""
                    try:
                        zf.writestr(f"files/{s['uuid']}{ext}", get_file(s["file_path"]))
                    except Exception as e:
                        logger.warning("Workspace export {}: source file {} unreadable ({}), skipping",
                                       workspace_uuid, s["uuid"], e)
                    for art_key, art_name in _list_transcript_artifacts(s.get("file_path") or "", s["uuid"]):
                        try:
                            zf.writestr(f"files/{art_name}", get_file(art_key))
                        except Exception as e:
                            logger.warning("Workspace export {}: transcript {} unreadable ({}), skipping",
                                           workspace_uuid, art_name, e)
        except BaseException as e:
            error_holder["err"] = e
        finally:
            q.put(sentinel)

    threading.Thread(target=_produce, name=f"aia-export-{workspace_uuid[:8]}", daemon=True).start()

    while True:
        item = q.get()
        if item is sentinel:
            break
        yield item

    if "err" in error_holder:
        # The client may have already received a partial ZIP; logging is the best we can do.
        logger.error("Workspace export {} failed mid-stream: {}", workspace_uuid, error_holder["err"])


# ─── Import ─────────────────────────────────────────────────────────────────

@router.post("/aia-workspaces/import")
async def import_workspace(
    file: UploadFile = File(...),
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Import a workspace bundle. Permissive on extras (anything not in the
    bundle is simply skipped). Conflicts: same UUID → 409, delete first."""
    admin_user_id = _admin["user_id"]

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.close()

        try:
            zf = zipfile.ZipFile(tmp.name, "r")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="not a valid zip archive")

        with zf:
            try:
                manifest = json.loads(zf.read("manifest.json"))
                workspace_data = json.loads(zf.read("workspace.json"))
                sources_data = json.loads(zf.read("sources.json"))
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"bundle missing required entry: {e}")
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"bundle metadata invalid: {e}")

            if manifest.get("version") != EXPORT_VERSION:
                raise HTTPException(
                    status_code=400,
                    detail=f"unsupported bundle version {manifest.get('version')!r} (expected {EXPORT_VERSION})",
                )

            workspace_uuid = workspace_data.get("uuid")
            if not workspace_uuid:
                raise HTTPException(status_code=400, detail="workspace.uuid missing")

            if db.get_aia_workspace(workspace_uuid) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"workspace {workspace_uuid} already exists — delete it first",
                )

            # 1. Workspace row
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO aia_workspaces
                           (uuid, user_id, title, description, is_active, status,
                            embedding_model, embedding_fingerprint,
                            transcript_translation_mode, transcript_default_lang, summary_mode)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id""",
                        (
                            workspace_uuid, admin_user_id,
                            workspace_data.get("title") or "Imported workspace",
                            workspace_data.get("description"),
                            False,  # always inactive on import
                            workspace_data.get("status") or "ready",
                            workspace_data.get("embedding_model") or "",
                            workspace_data.get("embedding_fingerprint"),
                            workspace_data.get("transcript_translation_mode") or "manual",
                            workspace_data.get("transcript_default_lang") or "both",
                            workspace_data.get("summary_mode") or "manual",
                        ),
                    )
                    workspace_id = cur.fetchone()[0]
                conn.commit()

            # 2. Sources + files (+ transcripts) + chunks
            sources_imported = 0
            chunks_imported = 0
            files_missing = 0
            transcripts_restored = 0
            uuid_to_source_id: dict[str, int] = {}

            for s in sources_data:
                source_uuid = s["uuid"]
                ext = s.get("file_ext") or ""
                file_path: str | None = None
                try:
                    file_data = zf.read(f"files/{source_uuid}{ext}")
                    file_path = _save_imported_file(
                        admin_user_id, workspace_uuid, source_uuid, ext, file_data,
                    )
                except KeyError:
                    files_missing += 1
                    logger.warning("Workspace import {}: file for source {} missing in bundle",
                                   workspace_uuid, source_uuid)

                # Transcript artifacts (if present in bundle)
                for entry in zf.namelist():
                    if not entry.startswith(f"files/{source_uuid}_transcript"):
                        continue
                    basename = entry.removeprefix("files/")
                    try:
                        _save_transcript_artifact(
                            admin_user_id, workspace_uuid, basename, zf.read(entry),
                        )
                        transcripts_restored += 1
                    except Exception as e:
                        logger.warning("Workspace import {}: transcript {} restore failed ({})",
                                       workspace_uuid, basename, e)

                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO aia_sources
                               (workspace_id, uuid, filename, file_path, file_type,
                                status, chunk_count, embedding_model, toc,
                                summaries_status, duration, language)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                               RETURNING id""",
                            (
                                workspace_id, source_uuid, s.get("filename") or "",
                                file_path or "", s.get("file_type") or "",
                                s.get("status") or "ready",
                                s.get("chunk_count") or 0, s.get("embedding_model") or "",
                                json.dumps(s["toc"]) if s.get("toc") is not None else None,
                                s.get("summaries_status") or "none",
                                s.get("duration"), s.get("language"),
                            ),
                        )
                        source_id = cur.fetchone()[0]
                    conn.commit()
                uuid_to_source_id[source_uuid] = source_id
                sources_imported += 1
                chunks_imported += _bulk_insert_chunks(source_id, s.get("chunks") or [])

            # 3. Extras (permissive — missing entries are silently skipped)
            extras_imported: dict[str, int | dict[str, int]] = {}

            def _try_load(name: str):
                try:
                    return json.loads(zf.read(f"{name}.json"))
                except KeyError:
                    return None
                except json.JSONDecodeError as e:
                    logger.warning("Workspace import {}: {}.json invalid JSON ({}), skipping",
                                   workspace_uuid, name, e)
                    return None

            glossary_rows = _try_load("glossary")
            if glossary_rows is not None:
                extras_imported["glossary"] = _insert_glossary(glossary_rows, uuid_to_source_id)
            summaries_rows = _try_load("summaries")
            if summaries_rows is not None:
                extras_imported["summaries"] = _insert_summaries(summaries_rows, uuid_to_source_id)
            notes_rows = _try_load("notes")
            if notes_rows is not None:
                extras_imported["notes"] = _insert_notes(workspace_id, admin_user_id, notes_rows)
            schedule_rows = _try_load("schedule")
            if schedule_rows is not None:
                extras_imported["schedule"] = _insert_schedule(workspace_id, admin_user_id, schedule_rows)
            studio_payload = _try_load("studio")
            if studio_payload is not None:
                extras_imported["studio"] = _insert_studio(
                    workspace_id, admin_user_id, studio_payload, uuid_to_source_id,
                )

        # 4. Embedding-fingerprint mismatch flag
        from src.routes.admin._embedding import active_embedding_provider_key
        active_key = f"fingerprint_{active_embedding_provider_key()}"
        active_fp = db.get_setting(active_key, "") or ""
        bundle_fp = workspace_data.get("embedding_fingerprint") or ""
        needs_reindex = bool(active_fp) and bool(bundle_fp) and active_fp != bundle_fp

        logger.info(
            "Workspace import {}: sources={}, chunks={}, transcripts={}, "
            "files_missing={}, extras={}, needs_reindex={}",
            workspace_uuid, sources_imported, chunks_imported, transcripts_restored,
            files_missing, extras_imported, needs_reindex,
        )

        return {
            "ok": True,
            "workspace_uuid": workspace_uuid,
            "sources_imported": sources_imported,
            "chunks_imported": chunks_imported,
            "transcripts_restored": transcripts_restored,
            "files_missing": files_missing,
            "needs_reindex": needs_reindex,
            "bundle_embedding_model": manifest.get("embedding_model"),
            "extras_imported": extras_imported,
        }

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ─── Reindex single workspace ───────────────────────────────────────────────

@router.post("/aia-workspaces/{workspace_uuid}/reindex")
async def reindex_workspace(
    workspace_uuid: str,
    _admin=Depends(get_admin_user),
):
    """Queue a Celery job that re-embeds every chunk of one workspace."""
    workspace = db.get_aia_workspace(workspace_uuid)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    progress_key = f"reindex_workspace_progress_{workspace_uuid}"
    progress_raw = db.get_setting(progress_key, "") or ""
    try:
        progress = json.loads(progress_raw) if progress_raw else None
    except json.JSONDecodeError:
        progress = None
    if progress and progress.get("running"):
        raise HTTPException(status_code=409, detail="reindex already running for this workspace")

    from src.tasks.aia_tasks import run_reindex_workspace

    db.set_setting(progress_key, json.dumps({
        "total": 0, "done": 0, "current": "queued", "failed": 0, "running": True,
    }))
    run_reindex_workspace.delay(workspace_uuid)
    return {"ok": True, "workspace_uuid": workspace_uuid}


@router.get("/aia-workspaces/{workspace_uuid}/reindex")
async def reindex_workspace_progress(
    workspace_uuid: str,
    _admin=Depends(get_admin_user),
):
    """Return the current reindex progress for a workspace (or None)."""
    progress_raw = db.get_setting(f"reindex_workspace_progress_{workspace_uuid}", "") or ""
    try:
        progress = json.loads(progress_raw) if progress_raw else None
    except json.JSONDecodeError:
        progress = None
    return {"workspace_uuid": workspace_uuid, "progress": progress}
