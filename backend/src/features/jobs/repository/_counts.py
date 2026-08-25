"""Der Zaehler, der die Statistik ueber die ganze Zeit traegt.

Aus `jobs` faellt pro Nutzer alles ueber dem Vorrat wieder heraus, siehe
``_retention.py``. Wer also aus `jobs` eine Statistik zieht, bekommt die Reste
und nicht die Geschichte. Deshalb wird hier beim Abschluss jedes Auftrags eine
Zeile hochgezaehlt, die nie wieder geloescht wird.

Gezaehlt wird genau einmal je Auftrag: der Aufrufer haelt die Zeile gesperrt und
gibt den vorherigen Zustand mit. Wer schon fertig war, zaehlt nicht nochmal.
"""
from datetime import timezone

from ._shared import psycopg2, get_connection

# Bei diesen Werkzeugen ist die Vorbereitung nicht die Arbeit. Gemessen wird ab
# dem Start des Renderns, sonst stuende in der Dauer die Wartezeit auf den
# Nutzer mit drin. Gleiche Regel wie in _stats.py.
RENDER_TOOLS = ("screencast_render", "screencast_translate")

# Nur diese beiden Ausgaenge sind Endzustaende und damit zaehlbar.
FINAL = ("success", "failed")

# Der Zustand der Zeile, die beim Anlegen geschrieben wird. Kein echter Zustand
# eines Auftrags, sondern der Merker "dieser Auftrag hat es je gegeben".
GESTARTET = "started"


def _mit_zone(wert):
    """Zeiten aus `jobs` kommen ohne Zone, die des Aufrufers mit einer.

    Ohne diesen Ausgleich scheitert schon das Abziehen. Die Spalten stehen in
    UTC, also wird eine fehlende Zone als UTC gelesen.
    """
    if wert is None or wert.tzinfo is not None:
        return wert
    return wert.replace(tzinfo=timezone.utc)


def count_started(cur, tool: str) -> None:
    """Das Anlegen eines Auftrags mitzaehlen. Erwartet einen offenen Cursor.

    Diese Zeile ist die einzige Spur, die bleibt: der Auftrag selbst faellt
    spaeter aus `jobs` heraus, geloescht oder ueber dem Vorrat, und ein Auftrag,
    den jemand abbricht, erreicht nie einen Endzustand. Gezaehlt wird deshalb
    beim Anlegen und nicht beim Abschluss.
    """
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
    """Einen abgeschlossenen Auftrag mitzaehlen. Erwartet einen offenen Cursor.

    Laeuft bewusst im selben Vorgang wie das Setzen des Zustands: entweder beides
    oder keines. Ein eigener Vorgang koennte auf halbem Weg abbrechen und die
    Zahlen von der Wahrheit trennen.
    """
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
    """Ab wann die Dauer zaehlt. Screencasts erst ab dem Rendern."""
    if tool in RENDER_TOOLS and render_started is not None:
        return render_started
    return started


def get_counts(days: int | None = None) -> list[dict]:
    """Die Zaehlzeilen, wahlweise nur die letzten N Tage.

    Ohne ``days`` kommt alles, was je gezaehlt wurde. Genau das ist der Zweck
    der Tabelle: eine Statistik, die nicht mit dem Aufraeumen schrumpft.
    """
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
