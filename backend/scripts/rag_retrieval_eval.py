"""Messsatz fuer den Abruf: findet der Chat die Stelle, in der die Antwort steht?

Aufruf aus backend/:  python scripts/rag_retrieval_eval.py
Vergleich zweier Staende:  python scripts/rag_retrieval_eval.py --json > vorher.json

Warum es das gibt. Die Bausteine des Abrufs haben Unit-Tests mit ausgedachten
Zahlen, und die waren alle gruen, waehrend zwei Fragen, deren Antwort woertlich
in den Quellen steht, nicht beantwortet wurden. Ein gruener Baustein sagt nichts
darueber, ob die richtige Stelle beim Modell ankommt. Genau das misst dieser Satz,
und zwar an echten Workspaces, nicht an Attrappen.

Gemessen wird auf zwei Ebenen, weil die Fehler auf zwei Ebenen sitzen:

* ``anchor``  — steht die Stelle ueberhaupt in der Trefferliste ihrer Quelle?
                Das ist die Frage an die SUCHE.
* ``context`` — schafft sie es bis in den Prompt?
                Das ist die Frage an die VERTEILUNG des Platzes.

Eine Stelle kann als Treffer 1 gefunden und trotzdem weggeschnitten werden. Ohne
die Trennung sieht man nur, dass etwas fehlt, aber nicht wo.

Zwei Fallarten:

* ``expect_text``         — mindestens eine dieser Textstellen muss im Kontext stehen.
                            Bewusst der TEXT und nicht die Chunk-ID: beim Neu-Zerlegen
                            einer Quelle bekommen alle Chunks neue IDs, ein Messsatz
                            an IDs waere danach wertlos. Die Stelle bleibt dieselbe.
                            Kurz halten, damit sie keine Chunk-Grenze kreuzt.
* ``expect_sources_all``  — von JEDER dieser Dateien muss etwas im Kontext sein.
                            Der Waechter fuer Vergleichsfragen: er haelt fest, was
                            die Quote pro Quelle leisten soll, damit ein Umbau sie
                            nicht unbemerkt kaputt macht.

Der Satz ruft ``_retrieve_specific_context`` auf, also genau den Code, der auch im
Chat laeuft. Keine Kopie, die auseinanderlaeuft.

Exit 0, wenn kein Fall schlechter ist als in ``--baseline``, sonst 1.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import psycopg2.extras

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository import chunks as chunk_repo
from src.features.ai_assistant.routes import chat as chat_mod
from src.services.aia_embeddings import get_embedding_provider

CASES = json.loads((Path(__file__).parent / "rag_retrieval_cases.json").read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    """Ein Leerzeichen statt beliebigem Zwischenraum, damit ein Zeilenumbruch im
    Dokument keine Textstelle unauffindbar macht."""
    return " ".join((s or "").split())


def _workspace(uuid: str) -> tuple[int, list[dict]]:
    """Workspace-ID und die aktiven Quellen. Wie im Chat: alle fertigen Quellen."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM aia_workspaces WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Workspace {uuid!r} nicht gefunden")
            ws_id = row["id"]
            cur.execute(
                "SELECT id, filename FROM aia_sources "
                "WHERE workspace_id = %s AND status = 'ready' ORDER BY filename",
                (ws_id,),
            )
            return ws_id, [dict(r) for r in cur.fetchall()]


def _anchor_rank(ws_id: int, question: str, vec, source_id: int, wanted: set[int]):
    """Platz der gesuchten Stelle in der Trefferliste IHRER Quelle, oder None.

    Getrennt von der Kontext-Pruefung, damit ein Fehlschlag zeigt, ob die Suche
    die Stelle nicht findet oder die Verteilung sie wegwirft."""
    hits = chunk_repo.hybrid_search_chunks(
        ws_id, question, vec, [source_id], chat_mod._NEIGHBOR_ANCHORS, fuzzy=False) or []
    for i, h in enumerate(hits):
        if h["id"] in wanted:
            return i + 1
    return None


