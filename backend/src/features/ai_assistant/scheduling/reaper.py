"""Takes back slots of the shared pool whose job the broker no longer holds."""
from __future__ import annotations

import time
from typing import Callable, Optional

from loguru import logger

# Between taking a slot and storing the Celery id lies a short moment without an id.
GRACE_SECONDS = 120


def reap(store, stand, outcome: Callable[[str, dict], Optional[str]], *, now: float | None = None) -> int:
    """Frees orphaned slots, finished work only reports, unfinished work goes back in line."""
    if stand is None:
        return 0
    now = time.time() if now is None else now
    freed = 0
    for row in store.running_rows():
        if row["started_at"] is not None and now - row["started_at"] < GRACE_SECONDS:
            continue
        if stand.holds(row["celery_task_id"]):
            continue
        ergebnis = outcome(row["task_name"], row["payload"] or {})
        if ergebnis is None:
            store.requeue(row["job_uuid"])
        else:
            store.mark_finished(row["job_uuid"], ok=ergebnis == "done", error="Platz verwaist, zurückgeholt")
        logger.warning("KI Tutor: verwaister Platz {} ({}) zurückgeholt, Arbeit {}",
                       row["job_uuid"][:8], row["task_name"], ergebnis or "neu eingereiht")
        freed += 1
    return freed


def outcome_of(task_name: str, payload: dict) -> Optional[str]:
    """Whether the work behind a slot got done, "done", "failed" or None when unfinished."""
    from src import database as db

    args = payload.get("args") or []
    if task_name == "aia.index_source" and args:
        quelle = db.get_aia_source(args[0])
        stand = quelle and quelle.get("status")
        return {"ready": "done", "failed": "failed"}.get(stand) if quelle else "failed"
    if task_name == "aia.generate_mindmap" and args:
        karte = db.get_aia_mindmap(args[0])
        stand = karte and karte.get("status")
        return {"success": "done", "failed": "failed"}.get(stand) if karte else "failed"
    if task_name == "aia.generate_exercise_set" and args:
        satz = db.get_exercise_set_with_items(args[0])
        return {"ready": "done", "failed": "failed"}.get(satz.get("status")) if satz else "failed"
    if task_name == "aia.generate_data_table" and args:
        tabelle = db.get_aia_data_table(args[0])
        return {"success": "done", "failed": "failed"}.get(tabelle.get("status")) if tabelle else "failed"
    if task_name == "aia.generate_schedule" and len(args) > 2:
        plan = db.get_schedule_job(args[0], args[2])
        return {"success": "done", "failed": "failed"}.get(plan.get("status")) if plan else "failed"
    # An unknown kind is not run twice, its slot is only given back.
    return "failed"
