"""Alles zu einer Person oder zu einem Modul an einer Stelle.

Der Zweck ist eine Frage, die man wirklich hat: "der Kollege sagt, bei ihm geht
Screencast nicht" oder "wieso hat dieses Modul 900 Uebungen". Dafuer musste man
bisher durch mehrere Reiter klicken und im Kopf zusammensetzen.

Eine Einschraenkung, die in der Oberflaeche steht: was eine Person an Auftraegen
gemacht hat, reicht nur so weit zurueck wie ihr Vorrat. Der Zaehler fuer die
Statistik kennt keine Nutzernummer, er zaehlt die Plattform, nicht Personen.
"""
from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.stats.assistant import FACHSPRACHE, KACHEL, SPRACHE

# Wie viele der juengsten Auftraege die Detailansicht zeigt.
LETZTE_JOBS = 5


def user_detail(user_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT u.id, COALESCE(u.display_name, u.ldap_username, 'Unbekannt') AS name,
                          COALESCE(c.name, u.role) AS rolle, u.language_level AS niveau,
                          u.created_at
                   FROM users u LEFT JOIN custom_roles c ON u.custom_role_id = c.id
                   WHERE u.id = %s""",
                (user_id,),
            )
            kopf = cur.fetchone()
            if not kopf:
                return None

            cur.execute(
                "SELECT MAX(day) AS zuletzt, COUNT(DISTINCT day) AS tage FROM user_presence WHERE user_id = %s",
                (user_id,),
            )
            anwesend = cur.fetchone()

            cur.execute(
                """SELECT tool, COUNT(*) AS n FROM jobs WHERE user_id = %s
                   GROUP BY tool ORDER BY 2 DESC""",
                (user_id,),
            )
            werkzeuge = [{"tool": r["tool"], "jobs": r["n"]} for r in cur.fetchall()]

            cur.execute(
                """SELECT tool, status, created_at FROM jobs WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (user_id, LETZTE_JOBS),
            )
            letzte = [
                {"tool": r["tool"], "status": r["status"],
                 "when": r["created_at"].isoformat() + "Z" if r["created_at"] else None}
                for r in cur.fetchall()
            ]

            cur.execute(
                """SELECT m.title, m.uuid,
                          CASE WHEN m.user_id = %s THEN 'owner' ELSE 'member' END AS rolle,
                          (SELECT COUNT(*) FROM aia_exercise_progress p
                             JOIN aia_exercise_sets s ON s.id = p.set_id
                            WHERE s.workspace_id = m.id AND p.user_id = %s) AS uebungen,
                          (SELECT COUNT(*) FROM aia_messages msg
                            WHERE msg.workspace_id = m.id AND msg.user_id = %s
                              AND msg.role = 'user') AS chat
                   FROM aia_workspaces m
                   WHERE m.user_id = %s
                      OR EXISTS (SELECT 1 FROM aia_enrollments e
                                  WHERE e.workspace_id = m.id AND e.user_id = %s)
                   ORDER BY 4 DESC""",
                (user_id, user_id, user_id, user_id, user_id),
            )
            module = [
                {"title": r["title"], "uuid": r["uuid"], "role": r["rolle"],
                 "answered": r["uebungen"], "chat": r["chat"]}
                for r in cur.fetchall()
            ]

            return {
                "id": kopf["id"],
                "name": kopf["name"],
                "role": kopf["rolle"],
                "level": kopf["niveau"],
                "since": kopf["created_at"].strftime("%m/%Y") if kopf["created_at"] else None,
                "last_seen": str(anwesend["zuletzt"]) if anwesend["zuletzt"] else None,
                "present_days": anwesend["tage"],
                "totals": {
                    "jobs": sum(w["jobs"] for w in werkzeuge),
                    "answered": sum(m["answered"] for m in module),
                    "chat": sum(m["chat"] for m in module),
                },
                "tools": werkzeuge,
                "modules": module,
                "recent": letzte,
            }


