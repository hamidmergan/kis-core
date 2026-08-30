"""Numbers for the global tools, counted at creation instead of from jobs."""
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection

ZEITRAEUME = {"jahr": 365, "halbjahr": 182, "30t": 30}

# Only the creation row counts as a job.
GESTARTET = "status = 'started'"

# A screencast stays a screencast, translated or not.
ZUSAMMEN = {"screencast_render": "screencast", "screencast_translate": "screencast"}

# All tools that create jobs, the never run ones included.
WERKZEUGE = [
    "screencast", "transcription", "translation", "tts", "summary",
    "image_generate", "image_edit", "image_analyze",
]


def tool_overview(zeitraum: str = "30t") -> dict:
    """Tiles, bars per tool and the weekday by hour grid."""
    tage = ZEITRAEUME.get(zeitraum)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            return {
                "range": zeitraum,
                "totals": _totals(cur, tage),
                "per_tool": _per_tool(cur, tage),
                "heat": _heat(cur, tage),
            }


def _wo(tage: int) -> tuple[str, tuple]:
    return f"WHERE {GESTARTET} AND day >= CURRENT_DATE - %s::int", (tage,)


def _totals(cur, tage) -> dict:
    wo, args = _wo(tage)
    cur.execute(f"SELECT COALESCE(SUM(runs), 0) AS n FROM job_counts {wo}", args)
    return {"jobs": int(cur.fetchone()["n"])}


def _per_tool(cur, tage) -> list[dict]:
    """How often each tool was started, the never started ones included."""
    wo, args = _wo(tage)
    cur.execute(f"SELECT tool, SUM(runs) AS gesamt FROM job_counts {wo} GROUP BY tool", args)
    jobs: dict[str, int] = {}
    for r in cur.fetchall():
        name = ZUSAMMEN.get(r["tool"], r["tool"])
        jobs[name] = jobs.get(name, 0) + int(r["gesamt"])

    zeilen = [{"tool": w, "jobs": jobs.get(w, 0)} for w in WERKZEUGE]
    return sorted(zeilen, key=lambda z: z["jobs"], reverse=True)


def _heat(cur, tage) -> list[list[float]]:
    """Average per weekday and hour so periods stay comparable."""
    wo, args = _wo(tage)
    cur.execute(
        f"""SELECT EXTRACT(ISODOW FROM day)::int AS wochentag,
                   hour::int AS stunde,
                   SUM(runs)::float AS summe,
                   COUNT(DISTINCT day)::float AS tage
            FROM job_counts {wo}
            GROUP BY 1, 2""",
        args,
    )
    raster = [[0.0] * 24 for _ in range(7)]
    for r in cur.fetchall():
        raster[r["wochentag"] - 1][r["stunde"]] = r["summe"] / max(1.0, r["tage"])
    return raster
