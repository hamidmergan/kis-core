"""Thin SQL for the per-user learner profile. All weighting lives in
src.services.aia_learner_profile, this module only reads and writes rows.

The table self-aggregates: one upsert per event, decay applied on read and on the
next write, and a hard cap enforced after every write so it never grows unbounded.
"""

from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.admin.repository.settings import get_setting
from src.services import aia_learner_profile as lp

LEARNER_WINDOW_SETTING = "learner_profile_window_days"
DEFAULT_WINDOW_DAYS = lp.DEFAULT_WINDOW_DAYS


def _window_days() -> int:
    """Admin-configured decay window in days, default 30, never below 1."""
    try:
        return max(1, int(get_setting(LEARNER_WINDOW_SETTING, str(lp.DEFAULT_WINDOW_DAYS))))
    except (TypeError, ValueError):
        return lp.DEFAULT_WINDOW_DAYS


def is_learning_profile_enabled(user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT learning_profile_enabled FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return bool(row[0]) if row else False


def set_learning_profile_enabled(user_id: int, enabled: bool) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET learning_profile_enabled = %s WHERE id = %s",
                (enabled, user_id),
            )
        conn.commit()


def record_weakness(user_id: int, workspace_id: int, category: str, kind: str,
                    label: str, source_id: int | None = None) -> None:
    """Upsert one weakness event, scoped to a workspace. Skips silently when tracking
    is off or the label is empty. Applies decay to the prior weight, adds this kind's
    base weight, then enforces the per-workspace cap."""
    label = (label or "").strip()
    if not label or not is_learning_profile_enabled(user_id):
        return
    key = lp.normalize_key(label)
    now = datetime.now(timezone.utc)
    window = _window_days()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT weight, last_seen_at FROM aia_learner_weakness "
                "WHERE user_id = %s AND workspace_id = %s AND category = %s AND key_norm = %s",
                (user_id, workspace_id, category, key),
            )
            row = cur.fetchone()
            prev_eff = lp.effective_weight(row["weight"], row["last_seen_at"], now, window) if row else 0.0
            new_weight = lp.accumulate(prev_eff, kind)
            cur.execute(
                """
                INSERT INTO aia_learner_weakness
                    (user_id, workspace_id, category, key_norm, label, source_id, weight,
                     hit_count, first_seen_at, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (user_id, workspace_id, category, key_norm) DO UPDATE SET
                    label = EXCLUDED.label,
                    source_id = COALESCE(EXCLUDED.source_id, aia_learner_weakness.source_id),
                    weight = %s,
                    hit_count = aia_learner_weakness.hit_count + 1,
                    last_seen_at = %s
                """,
                (user_id, workspace_id, category, key, label, source_id, new_weight,
                 now, now, new_weight, now),
            )
            # Enforce the cap per workspace: evict the weakest rows if over PROFILE_CAP.
            cur.execute(
                "SELECT id, weight, last_seen_at FROM aia_learner_weakness "
                "WHERE user_id = %s AND workspace_id = %s",
                (user_id, workspace_id),
            )
            rows = [dict(r) for r in cur.fetchall()]
            drop = lp.overflow_ids(rows, now, window)
            if drop:
                cur.execute("DELETE FROM aia_learner_weakness WHERE id = ANY(%s)", (drop,))
        conn.commit()


def graduate_learner_term(user_id: int, workspace_id: int, label: str) -> None:
    """A later correct answer shrinks the matching term's weight in this workspace.
    Below the master floor the row is dropped as mastered. No-op if not tracked."""
    key = lp.normalize_key(label)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, weight FROM aia_learner_weakness "
                "WHERE user_id = %s AND workspace_id = %s AND category = %s AND key_norm = %s",
                (user_id, workspace_id, lp.CATEGORY_TERM, key),
            )
            row = cur.fetchone()
            if not row:
                return
            new_weight = lp.graduate(row["weight"])
            if new_weight < lp.MASTER_FLOOR:
                cur.execute("DELETE FROM aia_learner_weakness WHERE id = %s", (row["id"],))
            else:
                cur.execute(
                    "UPDATE aia_learner_weakness SET weight = %s WHERE id = %s",
                    (new_weight, row["id"]),
                )
        conn.commit()


def _load_rows(user_id: int, workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, label, source_id, weight, hit_count, last_seen_at "
                "FROM aia_learner_weakness WHERE user_id = %s AND workspace_id = %s",
                (user_id, workspace_id),
            )
            return [dict(r) for r in cur.fetchall()]


def get_learner_focus_items(user_id: int, workspace_id: int) -> list[dict]:
    """Top weaknesses over the act threshold in this workspace, for the answer hint.
    Each item carries its ``label`` and ``category`` so the prompt can treat terms and
    passages differently (see weakness_focus_appendix)."""
    now = datetime.now(timezone.utc)
    focus = lp.select_focus(_load_rows(user_id, workspace_id), now, _window_days())
    return [{"label": f["label"], "category": f["category"]} for f in focus]


def get_learner_weaknesses(user_id: int, workspace_id: int) -> list[dict]:
    """All still-live weaknesses in this workspace with effective weight, strongest
    first, for the profile view. Rows past the window (effective 0) are dropped."""
    now = datetime.now(timezone.utc)
    window = _window_days()
    out = []
    for r in _load_rows(user_id, workspace_id):
        eff = lp.effective_weight(r["weight"], r["last_seen_at"], now, window)
        if eff <= 0:
            continue
        out.append({
            "id": r["id"], "category": r["category"], "label": r["label"],
            "source_id": r["source_id"], "effective_weight": round(eff, 2),
            "hit_count": r["hit_count"], "last_seen_at": r["last_seen_at"].isoformat(),
        })
    out.sort(key=lambda x: x["effective_weight"], reverse=True)
    return out


def delete_learner_weakness(weakness_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_learner_weakness WHERE id = %s AND user_id = %s",
                (weakness_id, user_id),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def delete_all_learner_weaknesses(user_id: int, workspace_id: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_learner_weakness WHERE user_id = %s AND workspace_id = %s",
                (user_id, workspace_id),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted
