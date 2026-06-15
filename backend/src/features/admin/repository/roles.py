"""DB helpers for the role system: custom-role CRUD + user-role mutation."""
import json
from typing import Any

import psycopg2.extras

from src.core.db.pool import get_connection


def list_custom_roles() -> list[dict[str, Any]]:
    """All custom roles, ordered by name."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, aia_access, allowed_tools, created_at, updated_at "
                "FROM custom_roles ORDER BY name"
            )
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "aia_access": r["aia_access"],
            "allowed_tools": r["allowed_tools"] or [],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]

def get_custom_role(role_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, aia_access, allowed_tools "
                "FROM custom_roles WHERE id = %s",
                (role_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "aia_access": row["aia_access"],
        "allowed_tools": row["allowed_tools"] or [],
    }

def create_custom_role(name: str, aia_access: str, allowed_tools: list[str]) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_roles (name, aia_access, allowed_tools) "
                "VALUES (%s, %s, %s::jsonb) RETURNING id",
                (name, aia_access, json.dumps(allowed_tools)),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id

def update_custom_role(
    role_id: int, name: str, aia_access: str, allowed_tools: list[str],
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE custom_roles SET name = %s, aia_access = %s, "
                "allowed_tools = %s::jsonb, updated_at = NOW() WHERE id = %s",
                (name, aia_access, json.dumps(allowed_tools), role_id),
            )
        conn.commit()

def delete_custom_role(role_id: int) -> None:
    """Delete a custom role.

    Users assigned to this role are reset to 'user' (the FK is ON DELETE SET NULL,
    so custom_role_id becomes NULL automatically; we additionally reset role to 'user'
    here so the user does not end up with role='custom' and custom_role_id=NULL,
    which would degrade gracefully but is a confusing intermediate state).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET role = 'user', custom_role_id = NULL "
                "WHERE custom_role_id = %s",
                (role_id,),
            )
            cur.execute("DELETE FROM custom_roles WHERE id = %s", (role_id,))
        conn.commit()

def set_user_role(user_id: int, role: str, custom_role_id: int | None) -> None:
    """Set a user's role.

    - role must be one of 'admin', 'staff', 'user', 'custom'
    - if role == 'custom', custom_role_id must point to an existing custom role
    - otherwise custom_role_id is forced to None
    """
    if role not in ("admin", "staff", "user", "custom"):
        raise ValueError(f"Invalid role: {role!r}")
    if role == "custom":
        if custom_role_id is None or get_custom_role(custom_role_id) is None:
            raise ValueError("custom role requires existing custom_role_id")
    else:
        custom_role_id = None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET role = %s, custom_role_id = %s WHERE id = %s",
                (role, custom_role_id, user_id),
            )
        conn.commit()

def get_user_role(user_id: int) -> tuple[str, int | None]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT role, custom_role_id FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    if row is None:
        raise ValueError(f"User {user_id} not found")
    return row[0], row[1]
