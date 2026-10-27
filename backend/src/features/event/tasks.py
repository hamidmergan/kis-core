"""The task card in storage: one tick per account and task, shown only to accounts from the card's code."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from loguru import logger

from src.core.db.pool import get_connection
from src.features.event import repository as repo
from src.features.event.service import TASK_IDS, task_card_for, tasks_view

# The card's window is a calendar day where the event takes place.
_TZ_BERLIN = ZoneInfo("Europe/Berlin")


def _today() -> date:
    return datetime.now(_TZ_BERLIN).date()


def _epoch_ms(done_at: datetime) -> int:
    """The database keeps naive UTC timestamps, the browser wants milliseconds."""
    if done_at.tzinfo is None:
        done_at = done_at.replace(tzinfo=timezone.utc)
    return int(done_at.timestamp() * 1000)


def user_access_code(user_id: int) -> str | None:
    """The code this account was made from, None for accounts without one."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.code FROM users u
                       JOIN access_codes c ON c.id = u.access_code_id
                   WHERE u.id = %s""",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def workspaces_for_code(code: str) -> list[dict]:
    """The workspaces an access code enrols into, the choices for the question task."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT w.uuid, w.title FROM access_code_workspaces cw
                       JOIN access_codes c ON c.id = cw.code_id
                       JOIN aia_workspaces w ON w.id = cw.workspace_id
                   WHERE UPPER(c.code) = UPPER(%s)
                   ORDER BY w.title""",
                (code.strip(),),
            )
            return [{"uuid": uuid, "title": title} for uuid, title in cur.fetchall()]


def workspace_title(workspace_uuid: str) -> str:
    """The title of the question task's workspace, empty when none is set or it is gone."""
    if not workspace_uuid:
        return ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM aia_workspaces WHERE uuid = %s", (workspace_uuid,))
            row = cur.fetchone()
            return row[0] if row else ""


def done_for(user_id: int) -> dict[str, int]:
    """Every tick of this account, task id to the moment it was set."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT task_id, done_at FROM event_tasks WHERE user_id = %s", (user_id,))
            return {task_id: _epoch_ms(done_at) for task_id, done_at in cur.fetchall()}


def add_done(user_id: int, task_id: str) -> None:
    """Ticks once, doing the same task again changes nothing."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO event_tasks (user_id, task_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, task_id),
            )
        conn.commit()


def counts() -> dict:
    """How many accounts ticked each task and how many ticked all of them."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT task_id, COUNT(*) FROM event_tasks WHERE task_id = ANY(%s) GROUP BY task_id",
                (list(TASK_IDS),),
            )
            je_aufgabe = {task_id: int(anzahl) for task_id, anzahl in cur.fetchall()}
            cur.execute(
                """SELECT COUNT(*) FROM (
                       SELECT user_id FROM event_tasks WHERE task_id = ANY(%s)
                       GROUP BY user_id HAVING COUNT(DISTINCT task_id) = %s
                   ) AS voll""",
                (list(TASK_IDS), len(TASK_IDS)),
            )
            voll = int(cur.fetchone()[0])
    return {"byTask": {task_id: je_aufgabe.get(task_id, 0) for task_id in TASK_IDS}, "complete": voll}


def delete_all() -> None:
    """Empties every task card at once."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM event_tasks")
        conn.commit()


def card_for(user_id: int) -> dict | None:
    """The task card config if this account sees it today, else None."""
    karte = repo.get_config()["taskCard"]
    return karte if task_card_for(karte, _today(), user_access_code(user_id)) else None


def view_for(user_id: int) -> dict:
    """What the services page shows this account."""
    karte = card_for(user_id)
    if karte is None:
        return {"visible": False}
    return tasks_view(done_for(user_id), karte["workspace"], workspace_title(karte["workspace"]))


def mark_question(user_id: int, workspace_uuid: str) -> None:
    """Ticks the question task once a question is sent in the card's workspace, never breaks the chat."""
    try:
        karte = card_for(user_id)
        if karte is not None and karte["workspace"] and karte["workspace"] == workspace_uuid:
            add_done(user_id, "question")
    except Exception as fehler:
        logger.warning("Event task tick failed user={}: {}", user_id, fehler)
