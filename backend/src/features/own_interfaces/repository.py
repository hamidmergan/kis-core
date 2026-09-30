"""The one-time agreement a person gives before connecting their own voice service."""

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection


def get_interfaces_consent(user_id: int) -> dict:
    """When and which version of the disclaimer this person accepted, both None when never."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT interfaces_consent_at, interfaces_consent_version FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"interfaces_consent_at": None, "interfaces_consent_version": None}
    return dict(row)


def set_interfaces_consent(user_id: int, version: int) -> None:
    """Notes the acceptance with the current time."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users
                   SET interfaces_consent_at = NOW(), interfaces_consent_version = %s
                   WHERE id = %s""",
                (version, user_id),
            )
        conn.commit()
