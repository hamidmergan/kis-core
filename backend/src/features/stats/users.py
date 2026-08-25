"""Zahlen zu den Nutzern: wer da ist, wie viele dazukommen, wer bleibt.

Alles Zeitliche stuetzt sich auf `user_presence` und nicht auf die Auftraege.
Wer nur Uebungen macht oder ein PDF liest, startet nie einen Auftrag und waere
sonst unsichtbar. Genau die Gruppe ist bei der Frage nach Bindung die
interessante.
"""
import time

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.security import presence

# Ab wie vielen Tagen mit Anwesenheit jemand als regelmaessig gilt. Grob
# gegriffen, aber die Schwelle muss irgendwo liegen, und ein Wert im Code ist
# ehrlicher als eine Zahl, die im Diagramm erfunden aussieht.
REGELMAESSIG_AB_TAGEN = 10


def user_overview() -> dict:
    """Alles, was der Reiter Nutzer braucht, in einem Rutsch."""
    seit = presence.online_since()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            return {
                "online": _online_details(cur, seit),
                "totals": _totals(cur),
                "per_day": _per_day(cur),
                "today_by_hour": _today_by_hour(cur),
                "new_per_month": _new_per_month(cur),
                "retention": _retention(cur),
                "roles": _roles(cur),
                "people": _people(cur),
            }


def _online_details(cur, seit: dict[int, int]) -> dict:
    """Namen zu den Nummern. Ohne Namen waere die Liste eine Zahlenkolonne.

    Gezaehlt wird, wer sich wirklich zuordnen laesst, nicht wie viele Schluessel
    in Redis liegen. Ein geloeschter Nutzer laesst seinen Schluessel noch bis zum
    Ablauf stehen und wuerde die Zahl sonst aufblaehen.
    """
    if not seit:
        return {"count": 0, "users": []}
    jetzt = int(time.time())
    cur.execute(
        """SELECT id, display_name, ldap_username
           FROM users WHERE id = ANY(%s) ORDER BY display_name""",
        (list(seit),),
    )
    users = [
        {
            "id": r["id"],
            "name": r["display_name"] or r["ldap_username"] or "Unbekannt",
            # Minuten seit dem ersten Lebenszeichen, nicht seit dem letzten.
            "minutes": max(0, (jetzt - seit[r["id"]]) // 60),
        }
        for r in cur.fetchall()
    ]
    users.sort(key=lambda u: -u["minutes"])
    return {"count": len(users), "users": users}


def _totals(cur) -> dict:
    cur.execute("SELECT COUNT(*) AS n FROM users")
    gesamt = cur.fetchone()["n"]
    cur.execute(
        """SELECT COUNT(DISTINCT user_id) AS n FROM user_presence
           WHERE day >= CURRENT_DATE - 30"""
    )
    aktiv = cur.fetchone()["n"]
    cur.execute(
        """SELECT COUNT(*) AS n FROM users
           WHERE date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE)"""
    )
    neu = cur.fetchone()["n"]
    return {"total": gesamt, "active_30d": aktiv, "new_this_month": neu}


def _per_day(cur) -> list[dict]:
    """Verschiedene Personen je Tag, letzte 30 Tage."""
    cur.execute(
        """SELECT day, COUNT(DISTINCT user_id) AS n
           FROM user_presence WHERE day >= CURRENT_DATE - 30
           GROUP BY day ORDER BY day"""
    )
    return [{"day": str(r["day"]), "users": r["n"]} for r in cur.fetchall()]


def _today_by_hour(cur) -> list[dict]:
    """Heute, Stunde fuer Stunde. Die laufende Stunde bleibt draussen: sie ist
    noch nicht vorbei und stuende als volle Saeule falsch da."""
    cur.execute(
        """SELECT hour, COUNT(DISTINCT user_id) AS n
           FROM user_presence
           WHERE day = (NOW() AT TIME ZONE 'Europe/Berlin')::date
             AND hour < EXTRACT(HOUR FROM (NOW() AT TIME ZONE 'Europe/Berlin'))
           GROUP BY hour ORDER BY hour"""
    )
    gefunden = {int(r["hour"]): r["n"] for r in cur.fetchall()}
    letzte = max(gefunden) if gefunden else -1
    return [{"hour": h, "users": gefunden.get(h, 0)} for h in range(letzte + 1)]


def _new_per_month(cur) -> list[dict]:
    cur.execute(
        """SELECT to_char(date_trunc('month', created_at), 'MM/YY') AS monat,
                  date_trunc('month', created_at) AS sortier,
                  COUNT(*) AS n
           FROM users GROUP BY 1, 2 ORDER BY 2"""
    )
    return [{"month": r["monat"], "users": r["n"]} for r in cur.fetchall()]


def _retention(cur) -> dict:
    """Wie viele Tage jemand da war, in drei Gruppen.

    Ein Tag zaehlt, sobald an ihm ein Lebenszeichen kam. Das Lebenszeichen
    verlangt fuenf Minuten offene Seite, weil der Schluessel in Redis so lange
    lebt und nur von einer laufenden Leitung erneuert wird.
    """
    cur.execute(
        """SELECT tage, COUNT(*) AS n FROM (
               SELECT user_id, COUNT(DISTINCT day) AS tage
               FROM user_presence GROUP BY user_id
           ) je_nutzer
           GROUP BY tage"""
    )
    regelmaessig = gelegentlich = einmal = 0
    for r in cur.fetchall():
        if r["tage"] > REGELMAESSIG_AB_TAGEN:
            regelmaessig += r["n"]
        elif r["tage"] > 1:
            gelegentlich += r["n"]
        else:
            einmal += r["n"]
    return {
        "regular": regelmaessig,
        "occasional": gelegentlich,
        "once": einmal,
        "threshold_days": REGELMAESSIG_AB_TAGEN,
    }


def _people(cur) -> list[dict]:
    """Alle Namen fuer die Suche. Nur Nummer, Name und Rolle: die Detailansicht
    holt den Rest erst, wenn jemand gewaehlt wurde."""
    cur.execute(
        """SELECT u.id, COALESCE(u.display_name, u.ldap_username, 'Unbekannt') AS name,
                  COALESCE(c.name, u.role) AS rolle
           FROM users u LEFT JOIN custom_roles c ON u.custom_role_id = c.id
           ORDER BY 2"""
    )
    return [{"id": r["id"], "name": r["name"], "role": r["rolle"]} for r in cur.fetchall()]


def _roles(cur) -> list[dict]:
    cur.execute(
        """SELECT COALESCE(c.name, u.role) AS rolle, COUNT(*) AS n
           FROM users u
           LEFT JOIN custom_roles c ON u.custom_role_id = c.id
           GROUP BY 1 ORDER BY 2 DESC"""
    )
    return [{"role": r["rolle"], "users": r["n"]} for r in cur.fetchall()]
