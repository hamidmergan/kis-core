"""Retrieval benchmark: does the chat find the spot the answer lives in?"""
import argparse
import asyncio
import json
import math
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

_STANDARD_FAELLE = Path(__file__).parent / "rag_retrieval_cases.json"


def _lade_faelle(pfad=None) -> list[dict]:
    """The 19 grown hand-written cases, or another set via --faelle."""
    return json.loads(Path(pfad or _STANDARD_FAELLE).read_text(encoding="utf-8"))


CASES = _lade_faelle()


def _norm(s: str) -> str:
    """Flattens whitespace so a line break cannot make a spot unfindable."""
    return " ".join((s or "").split())


def _ndcg_at_k(platz: int | None, k: int = 10) -> float:
    """Score for one case from the rank of its carrying spot."""
    if platz is None or platz > k:
        return 0.0
    return 1.0 / math.log2(platz + 1)


def _mittel_ndcg(plaetze: list[int | None], k: int = 10) -> float:
    """The single number for the whole run, 0.0 instead of a division by zero."""
    if not plaetze:
        return 0.0
    return sum(_ndcg_at_k(p, k) for p in plaetze) / len(plaetze)


def _workspace(uuid: str) -> tuple[int, list[dict]]:
    """Workspace id and the active sources, as in the chat all ready ones."""
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


def _anchor_rank(ws_id: int, question: str, vec, source_id: int, wanted: set[int],
                 mode: str = "hybrid"):
    """Rank of the wanted spot in its source's hit list, or None."""
    hits = chunk_repo.hybrid_search_chunks(
        ws_id, question, vec, [source_id], chat_mod._NEIGHBOR_ANCHORS, fuzzy=False,
        mode=mode) or []
    for i, h in enumerate(hits):
        if h["id"] in wanted:
            return i + 1
    return None


def _wanted_chunks(ws_id: int, expect_text: list[str]) -> tuple[set[int], set[int]]:
    """Which chunks currently carry the wanted spots, and from which sources?"""
    wanted: set[int] = set()
    owner_ids: set[int] = set()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            for roh in expect_text:
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
    return wanted, owner_ids


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
        # Which chunks carry the spot, and at which rank do they sit?
        wanted, owner_ids = _wanted_chunks(ws_id, case["expect_text"])
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
    # The single number for the search, only over cases with a carrying spot.
    plaetze = [r["anchor_rank"] for r in results if r["anchor_ok"] is not None]
    if plaetze:
        print(f"NDCG@10 der Suche: {_mittel_ndcg(plaetze):.3f}  ({len(plaetze)} Faelle)")


def _vergleich(faelle: list[dict]) -> None:
    """The same cases once per search path, to see which path carries."""
    modi = ("hybrid", "dense", "keyword")
    provider = get_embedding_provider()
    plaetze: dict[str, list] = {m: [] for m in modi}
    namen: list[str] = []

    for case in faelle:
        if "expect_text" not in case:
            continue
        ws_id, _ = _workspace(case["workspace"])
        wanted, owner_ids = _wanted_chunks(ws_id, case["expect_text"])
        if not wanted:
            print(f"uebersprungen (Stelle nicht in der Ablage): {case['id']}", file=sys.stderr)
            continue
        namen.append(case["id"])
        vec = provider.embed([case["question"]])[0]
        for m in modi:
            ranks = [r for sid in owner_ids
                     if (r := _anchor_rank(ws_id, case["question"], vec, sid, wanted, m))
                     is not None]
            plaetze[m].append(min(ranks) if ranks else None)

    kopf = f"\n{'Fall':34s}" + "".join(f"{m:>10s}" for m in modi)
    print(kopf)
    print("-" * len(kopf))
    for i, name in enumerate(namen):
        zeile = f"{name:34s}"
        for m in modi:
            p = plaetze[m][i]
            zeile += f"{('-' if p is None else str(p)):>10s}"
        print(zeile)
    print("-" * len(kopf))
    print(f"{'NDCG@10':34s}" + "".join(f"{_mittel_ndcg(plaetze[m]):>10.3f}" for m in modi))
    print(f"{'in den Top 10':34s}"
          + "".join(f"{sum(1 for p in plaetze[m] if p and p <= 10):>10d}" for m in modi))
    print(f"\n{len(namen)} Faelle. Platz = Rang der tragenden Stelle, '-' = nicht gefunden.")


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    ap.add_argument("--baseline", help="Frueherer JSON-Stand; Exit 1 bei Rueckschritt")
    ap.add_argument("--only", help="Nur Faelle, deren id diesen Text enthaelt")
    ap.add_argument("--faelle", help="Andere Falldatei, z.B. rag_retrieval_cases_auto.json")
    ap.add_argument("--vergleich", action="store_true",
                    help="Dieselben Faelle je Suchweg (hybrid/dense/keyword) messen")
    args = ap.parse_args()

    alle = _lade_faelle(args.faelle)
    faelle = [c for c in alle if not args.only or args.only in c["id"]]

    if args.vergleich:
        _vergleich(faelle)
        return 0

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


