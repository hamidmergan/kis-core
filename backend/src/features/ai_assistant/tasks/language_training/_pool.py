"""Takes exercises out of the pool and stores newly generated ones."""

import hashlib

from loguru import logger

from src import database as db
# The list sits at the pool because clearing it in the admin area needs it too.
from src.features.ai_assistant.repository.exercise_pool import POOL_TOOLS
from src.features.ai_assistant.tasks.language_training._dedup import item_key

# Tools with a pool, the cloze only when generated from the sources.

# Fields a pool row brings along and an exercise in a set needs.
_CARRIED = (
    "front", "back", "back_en", "options", "correct_idx", "explanation",
    "source_label", "page_number", "start_time", "sources", "extras",
)


def uses_pool(tool: str, mode: str) -> bool:
    """Whether this request goes through the pool, source mode only."""
    return mode == "source" and tool in POOL_TOOLS


def pool_level(adaptive_suffix: str, user_id: int | None) -> str | None:
    """The level items are stored and taken under, derived from the suffix."""
    if not adaptive_suffix or not user_id:
        return None
    try:
        return db.get_user_language_level(user_id)["language_level"] or None
    except Exception:  # noqa: BLE001 - without a level the level-free pool is right
        return None


# Beyond this length a hash takes the place of the raw text, otherwise the index bursts.
_FINGERPRINT_HASH_THRESHOLD = 1000


def _fingerprint(front: str) -> str:
    """Comparison value for the unique pool index, safe in length."""
    schluessel = item_key(front)
    if len(schluessel.encode("utf-8")) <= _FINGERPRINT_HASH_THRESHOLD:
        return schluessel
    return hashlib.sha256(schluessel.encode("utf-8")).hexdigest()


def _as_item(row: dict) -> dict:
    """Puts a pool row into the shape the set stores."""
    item = {feld: row.get(feld) for feld in _CARRIED}
    item["pool_item_id"] = row["id"]
    # Travels alongside for the set name, finalize_exercise_set ignores it.
    item["set_title"] = row.get("set_title")
    return item


def title_from_items(items: list[dict]) -> str:
    """The set name a purely pooled set inherits, the most common one wins."""
    from collections import Counter
    namen = [
        " ".join((i.get("set_title") or "").split())
        for i in items
        if (i.get("set_title") or "").strip()
    ]
    if not namen:
        return ""
    return Counter(namen).most_common(1)[0][0]


def take(uuids: list[str], tool: str, level, user_id: int, count: int,
         topic_id=None, kinds=None, exclude_ids=None, ignore_seen: bool = False) -> list[dict]:
    """Takes up to count exercises, exclude_ids and ignore_seen serve the repeat fallback."""
    if not uuids or count <= 0 or not user_id:
        return []
    try:
        return _take(uuids, tool, level, user_id, count, topic_id, kinds,
                     exclude_ids, ignore_seen)
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Vorrat nicht lesbar, es wird erzeugt: {}", e)
        return []


def _take(uuids: list[str], tool: str, level, user_id: int, count: int,
          topic_id=None, kinds=None, exclude_ids=None, ignore_seen: bool = False) -> list[dict]:
    quellen = [db.get_aia_source(u) for u in uuids]
    source_ids = [q["id"] for q in quellen if q and q.get("id")]
    if not ignore_seen:
        # A pool still warming up hands out nothing, the repeat fallback may still draw.
        warm = db.warm_pool_sources(source_ids, tool, level, topic_id)
        source_ids = [s for s in source_ids if s in warm]
    if not source_ids:
        return []
    offen = count
    genommen: list[dict] = []
    # Marker for what this order already has, the query knows nothing of it.
    geholt: list = list(exclude_ids or [])  # pool ids, passed to the query as exclusions
    texte: set[str] = set()  # their comparison forms, against duplicates across sources
    leer: set = set()        # sources that delivered less than ordered
    # Two rounds: first an equal share per source, then the rest.
    for runde in (1, 2):
        for i, source_id in enumerate(source_ids):
            if offen <= 0:
                break
            if source_id in leer:
                continue
            if runde == 1:
                uebrig = len(source_ids) - i
                will = min(offen, -(-offen // uebrig))  # aufgerundeter gleicher Anteil
            else:
                will = offen
            rows = db.take_from_pool(source_id, tool, level, user_id, will, topic_id,
                                     exclude_ids=geholt or None, kinds=kinds,
                                     ignore_seen=ignore_seen)
            if len(rows) < will:
                # Fewer than ordered means this pool has no more.
                leer.add(source_id)
            for row in rows:
                geholt.append(row["id"])
                # Two sources can hold the same exercise, the index sits per source.
                schluessel = item_key(row.get("front") or "")
                if schluessel:
                    if schluessel in texte:
                        continue
                    texte.add(schluessel)
                genommen.append(_as_item(row))
                offen -= 1
        if offen <= 0:
            break
    return genommen[:count]


def store(items: list[dict], ctx, tool: str, level, topic_id=None,
          set_title: str | None = None) -> None:
    """Stores freshly generated items and records the pool id on them."""
    if not items:
        return
    nach_quelle: dict[int, list[dict]] = {}
    for item in items:
        if item.get("pool_item_id"):
            continue  # already came from the pool
        quelle = (ctx.source_by_name or {}).get(item.get("source_label") or "")
        if not quelle or not quelle.get("id"):
            continue
        nach_quelle.setdefault(quelle["id"], []).append(item)

    for source_id, gruppe in nach_quelle.items():
        try:
            # Counted before the size check, a full pool must still reach the warm-up mark.
            db.count_pool_run(source_id, tool, level, topic_id)
            platz = db.POOL_MAX_ITEMS - db.pool_size(source_id, tool, level, topic_id)
            if platz <= 0:
                continue
            gruppe = gruppe[:platz]
            ids = db.add_pool_items(
                source_id, tool, level, gruppe,
                [_fingerprint(i.get("front", "")) for i in gruppe],
                topic_id, set_title,
            )
            for item, pool_id in zip(gruppe, ids):
                if pool_id:
                    item["pool_item_id"] = pool_id
        except Exception as e:  # noqa: BLE001
            # Storing is an improvement, the set is saved either way.
            logger.warning("KI Tutor: Vorrat der Quelle {} nicht gefuellt: {}", source_id, e)


__all__ = ["POOL_TOOLS", "pool_level", "store", "take", "title_from_items", "uses_pool"]
