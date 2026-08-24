"""Aufbewahrung: pro Nutzer bleiben die letzten N Auftraege stehen.

Wie viele N sind, steht im Admin (``services/tool_limits.py``), ``-1`` heisst
unbegrenzt und raeumt gar nichts.

Frueher gab es zusaetzlich eine Frist von sieben Tagen. Sie ist raus, damit ein
Nutzer nichts mehr verliert, was in seiner Liste noch sichtbar ist. Damit ist der
Vorrat die einzige Regel, und er muss alles raeumen, was die Frist frueher
mitgenommen hat: auch Fehlschlaege und abgebrochene Laeufe, nicht nur fertige
Ergebnisse.

Die Auswahl selbst ist eine reine Funktion, damit sie ohne Datenbank pruefbar ist.
"""
from ._shared import psycopg2, get_connection

# Laufende Auftraege werden nie geraeumt, sonst reisst die Raeumung einem Nutzer
# den Job unter den Fuessen weg, an dem er gerade arbeitet. Haengengebliebene
# Laeufe fallen dem Wachhund zu, der sie auf "failed" setzt, danach sind sie hier
# ganz normal raeumbar.
ACTIVE_STATUSES = ("pending", "queued", "running", "awaiting_user")


def select_jobs_to_evict(
    jobs_newest_first: list[dict],
    cap: int | None = None,
) -> list[dict]:
    """Welche Jobs fallen aus dem Vorrat? Erwartet die Liste neueste zuerst.

    Laufende Jobs belegen einen Platz, werden aber nie selbst geraeumt. Ohne
    ``cap`` gilt der Wert aus dem Admin, ``-1`` raeumt nichts.
    """
    if cap is None:
        from src.services.tool_limits import results_kept_per_user
        cap = results_kept_per_user()
    if cap < 0:
        return []
    return [job for job in jobs_newest_first[cap:] if job["status"] not in ACTIVE_STATUSES]


def get_jobs_for_user_newest_first(user_id: int) -> list[dict]:
    """Alle Jobs eines Nutzers, neueste zuerst. Grundlage jeder Raeumung."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, user_id, status, original_filename, result_filename
                   FROM jobs WHERE user_id = %s
                   ORDER BY created_at DESC""",
                (user_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_users_over_cap(cap: int | None = None) -> list[int]:
    """Nutzer mit mehr Jobs als erlaubt. Fuer das naechtliche Nachraeumen.

    Noetig fuer den Fall, dass jemand nur Fehlschlaege produziert: die Raeumung
    beim Speichern eines Ergebnisses laeuft dann naemlich nie an.
    """
    if cap is None:
        from src.services.tool_limits import results_kept_per_user
        cap = results_kept_per_user()
    if cap < 0:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM jobs GROUP BY user_id HAVING COUNT(*) > %s",
                (cap,),
            )
            return [row[0] for row in cur.fetchall()]
