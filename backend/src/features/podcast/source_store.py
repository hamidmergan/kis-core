"""The hidden per-person module the podcast files its uploads in, so a rerun can search them."""

import hashlib
import uuid as _uuid

from loguru import logger

from src import database as db
from src.limits import PODCAST_STORE_MAX_SOURCES

STORE_TITLE = "Podcast-Vorrat"

_HASH_BLOCK = 1024 * 1024


def _save_file(user_id: int, workspace_uuid: str, source_uuid: str, ext: str, path: str) -> str:
    from src.features.ai_assistant.routes._workspace_access import _save_source_file_path
    return _save_source_file_path(user_id, workspace_uuid, source_uuid, ext, path)


def _index(source_uuid: str, user_id: int, locale: str) -> None:
    from src.features.ai_assistant.routes.sources._shared import _enqueue_index_source
    _enqueue_index_source(source_uuid, user_id, locale)


def _remove_files(file_path: str) -> None:
    from src.storage import delete_aia_source_files
    delete_aia_source_files(file_path)


def content_hash(path: str) -> str:
    """Recognises the same file again even under a different name."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(_HASH_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def store_of(user_id: int) -> dict | None:
    """The person's hidden store as it is, this never creates one."""
    return db.get_podcast_store_workspace(user_id)


def store_for_user(user_id: int) -> dict:
    """The person's hidden store, created on first use."""
    return store_of(user_id) or db.create_podcast_store_workspace(user_id, STORE_TITLE)


def find_by_hash(workspace_id: int, digest: str) -> dict | None:
    """The file is already in the store, no second copy and no second indexing run."""
    return db.get_aia_source_by_content_hash(workspace_id, digest)


def make_room(workspace_id: int) -> int:
    """Drops the least recently used files until one more fits, returns how many went."""
    sources = db.get_aia_sources_by_last_used(workspace_id)
    gone = 0
    for source in sources:
        if len(sources) - gone < PODCAST_STORE_MAX_SOURCES:
            break
        try:
            _remove_files(source["file_path"])
        except Exception as e:  # noqa: BLE001 — a missing file must not keep the row alive
            logger.warning("Podcast-Vorrat: Dateien von {} nicht loeschbar: {}", source["uuid"], e)
        db.delete_aia_source(source["uuid"])
        gone += 1
    return gone


def touch(uuids: list[str]) -> None:
    """Keeps the files of this run out of the eviction queue."""
    db.touch_aia_sources_used(uuids)


def put(user_id: int, filename: str, path: str, ext: str, locale: str = "de") -> str:
    """Files one uploaded file and hands the indexing to the background, returns its uuid."""
    store = store_for_user(user_id)
    digest = content_hash(path)

    known = find_by_hash(store["id"], digest)
    if known:
        touch([known["uuid"]])
        return known["uuid"]

    make_room(store["id"])
    source_uuid = _uuid.uuid4().hex
    file_path = _save_file(user_id, store["uuid"], source_uuid, ext, path)
    db.create_aia_source(
        workspace_id=store["id"],
        uuid=source_uuid,
        filename=filename,
        file_path=file_path,
        file_type=ext.lstrip("."),
        content_hash=digest,
    )
    _index(source_uuid, user_id, locale)
    return source_uuid
