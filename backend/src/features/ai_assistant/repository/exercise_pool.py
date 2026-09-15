"""The exercise pool per source, tool and language level."""

import json

import psycopg2.extras

from src.core.db.pool import get_connection

# Ceiling per pool, it is never refilled with repeats.
POOL_MAX_ITEMS = 1000

# Tools with a pool, only these values appear in tool.
POOL_TOOLS = frozenset({"flashcards", "karteikarten", "quiz", "grammatik", "wortschatz"})

# Fields an exercise carries in the pool.
_ITEM_FIELDS = (
    "front", "back", "back_en", "options", "correct_idx", "explanation",
    "source_label", "page_number", "start_time", "sources", "extras",
)
_JSON_FIELDS = ("options", "sources", "extras")


def _as_row(item: dict, source_id: int, tool: str, level, topic_id, fingerprint: str,
            set_title) -> tuple:
    values = []
    for field in _ITEM_FIELDS:
        value = item.get(field)
        if field in _JSON_FIELDS:
            values.append(json.dumps(value) if value else None)
        else:
            values.append(value)
    # The kind sits on the item under _kind and still belongs in the pool.
    return (source_id, tool, level, topic_id, item.get("_kind"), fingerprint, set_title,
            *values)


def add_pool_items(
    source_id: int, tool: str, level, items: list[dict], fingerprints: list[str],
    topic_id=None, set_title: str | None = None,
) -> list[int]:
    """Stores exercises and returns the pool ids in the same order."""
    if not items:
        return []
    ids: list[int] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item, fingerprint in zip(items, fingerprints):
                if not fingerprint:
                    ids.append(None)
                    continue
                cur.execute(
                    f"""INSERT INTO aia_exercise_pool
                        (source_id, tool, level, topic_id, kind, fingerprint, set_title,
                         {", ".join(_ITEM_FIELDS)})
                        VALUES ({", ".join(["%s"] * (7 + len(_ITEM_FIELDS)))})
                        ON CONFLICT (source_id, tool, COALESCE(level, ''),
                                     COALESCE(topic_id, 0), fingerprint)
                        DO NOTHING
                        RETURNING id""",
                    _as_row(item, source_id, tool, level, topic_id, fingerprint, set_title),
                )
                row = cur.fetchone()
                if row is None:
                    # Already there, we take the existing row.
                    cur.execute(
                        """SELECT id FROM aia_exercise_pool
                           WHERE source_id = %s AND tool = %s
                             AND COALESCE(level, '') = COALESCE(%s, '')
                             AND COALESCE(topic_id, 0) = COALESCE(%s, 0)
                             AND fingerprint = %s""",
                        (source_id, tool, level, topic_id, fingerprint),
                    )
                    row = cur.fetchone()
                ids.append(row[0] if row else None)
        conn.commit()
    return ids


def pool_size(source_id: int, tool: str, level, topic_id=None) -> int:
    """How many exercises sit in this pool."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM aia_exercise_pool
                   WHERE source_id = %s AND tool = %s
                     AND COALESCE(level, '') = COALESCE(%s, '')
                     AND COALESCE(topic_id, 0) = COALESCE(%s, 0)""",
                (source_id, tool, level, topic_id),
            )
            return cur.fetchone()[0]


def take_from_pool(
    source_id: int, tool: str, level, user_id: int, limit: int, topic_id=None,
    exclude_ids=None, kinds=None, ignore_seen: bool = False,
) -> list[dict]:
    """Draws random exercises, skipping what this person already had, unless told not to."""
    if limit <= 0:
        return []
    # The seen-table is permanent, unlike the set it was first handed out in.
    gesehen = "" if ignore_seen else (
        " AND NOT EXISTS ("
        "SELECT 1 FROM aia_exercise_pool_seen sn "
        "WHERE sn.pool_item_id = p.id AND sn.user_id = %s)"
    )
    ausschluss = " AND p.id <> ALL(%s)" if exclude_ids else ""
    formate = " AND p.kind = ANY(%s)" if kinds else ""
    werte = [source_id, tool, level, topic_id]
    if not ignore_seen:
        werte.append(user_id)
    if exclude_ids:
        werte.append(list(exclude_ids))
    if kinds:
        werte.append(list(kinds))
    werte.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT p.* FROM aia_exercise_pool p
                   WHERE p.source_id = %s AND p.tool = %s
                     AND COALESCE(p.level, '') = COALESCE(%s, '')
                     AND COALESCE(p.topic_id, 0) = COALESCE(%s, 0)
                     {gesehen}{ausschluss}{formate}
                   ORDER BY random()
                   LIMIT %s""",
                tuple(werte),
            )
            return [dict(row) for row in cur.fetchall()]


def seen_fingerprints(user_id: int, tool: str, limit: int = 2000) -> list[str]:
    """Comparison forms of the exercises this person already had in this tool."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.front FROM aia_exercise_pool_seen sn
                   JOIN aia_exercise_pool p ON p.id = sn.pool_item_id
                   WHERE sn.user_id = %s AND p.tool = %s AND p.front <> ''
                   ORDER BY sn.seen_at DESC
                   LIMIT %s""",
                (user_id, tool, limit),
            )
            return [row[0] for row in cur.fetchall() if row[0]]


def _materialize(bedingung: str, wert) -> int:
    """The shared write-back statement, ``bedingung`` picks the pool."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE aia_exercise_items i
                   SET back = p.back, back_en = p.back_en, options = p.options,
                       correct_idx = p.correct_idx, explanation = p.explanation,
                       source_label = p.source_label, page_number = p.page_number,
                       start_time = p.start_time, sources = p.sources, extras = p.extras
                   FROM aia_exercise_pool p
                   WHERE i.pool_item_id = p.id AND {bedingung}""",
                (wert,),
            )
            zurueck = cur.rowcount
        conn.commit()
    return zurueck


def materialize_pool_items(source_id: int) -> int:
    """Writes pool content back into the sets that point at it."""
    return _materialize("p.source_id = %s", source_id)


def materialize_pool_items_for_topic(topic_id: int) -> int:
    """The same for the pool of a grammar topic."""
    return _materialize("p.topic_id = %s", topic_id)


def pool_counts_by_tool() -> dict[str, int]:
    """How many exercises sit in the pool per tool, across all course rooms."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tool, COUNT(*) FROM aia_exercise_pool GROUP BY tool")
            return {row[0]: row[1] for row in cur.fetchall()}


def clear_pool_for_tools(tools) -> int:
    """Throws away the pool of the named tools platform wide."""
    tools = list(tools)
    unbekannt = [t for t in tools if t not in POOL_TOOLS]
    if unbekannt:
        raise ValueError(f"kein Werkzeug mit Vorrat: {', '.join(unbekannt)}")
    if not tools:
        return 0
    _materialize("p.tool = ANY(%s)", tools)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_exercise_pool WHERE tool = ANY(%s)", (tools,))
            geloescht = cur.rowcount
        conn.commit()
    return geloescht


def clear_pool_for_source(source_id: int) -> int:
    """Throws away a source's pool and returns the number of deleted exercises."""
    materialize_pool_items(source_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_exercise_pool WHERE source_id = %s", (source_id,)
            )
            geloescht = cur.rowcount
        conn.commit()
    return geloescht


__all__ = [
    "POOL_MAX_ITEMS",
    "POOL_TOOLS",
    "add_pool_items",
    "clear_pool_for_source",
    "clear_pool_for_tools",
    "pool_counts_by_tool",
    "materialize_pool_items",
    "pool_size",
    "seen_fingerprints",
    "take_from_pool",
]
