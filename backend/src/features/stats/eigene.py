"""A teacher's statistics, only their own modules."""
from psycopg2.extras import RealDictCursor

from src import database as db
from src.core.db.pool import get_connection


def may_see_workspace(uuid: str, user_id: int) -> bool:
    """Owner or tutor, the same two queries as for the management right."""
    workspace = db.get_aia_workspace(uuid)
    if not workspace:
        return False
    if workspace["user_id"] == user_id:
        return True
    return bool(db.is_workspace_tutor(workspace["id"], user_id))


def own_workspaces(user_id: int) -> dict:
    """Tiles and list for the 'my modules' tab."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT w.uuid, w.title, w.is_active,
                          CASE WHEN w.user_id = %s THEN 'owner' ELSE 'tutor' END AS access,
                          -- Der Eigentuemer steht in keiner Einschreibung. Ohne
                          -- das "+ 1" stuende in der Zeile 2 und im geoeffneten
                          -- Modul 3, und man suchte den Fehler bei sich.
                          (SELECT COUNT(DISTINCT e.user_id) FROM aia_enrollments e
                            WHERE e.workspace_id = w.id
                              AND e.user_id <> w.user_id) + 1 AS members,
                          (SELECT COUNT(*) FROM aia_sources s
                            WHERE s.workspace_id = w.id) AS sources,
                          (SELECT COUNT(*) FROM aia_messages m
                            WHERE m.workspace_id = w.id AND m.role = 'user') AS chat,
                          (SELECT COUNT(*) FROM aia_exercise_progress p
                             JOIN aia_exercise_sets s2 ON s2.id = p.set_id
                            WHERE s2.workspace_id = w.id) AS answered,
                          (SELECT MAX(m.created_at) FROM aia_messages m
                            WHERE m.workspace_id = w.id) AS last
                   FROM aia_workspaces w
                   WHERE w.user_id = %s
                      OR EXISTS (SELECT 1 FROM aia_enrollments e
                                  WHERE e.workspace_id = w.id AND e.user_id = %s
                                    AND e.role = 'tutor')
                   ORDER BY w.user_id = %s DESC, w.title ASC""",
                (user_id, user_id, user_id, user_id),
            )
            zeilen = cur.fetchall()

    module = [
        {
            "uuid": r["uuid"],
            "title": r["title"],
            "active": r["is_active"],
            "access": r["access"],
            "members": int(r["members"]),
            "sources": int(r["sources"]),
            "chat": int(r["chat"]),
            "answered": int(r["answered"]),
            "last": r["last"].isoformat() + "Z" if r["last"] else None,
        }
        for r in zeilen
    ]

    return {
        "totals": {
            "workspaces": len(module),
            "members": sum(m["members"] for m in module),
            "chat": sum(m["chat"] for m in module),
            "answered": sum(m["answered"] for m in module),
        },
        "workspaces": module,
    }