def workspace_detail(uuid: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT m.id, m.uuid, m.title, m.is_active, m.created_at,
                          COALESCE(u.display_name, u.ldap_username, 'Unbekannt') AS owner
                   FROM aia_workspaces m JOIN users u ON m.user_id = u.id
                   WHERE m.uuid = %s""",
                (uuid,),
            )
            kopf = cur.fetchone()
            if not kopf:
                return None
            mid = kopf["id"]

            cur.execute(
                """SELECT filename, file_type, chunk_count, status
                   FROM aia_sources WHERE workspace_id = %s
                   ORDER BY chunk_count DESC""",
                (mid,),
            )
            material = [
                {"name": r["filename"], "kind": r["file_type"],
                 "chunks": r["chunk_count"], "status": r["status"]}
                for r in cur.fetchall()
            ]

            # Die beiden Trainer getrennt, wie im Modul selbst.
            cur.execute(
                """SELECT s.tool,
                          (SELECT COUNT(*) FROM aia_exercise_items i WHERE i.set_id = s.id) AS erzeugt,
                          (SELECT COUNT(*) FROM aia_exercise_progress p WHERE p.set_id = s.id) AS beantwortet
                   FROM aia_exercise_sets s WHERE s.workspace_id = %s""",
                (mid,),
            )
            gruppen: dict[str, dict[str, dict]] = {"source": {}, "glossary": {}}
            for r in cur.fetchall():
                # Die Gruppe haengt am Werkzeug, nicht am Modus: derselbe Modus
                # kommt in beiden Trainern vor.
                kachel = KACHEL.get(r["tool"])
                if kachel in FACHSPRACHE:
                    wohin = "source"
                elif kachel in SPRACHE:
                    wohin = "glossary"
                else:
                    continue
                eintrag = gruppen[wohin].setdefault(
                    kachel, {"tool": kachel, "created": 0, "answered": 0}
                )
                eintrag["created"] += int(r["erzeugt"])
                eintrag["answered"] += int(r["beantwortet"])

            cur.execute(
                """SELECT COALESCE(u.display_name, u.ldap_username, 'Unbekannt') AS name,
                          (SELECT COUNT(*) FROM aia_exercise_progress p
                             JOIN aia_exercise_sets s ON s.id = p.set_id
                            WHERE s.workspace_id = %s AND p.user_id = u.id) AS uebungen,
                          (SELECT COUNT(*) FROM aia_messages msg
                            WHERE msg.workspace_id = %s AND msg.user_id = u.id
                              AND msg.role = 'user') AS chat
                   FROM aia_enrollments e JOIN users u ON e.user_id = u.id
                   WHERE e.workspace_id = %s
                   ORDER BY 2 DESC""",
                (mid, mid, mid),
            )
            leute = [
                {"name": r["name"], "answered": r["uebungen"], "chat": r["chat"]}
                for r in cur.fetchall()
            ]

            cur.execute(
                """SELECT COUNT(*) AS n, MAX(created_at) AS zuletzt
                   FROM aia_messages WHERE workspace_id = %s AND role = 'user'""",
                (mid,),
            )
            chat = cur.fetchone()

            sortiert = {
                k: sorted(v.values(), key=lambda x: x["created"], reverse=True)
                for k, v in gruppen.items()
            }
            return {
                "uuid": kopf["uuid"],
                "title": kopf["title"],
                "owner": kopf["owner"],
                "active": kopf["is_active"],
                "since": kopf["created_at"].strftime("%m/%Y") if kopf["created_at"] else None,
                "last": chat["zuletzt"].isoformat() + "Z" if chat["zuletzt"] else None,
                "totals": {
                    "members": len(leute),
                    "sources": len(material),
                    "created": sum(x["created"] for g in sortiert.values() for x in g),
                    "answered": sum(x["answered"] for g in sortiert.values() for x in g),
                    "chat": chat["n"],
                },
                "source_tools": sortiert["source"],
                "glossary_tools": sortiert["glossary"],
                "materials": material,
                "members": leute,
            }
