"""CRUD for the providers table.

A provider is an endpoint the admin registered (name + protocol + base_url +
api_key). Capabilities are filled in by the probe service or by protocol
definition. Feature routing happens in a separate table (``feature_routes``).
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2.extras

from src.core.db.pool import get_connection

_SELECT = """SELECT id, name, protocol, base_url, api_key, capabilities,
                    voices, enabled, last_probed_at, probe_status, probe_error,
                    created_at, updated_at"""


def _row_to_dict(row) -> dict:
    """Coerce a DictRow (mixed types from psycopg2) into a JSON-friendly dict."""
    d = dict(row)
    for jsonb_col in ("capabilities", "voices"):
        v = d.get(jsonb_col)
        if isinstance(v, str):
            d[jsonb_col] = json.loads(v)
        elif v is None:
            d[jsonb_col] = []
    for ts in ("last_probed_at", "created_at", "updated_at"):
        v = d.get(ts)
        if isinstance(v, datetime):
            d[ts] = v.isoformat()
    return d


def list_providers() -> list[dict]:
    """All providers, newest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""{_SELECT}
                   FROM providers
                   ORDER BY created_at ASC"""
            )
            return [_row_to_dict(r) for r in cur.fetchall()]


def get_provider(provider_id: int) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""{_SELECT}
                   FROM providers WHERE id = %s""",
                (provider_id,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def get_provider_by_name(name: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""{_SELECT}
                   FROM providers WHERE name = %s""",
                (name,),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def create_provider(
    *,
    name: str,
    protocol: str,
    base_url: str,
    api_key: Optional[str] = None,
    capabilities: Optional[list[str]] = None,
    voices: Optional[list[dict]] = None,
    enabled: bool = True,
) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""INSERT INTO providers
                       (name, protocol, base_url, api_key, capabilities, voices, enabled)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                   RETURNING {_SELECT.split('SELECT ')[1]}""",
                (
                    name,
                    protocol,
                    base_url,
                    api_key,
                    json.dumps(capabilities or []),
                    json.dumps(voices or []),
                    enabled,
                ),
            )
            conn.commit()
            return _row_to_dict(cur.fetchone())


def update_provider(provider_id: int, **fields: Any) -> Optional[dict]:
    """Patch any of name / protocol / base_url / api_key / capabilities / voices / enabled."""
    allowed = {"name", "protocol", "base_url", "api_key", "capabilities", "voices", "enabled"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_provider(provider_id)

    sets: list[str] = []
    values: list[Any] = []
    for key, value in updates.items():
        if key in ("capabilities", "voices"):
            sets.append(f"{key} = %s::jsonb")
            values.append(json.dumps(value or []))
        else:
            sets.append(f"{key} = %s")
            values.append(value)
    sets.append("updated_at = NOW()")
    values.append(provider_id)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""UPDATE providers SET {", ".join(sets)} WHERE id = %s
                    RETURNING {_SELECT.split('SELECT ')[1]}""",
                values,
            )
            row = cur.fetchone()
            conn.commit()
            return _row_to_dict(row) if row else None


def set_probe_result(
    provider_id: int,
    *,
    capabilities: list[str],
    status: str,
    error: Optional[str] = None,
) -> None:
    """Record the result of an auto-probe run on a provider."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE providers
                   SET capabilities = %s::jsonb,
                       last_probed_at = NOW(),
                       probe_status = %s,
                       probe_error = %s,
                       updated_at = NOW()
                   WHERE id = %s""",
                (json.dumps(capabilities), status, error, provider_id),
            )
            conn.commit()


def delete_provider(provider_id: int) -> bool:
    """Delete a provider. ON DELETE SET NULL on feature_routes.provider_id
    will leave the routes in an "unconfigured" state."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM providers WHERE id = %s", (provider_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted


def list_providers_with_capability(capability: str) -> list[dict]:
    """Providers whose capabilities array contains the given capability and which are enabled."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""{_SELECT}
                   FROM providers
                   WHERE enabled = TRUE
                     AND capabilities ? %s
                   ORDER BY created_at ASC""",
                (capability,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
