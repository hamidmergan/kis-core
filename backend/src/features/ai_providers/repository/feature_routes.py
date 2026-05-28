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
    "transcript_translate",
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
    for jsonb_col in ("user_choices", "provider_models"):
        v = d.get(jsonb_col)
        if isinstance(v, str):
            d[jsonb_col] = json.loads(v)
        elif v is None:
            d[jsonb_col] = [] if jsonb_col == "user_choices" else {}
    v = d.get("updated_at")
    if isinstance(v, datetime):
        d["updated_at"] = v.isoformat()
    return d


_SELECT = "id, feature, provider_id, model_name, user_choices, provider_models, updated_at"


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
) -> dict:
    """Upsert the row for one feature. Pass None to clear a field."""
    payload_choices = json.dumps(user_choices or [])
    payload_models = json.dumps(provider_models or {})
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""INSERT INTO feature_routes
                       (feature, provider_id, model_name, user_choices, provider_models)
                   VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                   ON CONFLICT (feature) DO UPDATE
                       SET provider_id = EXCLUDED.provider_id,
                           model_name = EXCLUDED.model_name,
                           user_choices = EXCLUDED.user_choices,
                           provider_models = EXCLUDED.provider_models,
                           updated_at = NOW()
                   RETURNING {_SELECT}""",
                (feature, provider_id, model_name, payload_choices, payload_models),
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
                f"""SELECT {_SELECT}
                   FROM feature_routes
                   WHERE provider_id = %s
                      OR user_choices @> %s::jsonb""",
                (provider_id, json.dumps([provider_id])),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def clear_provider_from_routes(provider_id: int) -> int:
    """Remove provider_id refs after a provider is deleted.

    Sets provider_id to NULL where it matches, filters the deleted id out of
    every user_choices array, and removes its entry from provider_models.
    Returns the number of rows touched.
    """
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
