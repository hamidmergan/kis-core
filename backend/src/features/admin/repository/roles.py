"""DB helpers for the role system: custom-role CRUD + user-role mutation.

Eine eigene Rolle ist ein Name und eine Liste von Rechte-Schluesseln aus
``src.permissions_registry``. Geschrieben wird immer ueber ``valid_keys``, damit
kein unbekannter Schluessel in der Datenbank landet und die Reihenfolge stabil
bleibt.
"""
import json
from typing import Any

import psycopg2
import psycopg2.extras

from src.core.db.pool import get_connection
from src.permissions_registry import valid_keys


class RoleNameTaken(Exception):
    """Den Rollennamen gibt es schon.

    Eigener Fehler statt der rohen Verletzung der Eindeutigkeit, damit die
    Route daraus eine Meldung machen kann, die der Mensch versteht.
    """


def role_name_taken(name: str, exclude_id: int | None = None) -> bool:
    """Ist der Name vergeben? Gross- und Kleinschreibung zaehlt nicht mit.

    Die Datenbank unterscheidet sie, ein Mensch nicht: zwei Spalten
    "Sprachexperte" und "sprachexperte" nebeneinander waeren nur verwirrend.
    ``exclude_id`` laesst die Rolle selbst aus, sonst koennte man sie nicht
    von "Tutor" auf "tutor" umbenennen.
    """
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
        # Zwei Anlagen gleichzeitig: die Vorabpruefung sah noch nichts, die
        # Eindeutigkeit in der Datenbank schon. Gleiche Meldung wie oben.
        raise RoleNameTaken(name)
    return new_id

def update_custom_role(role_id: int, name: str, permissions: list[str]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE custom_roles SET name = %s, permissions = %s::jsonb, "
                "updated_at = NOW() WHERE id = %s",
                (name, json.dumps(list(valid_keys(permissions))), role_id),
            )
        conn.commit()

def rename_custom_role(role_id: int, name: str) -> None:
    """Nur den Namen aendern, ohne die Rechte anzufassen.

    Die Rechtetabelle speichert je Haekchen. Wer den Namen in der Spaltenkopf-
    zeile aendert, soll dabei nicht versehentlich eine Rechteliste ueberschreiben,
    die inzwischen woanders veraendert wurde.
    """
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
    """Ein einzelnes Haekchen setzen oder loeschen, und die neue Liste liefern.

    Die Rechtetabelle hat keinen Speicherknopf, jeder Klick landet hier. Gelesen
    und geschrieben wird in einer Transaktion mit ``FOR UPDATE``, damit zwei
    gleichzeitige Klicks sich nicht gegenseitig ueberschreiben.
    """
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
