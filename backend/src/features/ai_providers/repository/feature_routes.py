"""CRUD for the feature_routes table.

One row per feature maps the feature to its chosen provider (+ optional model).
``user_choices`` is the multi-pill list of provider IDs the end-user may pick
between in the tool UI (used for tts / doc_translate / screencast_translate).
"""

import json
from datetime import datetime
from typing import Optional

import psycopg2.extras

from src.core.db.pool import get_connection


# Canonical feature identifiers. Kept here so the API layer can validate input
# without importing from the protocol package.
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
    "screencast_translate",
)

# Features that support user-choice multi-pill selection (admin enables a set
# of providers, end-user picks one inside the tool).
USER_CHOICE_FEATURES: frozenset[str] = frozenset({
    "tts",
    "doc_translate",
    "screencast_translate",
})


def _row_to_dict(row) -> dict:
    d = dict(row)
    uc = d.get("user_choices")
    if isinstance(uc, str):
        d["user_choices"] = json.loads(uc)
    v = d.get("updated_at")
    if isinstance(v, datetime):
        d["updated_at"] = v.isoformat()
    return d


def list_routes() -> list[dict]:
    """All configured routes (one row per feature that was ever set)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, feature, provider_id, model_name, user_choices, updated_at
                   FROM feature_routes ORDER BY feature"""
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_route(feature: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, feature, provider_id, model_name, user_choices, updated_at
                   FROM feature_routes WHERE feature = %s""",
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
) -> dict:
    """Upsert the row for one feature. Pass None to clear a field."""
    payload_choices = json.dumps(user_choices or [])
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """INSERT INTO feature_routes
                       (feature, provider_id, model_name, user_choices)
                   VALUES (%s, %s, %s, %s::jsonb)
                   ON CONFLICT (feature) DO UPDATE
                       SET provider_id = EXCLUDED.provider_id,
                           model_name = EXCLUDED.model_name,
                           user_choices = EXCLUDED.user_choices,
                           updated_at = NOW()
                   RETURNING id, feature, provider_id, model_name, user_choices, updated_at""",
                (feature, provider_id, model_name, payload_choices),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def routes_using_provider(provider_id: int) -> list[dict]:
    """Routes whose provider_id matches OR which list the provider in user_choices.

    Used for the delete-confirmation cascade so the admin sees what they're
    about to break.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, feature, provider_id, model_name, user_choices, updated_at
                   FROM feature_routes
                   WHERE provider_id = %s
                      OR user_choices @> %s::jsonb""",
                (provider_id, json.dumps([provider_id])),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def clear_provider_from_routes(provider_id: int) -> int:
    """Remove provider_id refs after a provider is deleted.

    Sets provider_id to NULL where it matches, and filters the deleted id out
    of every user_choices array. Returns the number of rows touched.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE feature_routes
                   SET provider_id = NULL, model_name = NULL, updated_at = NOW()
                   WHERE provider_id = %s""",
                (provider_id,),
            )
            cleared = cur.rowcount
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
            conn.commit()
            return cleared
