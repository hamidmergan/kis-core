"""Queues a summary for every ready source that was indexed before summaries existed."""
import argparse
import sys
import time
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import psycopg2.extras

from src.core.db.pool import get_connection

_OHNE_ZUSAMMENFASSUNG = """
    SELECT s.id, s.uuid, s.filename, w.title AS modul,
           coalesce(sum(length(c.content)), 0) AS zeichen
      FROM aia_sources s
      JOIN aia_workspaces w ON w.id = s.workspace_id
      LEFT JOIN aia_chunks c ON c.source_id = s.id
     WHERE s.status = 'ready'
       AND coalesce(s.summary, '') = ''
       AND (%(modul)s IS NULL OR w.title ILIKE %(modul)s)
       AND (%(mit_tests)s OR w.title NOT ILIKE ALL (ARRAY['LoadTest%%', 'SmokeTest%%']))
     GROUP BY s.id, s.uuid, s.filename, w.title, s.created_at
    HAVING coalesce(sum(length(c.content)), 0) > 0
     ORDER BY s.created_at
"""


def offene_quellen(limit: int | None, modul: str | None, mit_tests: bool) -> list[dict]:
    """The ready sources that have chunks but no summary, oldest first."""
    sql = _OHNE_ZUSAMMENFASSUNG + (" LIMIT %(limit)s" if limit else "")
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"limit": limit,
                              "modul": f"%{modul}%" if modul else None,
                              "mit_tests": mit_tests})
            return [dict(r) for r in cur.fetchall()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None, help="at most this many sources")
    p.add_argument("--start", action="store_true", help="do the work, otherwise only list")
    p.add_argument("--lanes", type=int, default=2, help="how many run at the same time")
    p.add_argument("--modul", default=None, help="only modules whose title contains this")
    p.add_argument("--mit-tests", action="store_true", help="include the LoadTest modules")
    args = p.parse_args()

    quellen = offene_quellen(args.limit, args.modul, args.mit_tests)
    if not quellen:
        print("Alle Quellen haben eine Zusammenfassung.")
        return 0

    zeichen = sum(q["zeichen"] for q in quellen)
    print(f"{len(quellen)} Quellen ohne Zusammenfassung, {zeichen:,} Zeichen".replace(",", "."))
    je_modul: dict[str, list[int]] = {}
    for q in quellen:
        eintrag = je_modul.setdefault(q["modul"], [0, 0])
        eintrag[0] += 1
        eintrag[1] += q["zeichen"]
    for modul, (anzahl, z) in sorted(je_modul.items(), key=lambda x: -x[1][1]):
        print(f"  {modul[:34]:36} {anzahl:>3} Quellen {z:>10,} Zeichen".replace(",", "."))

    if not args.start:
        print("\nNur gezeigt. Mit --start wird gearbeitet.")
        return 0

    # Sequential on purpose, in a few lanes: the queue would start sixteen at once
    # and every one of them would run into its timeout.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src import database as db
    from src.features.ai_assistant.tasks.ingestion import _build_source_summary_safely

    def eine(q: dict) -> tuple[str, float, int]:
        beginn = time.monotonic()
        _build_source_summary_safely(q["uuid"], db.get_chunks_by_source(q["id"]))
        quelle = db.get_aia_source(q["uuid"]) or {}
        return q["filename"], time.monotonic() - beginn, len(quelle.get("summary") or "")

    fertig = fehler = 0
    beginn = time.monotonic()
    print(f"\nLos, {args.lanes} gleichzeitig.")
    with ThreadPoolExecutor(max_workers=args.lanes) as pool:
        futures = {pool.submit(eine, q): q for q in quellen}
        for fut in as_completed(futures):
            name, dauer, laenge = fut.result()
            fertig += 1
            if not laenge:
                fehler += 1
            print(f"  [{fertig}/{len(quellen)}] {name[:44]:46} {dauer:5.1f}s "
                  f"{laenge:>6} Zeichen{'  OHNE' if not laenge else ''}", flush=True)
    print(f"\nFertig: {fertig - fehler} von {len(quellen)} in "
          f"{(time.monotonic() - beginn) / 60:.1f} Minuten, {fehler} ohne Zusammenfassung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
