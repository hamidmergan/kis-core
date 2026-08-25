"""Zahlen zu den globalen Werkzeugen.

Die Quelle ist `job_counts` und nicht `jobs`: aus `jobs` faellt pro Nutzer alles
ueber dem Vorrat wieder heraus, und geloeschte Auftraege sind ganz weg. Gezaehlt
wird deshalb beim Anlegen, und diese Zeile bleibt, was mit dem Auftrag danach
auch passiert. Siehe features/jobs/repository/_counts.py.
"""
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection

# Wie stark ein Zeitraum den Schnitt verduennt, haengt an der Zahl der Tage.
# Ohne Angabe zaehlt alles seit dem ersten Eintrag.
ZEITRAEUME = {"alles": None, "jahr": 365, "30t": 30}

# Nur die Zeile vom Anlegen zaehlt als Auftrag. Die Endzustaende stehen in
# derselben Tabelle und wuerden sonst ein zweites Mal mitgezaehlt.
GESTARTET = "status = 'started'"

# Ein Screencast bleibt ein Screencast, ob er uebersetzt wurde oder nicht.
ZUSAMMEN = {"screencast_render": "screencast", "screencast_translate": "screencast"}

# Alle Werkzeuge, die Auftraege anlegen. Auch die, die noch nie gelaufen sind:
# eine fehlende Zeile heisst null und soll auch als null dastehen.
WERKZEUGE = [
    "screencast", "transcription", "translation", "tts", "summary",
    "image_generate", "image_edit", "image_analyze",
]


def tool_overview(zeitraum: str = "alles") -> dict:
    """Kacheln, Balken je Werkzeug und das Raster Wochentag mal Stunde."""
    tage = ZEITRAEUME.get(zeitraum)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            return {
                "range": zeitraum,
                "totals": _totals(cur, tage),
                "per_tool": _per_tool(cur, tage),
                "heat": _heat(cur, tage),
            }


def _wo(tage: int | None) -> tuple[str, tuple]:
    if tage is None:
        return f"WHERE {GESTARTET}", ()
    return f"WHERE {GESTARTET} AND day >= CURRENT_DATE - %s::int", (tage,)


def _totals(cur, tage) -> dict:
    wo, args = _wo(tage)
    cur.execute(f"SELECT COALESCE(SUM(runs), 0) AS n FROM job_counts {wo}", args)
    return {"jobs": int(cur.fetchone()["n"])}


def _per_tool(cur, tage) -> list[dict]:
    """Wie oft jedes Werkzeug gestartet wurde, auch die nie gestarteten."""
    wo, args = _wo(tage)
    cur.execute(f"SELECT tool, SUM(runs) AS gesamt FROM job_counts {wo} GROUP BY tool", args)
    jobs: dict[str, int] = {}
    for r in cur.fetchall():
        name = ZUSAMMEN.get(r["tool"], r["tool"])
        jobs[name] = jobs.get(name, 0) + int(r["gesamt"])

    zeilen = [{"tool": w, "jobs": jobs.get(w, 0)} for w in WERKZEUGE]
    return sorted(zeilen, key=lambda z: z["jobs"], reverse=True)


def _heat(cur, tage) -> list[list[float]]:
    """Durchschnitt je Wochentag und Stunde.

    Durchschnitt und nicht Summe: sonst waeren die Zahlen zwischen den Zeitraeumen
    nicht vergleichbar, weil "alles" mehr Wochen enthaelt als "30 Tage". Geteilt
    wird durch die Zahl der Vorkommen dieses Wochentags im Zeitraum.

    Rueckgabe: sieben Zeilen (Montag zuerst) mal vierundzwanzig Stunden.
    """
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
