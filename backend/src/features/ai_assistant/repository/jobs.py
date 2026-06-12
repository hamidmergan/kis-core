"""DB-backed JobStore for the AIA orchestration queue (``aia_jobs`` table).

Implements the same ``JobStore`` protocol the in-memory store does, so the
``DispatchService`` runs identically in tests and in production. AIA-owned on
purpose: it must NOT share the global-tools ``jobs`` table, which is being
split into a separate project.

The queue claim in ``mark_running`` is guarded with ``FOR UPDATE`` so two
dispatch passes (backend + worker) cannot start the same job twice.
"""
from __future__ import annotations

import json
from typing import Optional

import psycopg2.extras
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.ai_assistant.scheduling.dispatch_service import Job
from src.features.ai_assistant.scheduling.fair_dispatch import QueuedJob


class DbJobStore:
    def add(self, job: Job) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO aia_jobs (job_uuid, user_id, area, task_name, payload, status)
                       VALUES (%s, %s, %s, %s, %s, 'queued')
                       ON CONFLICT (job_uuid) DO NOTHING""",
                    (job.job_uuid, job.user_id, job.area, job.task_name, json.dumps(job.payload)),
                )
            conn.commit()

    def get(self, job_uuid: str) -> Optional[Job]:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM aia_jobs WHERE job_uuid = %s", (job_uuid,))
                row = cur.fetchone()
        if row is None:
            return None
        return Job(
            job_uuid=row["job_uuid"],
            user_id=row["user_id"],
            area=row["area"],
            task_name=row["task_name"],
            payload=row["payload"] or {},
            created_at=row["created_at"].timestamp(),
            status=row["status"],
            celery_task_id=row["celery_task_id"],
            error=row["error"],
        )

    def queued(self, area: str) -> list[QueuedJob]:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT job_uuid, user_id, created_at FROM aia_jobs
                       WHERE area = %s AND status = 'queued'
                       ORDER BY created_at ASC""",
                    (area,),
                )
                rows = cur.fetchall()
        return [QueuedJob(r["job_uuid"], r["user_id"], r["created_at"].timestamp()) for r in rows]

    def running_user_ids(self, area: str) -> list[int]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id FROM aia_jobs WHERE area = %s AND status = 'running'",
                    (area,),
                )
                return [r[0] for r in cur.fetchall()]

    def mark_running(self, job_uuid: str, celery_task_id: str) -> None:
        """Claim a queued job atomically. No-op if it is no longer queued."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM aia_jobs WHERE job_uuid = %s FOR UPDATE",
                    (job_uuid,),
                )
                row = cur.fetchone()
                if row is None or row[0] != "queued":
                    conn.rollback()
                    return
                cur.execute(
                    """UPDATE aia_jobs
                       SET status = 'running', celery_task_id = %s, started_at = NOW()
                       WHERE job_uuid = %s""",
                    (celery_task_id, job_uuid),
                )
            conn.commit()

    def mark_finished(self, job_uuid: str, ok: bool, error: Optional[str]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE aia_jobs
                       SET status = %s, error = %s, finished_at = NOW()
                       WHERE job_uuid = %s""",
                    ("done" if ok else "failed", error, job_uuid),
                )
            conn.commit()
