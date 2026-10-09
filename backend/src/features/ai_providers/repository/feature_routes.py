"""Database access to feature_routes, one row per feature."""

import json
from datetime import datetime
from typing import Optional

import psycopg2.extras

from src.core.db.pool import get_connection


# The fixed feature ids, here so the API can validate them.
FEATURES: tuple[str, ...] = (
    "chat",
    "embedding",
    "vision",
    "ocr",
    "stt",
    "tts",
    "image_gen",
    "image_edit",
    "doc_translate",
    "transcript_translate",
)

# Features where the user may pick from several providers.
USER_CHOICE_FEATURES: frozenset[str] = frozenset({
    "tts",
    "vision",
    "image_gen",
    "image_edit",
    "doc_translate",
})

# Features that may name a second provider for when the first one fails, tts switches per job only.
FALLBACK_FEATURES: tuple[str, ...] = FEATURES

# The capability a provider needs to stand in for a feature, translating goes through chat.
FALLBACK_CAPABILITY: dict[str, str] = {
    "chat": "chat",
    "doc_translate": "chat",
    "transcript_translate": "chat",
    "embedding": "embedding",
    "vision": "vision",
    "ocr": "ocr",
    "stt": "stt",
    "image_gen": "image_gen",
    "image_edit": "image_edit",
    "tts": "tts",
}


def _row_to_dict(row) -> dict:
    d = dict(row)
    for jsonb_col in ("user_choices", "provider_models", "provider_sampling", "provider_order"):
        v = d.get(jsonb_col)
        if isinstance(v, str):
            d[jsonb_col] = json.loads(v)
        elif v is None:
            d[jsonb_col] = [] if jsonb_col in ("user_choices", "provider_order") else {}
    v = d.get("updated_at")
    if isinstance(v, datetime):
        d["updated_at"] = v.isoformat()
    return d


_SELECT = ("id, feature, provider_id, model_name, user_choices, provider_models, "
           "provider_sampling, fallback_provider_id, provider_order, updated_at")


def ordered_ids(route: Optional[dict], ids: list[int]) -> list[int]:
    """These provider ids in the admin's order, ids without a place follow in their own order.

    A route saved before the order existed puts its first choice and fallback in front.
    """
    route = route or {}
    gespeichert = list(route.get("provider_order") or []) or [
        route.get("provider_id"), route.get("fallback_provider_id")]
    vorne = [i for i in dict.fromkeys(gespeichert) if i in ids]
    return vorne + [i for i in ids if i not in vorne]


def list_routes() -> list[dict]:
    """All configured routes (one row per feature that was ever set)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT {_SELECT} FROM feature_routes ORDER BY feature"
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_route(feature: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT {_SELECT} FROM feature_routes WHERE feature = %s",
                (feature,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def set_route(
    feature: str,
    *,
    provider_id: Optional[int] = None,
    model_name: Optional[str] = None,
    user_choices: Optional[list[int]] = None,
    provider_models: Optional[dict] = None,
    provider_sampling: Optional[dict] = None,
    fallback_provider_id: Optional[int] = None,
    provider_order: Optional[list[int]] = None,
) -> dict:
    """Upsert the row for one feature. Pass None to clear a field."""
    payload_order = json.dumps(provider_order or [])
    payload_choices = json.dumps(user_choices or [])
    payload_models = json.dumps(provider_models or {})
    payload_sampling = json.dumps(provider_sampling or {})
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""INSERT INTO feature_routes
                       (feature, provider_id, model_name, user_choices, provider_models,
                        provider_sampling, fallback_provider_id, provider_order)
                   VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb)
                   ON CONFLICT (feature) DO UPDATE
                       SET provider_id = EXCLUDED.provider_id,
                           model_name = EXCLUDED.model_name,
                           user_choices = EXCLUDED.user_choices,
                           provider_models = EXCLUDED.provider_models,
                           provider_sampling = EXCLUDED.provider_sampling,
                           fallback_provider_id = EXCLUDED.fallback_provider_id,
                           provider_order = EXCLUDED.provider_order,
                           updated_at = NOW()
                   RETURNING {_SELECT}""",
                (feature, provider_id, model_name, payload_choices, payload_models,
                 payload_sampling, fallback_provider_id, payload_order),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def routes_using_provider(provider_id: int) -> list[dict]:
    """Routes that use this provider, offer it as a choice or fall back to it."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT {_SELECT}
                   FROM feature_routes
                   WHERE provider_id = %s
                      OR fallback_provider_id = %s
                      OR user_choices @> %s::jsonb
                      OR provider_order @> %s::jsonb""",
                (provider_id, provider_id, json.dumps([provider_id]), json.dumps([provider_id])),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def clear_provider_from_routes(provider_id: int) -> int:
    """Removes every reference to a deleted provider."""
    key = str(provider_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE feature_routes
                   SET provider_id = NULL, model_name = NULL, updated_at = NOW()
                   WHERE provider_id = %s""",
                (provider_id,),
            )
            cleared = cur.rowcount
            # A route that fell back to the deleted provider now has no fallback.
            cur.execute(
                """UPDATE feature_routes
                   SET fallback_provider_id = NULL, updated_at = NOW()
                   WHERE fallback_provider_id = %s""",
                (provider_id,),
            )
            cleared += cur.rowcount
            # Strip the deleted id from each user_choices array.
            cur.execute(
                """UPDATE feature_routes
                   SET user_choices = (
                       SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                       FROM jsonb_array_elements(user_choices) elem
                       WHERE (elem)::int <> %s
                   ),
                   updated_at = NOW()
                   WHERE user_choices @> %s::jsonb""",
                (provider_id, json.dumps([provider_id])),
            )
            cleared += cur.rowcount
            # The order closes up behind the deleted provider.
            cur.execute(
                """UPDATE feature_routes
                   SET provider_order = (
                       SELECT COALESCE(jsonb_agg(elem), '[]'::jsonb)
                       FROM jsonb_array_elements(provider_order) elem
                       WHERE (elem)::int <> %s
                   ),
                   updated_at = NOW()
                   WHERE provider_order @> %s::jsonb""",
                (provider_id, json.dumps([provider_id])),
            )
            # Remove the deleted provider's model entry from provider_models.
            cur.execute(
                """UPDATE feature_routes
                   SET provider_models = provider_models - %s,
                       updated_at = NOW()
                   WHERE provider_models ? %s""",
                (key, key),
            )
            conn.commit()
            return cleared


def delete_all_routes() -> int:
    """Delete every row from the feature_routes table. Returns count deleted."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM feature_routes")
            deleted = cur.rowcount
            conn.commit()
            return deleted