async def _run_case(case: dict) -> dict:
    ws_id, sources = _workspace(case["workspace"])
    source_ids = [s["id"] for s in sources]
    names = {s["id"]: s["filename"] for s in sources}
    provider = get_embedding_provider()
    budget = chat_mod._context_budget()

    chunks = await chat_mod._retrieve_specific_context(
        provider, ws_id, source_ids, [case["question"]], case["question"], budget,
    )
    got = {c["id"] for c in chunks}
    got_files = {names.get(c["source_id"], "?") for c in chunks}
    chars = sum(len(c.get("content") or "") for c in chunks)

    out = {
        "id": case["id"], "question": case["question"],
        "chunks": len(chunks), "chars": chars, "sources_in_context": len(got_files),
    }

    if "expect_text" in case:
        phrasen = [_norm(p) for p in case["expect_text"]]
        out["context_ok"] = any(p in _norm(c.get("content") or "")
                                for c in chunks for p in phrasen)
        # Welche Chunks tragen die Stelle GERADE, und auf welchem Platz stehen sie in
        # der Trefferliste ihrer Quelle? Ueber den Text nachgeschlagen, damit das auch
        # nach einem Neu-Zerlegen noch stimmt.
        wanted, owner_ids = set(), set()
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for roh in case["expect_text"]:
                    cur.execute(
                        """SELECT c.id, c.source_id FROM aia_chunks c
                             JOIN aia_sources s ON s.id = c.source_id
                            WHERE s.workspace_id = %s
                              AND regexp_replace(c.content, '\\s+', ' ', 'g') ILIKE %s""",
                        (ws_id, f"%{_norm(roh)}%"),
                    )
                    for r in cur.fetchall():
                        wanted.add(r["id"])
                        owner_ids.add(r["source_id"])
        if not wanted:
            out["context_ok"] = False
            out["anchor_ok"] = False
            out["anchor_rank"] = None
            out["missing_sources"] = ["TEXTSTELLE NICHT IN DER ABLAGE"]
            return out
        vec = provider.embed([case["question"]])[0]
        ranks = [r for sid in owner_ids
                 if (r := _anchor_rank(ws_id, case["question"], vec, sid, wanted)) is not None]
        out["anchor_rank"] = min(ranks) if ranks else None
        out["anchor_ok"] = bool(ranks)
    else:
        needed = set(case["expect_sources_all"])
        out["context_ok"] = needed <= got_files
        out["missing_sources"] = sorted(needed - got_files)
        out["anchor_ok"] = None
        out["anchor_rank"] = None
    return out


def _print(results: list[dict]) -> None:
    ok = sum(1 for r in results if r["context_ok"])
    print(f"\n{'Fall':38s} {'Suche':>10s} {'Kontext':>8s} {'Chunks':>7s} {'Zeichen':>8s}")
    print("-" * 78)
    for r in results:
        suche = ("-" if r["anchor_ok"] is None
                 else (f"Platz {r['anchor_rank']}" if r["anchor_ok"] else "NICHT"))
        print(f"{r['id']:38s} {suche:>10s} {'JA' if r['context_ok'] else 'NEIN':>8s} "
              f"{r['chunks']:7d} {r['chars']:8d}")
        if r.get("missing_sources"):
            print(f"{'':38s} fehlende Quellen: {', '.join(r['missing_sources'])}")
    print("-" * 78)
    print(f"Im Kontext gefunden: {ok}/{len(results)}")


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    ap.add_argument("--baseline", help="Frueherer JSON-Stand; Exit 1 bei Rueckschritt")
    ap.add_argument("--only", help="Nur Faelle, deren id diesen Text enthaelt")
    args = ap.parse_args()

    faelle = [c for c in CASES if not args.only or args.only in c["id"]]
    results = [await _run_case(c) for c in faelle]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        _print(results)

    if args.baseline:
        alt = {r["id"]: r for r in json.loads(Path(args.baseline).read_text(encoding="utf-8"))}
        schlechter = [r["id"] for r in results
                      if alt.get(r["id"], {}).get("context_ok") and not r["context_ok"]]
        if schlechter:
            print(f"\nRUECKSCHRITT bei: {', '.join(schlechter)}", file=sys.stderr)
            return 1
        print("\nKein Rueckschritt gegenueber der Grundlinie.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
