"""Grammar exercise topics per course room, name and elaboration kept apart."""

import json

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository.exercise_pool import (
    materialize_pool_items_for_topic,
)


# Seed so nobody faces an empty list.
SEED_TOPICS = [
    {"name": "Passiv Präsens"},
    {"name": "Passiv mit Modalverb"},
    {"name": "Perfekt"},
    {"name": "Präteritum"},
    {"name": "Konjunktiv II"},
    {"name": "Relativsätze"},
    {"name": "Nebensätze"},
    {"name": "Adjektivdeklination"},
]

# Exactly one pair, the generator never read a second one.
MAX_EXAMPLES = 1

_EMPTY_PAIR = {"before": "", "after": ""}


def catalog_entry(topic: dict, spec: dict) -> dict:
    """Topic plus elaboration in the shape the generators expect."""
    examples = list(spec.get("examples") or [])
    return {
        "id": topic["id"],
        "label": topic["name"],
        "rule": spec.get("rule") or "",
        "example": examples[0] if examples else dict(_EMPTY_PAIR),
        "examples": examples,
    }


def list_grammar_topics(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, created_by FROM aia_grammar_topics "
                "WHERE workspace_id = %s ORDER BY name",
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_grammar_topic(topic_id) -> dict | None:
    if not topic_id:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, workspace_id, name, created_by FROM aia_grammar_topics "
                "WHERE id = %s",
                (topic_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_grammar_topic(workspace_id: int, name: str, created_by: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO aia_grammar_topics (workspace_id, name, created_by) "
                "VALUES (%s, %s, %s) RETURNING id, name, created_by",
                (workspace_id, name.strip(), created_by),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def delete_grammar_topic(topic_id: int) -> None:
    """Removes a topic with elaboration and pool, finished sets stay."""
    materialize_pool_items_for_topic(topic_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_grammar_topics WHERE id = %s", (topic_id,))
        conn.commit()


def get_topic_spec(topic_id: int, language: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT rule, examples FROM aia_grammar_topic_specs "
                "WHERE topic_id = %s AND language = %s",
                (topic_id, language),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def save_topic_spec(topic_id: int, language: str, rule: str, examples: list) -> dict:
    """Creates or replaces the elaboration, surplus pairs are dropped."""
    trimmed = list(examples)[:MAX_EXAMPLES]
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO aia_grammar_topic_specs "
                "(topic_id, language, rule, examples) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (topic_id, language) DO UPDATE "
                "SET rule = EXCLUDED.rule, examples = EXCLUDED.examples "
                "RETURNING rule, examples",
                (topic_id, language, rule, json.dumps(trimmed)),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def seed_grammar_topics(workspace_id: int, created_by: int) -> None:
    """Copies the seed into a fresh course room, without elaboration."""
    for entry in SEED_TOPICS:
        create_grammar_topic(workspace_id, entry["name"], created_by)
