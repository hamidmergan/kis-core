"""Database access for custom roles and a user's role."""
import json
from typing import Any

import psycopg2
import psycopg2.extras

from src.core.db.pool import get_connection
from src.permissions_registry import valid_keys


class RoleNameTaken(Exception):
    """The role name already exists."""


def role_name_taken(name: str, exclude_id: int | None = None) -> bool:
    """Is the name taken, ignoring case?"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM custom_roles "
                "WHERE lower(name) = lower(%s) AND (%s::int IS NULL OR id <> %s) "
                "LIMIT 1",
                (name.strip(), exclude_id, exclude_id),
            )
            return cur.fetchone() is not None


def list_custom_roles() -> list[dict[str, Any]]:
    """All custom roles, ordered by name."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, permissions, created_at, updated_at "
                "FROM custom_roles ORDER BY name"
            )
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "permissions": list(valid_keys(r["permissions"] or [])),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]

def get_custom_role(role_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, permissions FROM custom_roles WHERE id = %s",
                (role_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "permissions": list(valid_keys(row["permissions"] or [])),
    }

def create_custom_role(name: str, permissions: list[str]) -> int:
    if role_name_taken(name):
        raise RoleNameTaken(name)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO custom_roles (name, permissions) "
                    "VALUES (%s, %s::jsonb) RETURNING id",
                    (name, json.dumps(list(valid_keys(permissions)))),
                )
                new_id = cur.fetchone()[0]
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        # Two creations at once, the database saw the duplicate first.
        raise RoleNameTaken(name)
    return new_id

def rename_custom_role(role_id: int, name: str) -> None:
    """Change only the name, without touching the permissions."""
    if role_name_taken(name, exclude_id=role_id):
        raise RoleNameTaken(name)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE custom_roles SET name = %s, updated_at = NOW() WHERE id = %s",
                    (name, role_id),
                )
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        raise RoleNameTaken(name)

def set_custom_role_permission(role_id: int, key: str, granted: bool) -> list[str]:
    """Set or clear a single checkbox and return the new list."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT permissions FROM custom_roles WHERE id = %s FOR UPDATE",
                (role_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise LookupError(f"Unknown custom role: {role_id}")
            current = set(row[0] or [])
            if granted:
                current.add(key)
            else:
                current.discard(key)
            new_keys = list(valid_keys(current))
            cur.execute(
                "UPDATE custom_roles SET permissions = %s::jsonb, updated_at = NOW() "
                "WHERE id = %s",
                (json.dumps(new_keys), role_id),
            )
        conn.commit()
    return new_keys

def delete_custom_role(role_id: int) -> None:
    """Deletes a custom role and resets its users to 'user'."""
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
    """Sets a user's role, custom_role_id only for 'custom'."""
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
