"""The counter that carries the statistics over all time."""
from datetime import timezone

from ._shared import psycopg2, get_connection

# For these tools the duration only counts from rendering on.
RENDER_TOOLS = ("screencast_render", "screencast_translate")

# Only these two outcomes are final states and therefore countable.
FINAL = ("success", "failed")

# The marker that this job ever existed.
GESTARTET = "started"


def _mit_zone(wert):
    """Compensates for missing time zones, the columns are in UTC."""
    if wert is None or wert.tzinfo is not None:
        return wert
    return wert.replace(tzinfo=timezone.utc)


def count_started(cur, tool: str) -> None:
    """Counts the creation of a job, expects an open cursor."""
    cur.execute(
        """INSERT INTO job_counts (day, hour, tool, status, runs, seconds)
           VALUES (
               (NOW() AT TIME ZONE 'Europe/Berlin')::date,
               EXTRACT(HOUR FROM (NOW() AT TIME ZONE 'Europe/Berlin')),
               %s, %s, 1, 0
           )
           ON CONFLICT (day, hour, tool, status) DO UPDATE
              SET runs = job_counts.runs + 1""",
        (tool, GESTARTET),
    )


def count_job(cur, tool: str, status: str, started, completed) -> None:
    """Counts a finished job, in the same transaction as the state."""
    if status not in FINAL or completed is None:
        return
    started, completed = _mit_zone(started), _mit_zone(completed)
    dauer = 0
    if status == "success" and started is not None:
        dauer = max(0, int((completed - started).total_seconds()))
    cur.execute(
        """INSERT INTO job_counts (day, hour, tool, status, runs, seconds)
           VALUES (
               (%s AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')::date,
               EXTRACT(HOUR FROM (%s AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin')),
               %s, %s, 1, %s
           )
           ON CONFLICT (day, hour, tool, status) DO UPDATE
              SET runs = job_counts.runs + 1,
                  seconds = job_counts.seconds + EXCLUDED.seconds""",
        (completed, completed, tool, status, dauer),
    )


def messpunkt(tool: str, started, render_started):
    """When the duration starts counting, screencasts only from rendering on."""
    if tool in RENDER_TOOLS and render_started is not None:
        return render_started
    return started


def get_counts(days: int | None = None) -> list[dict]:
    """The counter rows, optionally only the last N days."""
    wo = "WHERE day >= CURRENT_DATE - %s::int" if days else ""
    args = (days,) if days else ()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT day, hour, tool, status, runs, seconds
                    FROM job_counts {wo}
                    ORDER BY day, hour""",
                args,
            )
            return [
                {**dict(r), "day": str(r["day"]), "hour": int(r["hour"])}
                for r in cur.fetchall()
            ]
