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
    """Die 19 gewachsenen Handfaelle, oder ein anderer Satz per --faelle.

    Der breite, maschinell erzeugte Satz liegt bewusst in einer eigenen Datei
    (siehe scripts/build_retrieval_cases.py). Die Handfaelle bewachen bekannte
    Schwachstellen und stehen fast an der Decke, der breite Satz misst den
    Normalfall. Zusammengeworfen wuerde keiner von beiden mehr etwas sagen."""
    return json.loads(Path(pfad or _STANDARD_FAELLE).read_text(encoding="utf-8"))


CASES = _lade_faelle()


def _norm(s: str) -> str:
    """Ein Leerzeichen statt beliebigem Zwischenraum, damit ein Zeilenumbruch im
    Dokument keine Textstelle unauffindbar macht."""
    return " ".join((s or "").split())


def _ndcg_at_k(platz: int | None, k: int = 10) -> float:
    """Punktzahl fuer EINEN Fall aus dem Platz seiner tragenden Stelle.

    Jeder Fall hat genau eine richtige Stelle, damit faellt die ideale Rangfolge
    auf 1 zusammen und NDCG@k verkuerzt sich auf ``1 / log2(platz + 1)``. Platz 1
    gibt 1.0, Platz 3 gibt 0.5, Platz 10 gibt 0.29. Was hinter der Schranke steht,
    sieht das Modell nicht und zaehlt deshalb null statt wenig."""
    if platz is None or platz > k:
        return 0.0
    return 1.0 / math.log2(platz + 1)


def _mittel_ndcg(plaetze: list[int | None], k: int = 10) -> float:
    """Die eine Zahl fuer den ganzen Lauf. Ohne Faelle 0.0 statt Division durch null."""
    if not plaetze:
        return 0.0
    return sum(_ndcg_at_k(p, k) for p in plaetze) / len(plaetze)


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


def _anchor_rank(ws_id: int, question: str, vec, source_id: int, wanted: set[int],
                 mode: str = "hybrid"):
    """Platz der gesuchten Stelle in der Trefferliste IHRER Quelle, oder None.

    Getrennt von der Kontext-Pruefung, damit ein Fehlschlag zeigt, ob die Suche
    die Stelle nicht findet oder die Verteilung sie wegwirft.

    ``mode`` schaltet fuer --vergleich einen der beiden Suchwege ab."""
    hits = chunk_repo.hybrid_search_chunks(
        ws_id, question, vec, [source_id], chat_mod._NEIGHBOR_ANCHORS, fuzzy=False,
        mode=mode) or []
    for i, h in enumerate(hits):
        if h["id"] in wanted:
            return i + 1
    return None


def _wanted_chunks(ws_id: int, expect_text: list[str]) -> tuple[set[int], set[int]]:
    """Welche Chunks tragen die gesuchten Stellen GERADE, und aus welchen Quellen?

    Ueber den Text nachgeschlagen statt ueber IDs, damit die Zuordnung ein
    Neu-Zerlegen der Quelle ueberlebt: dabei bekommen alle Chunks neue IDs, die
    Textstelle bleibt aber dieselbe."""
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
        # Welche Chunks tragen die Stelle GERADE, und auf welchem Platz stehen sie in
        # der Trefferliste ihrer Quelle?
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
    # Die eine Zahl fuer die SUCHE, nur ueber die Faelle mit einer tragenden Stelle.
    # Vergleichsfaelle (expect_sources_all) haben keinen einzelnen Platz und wuerden
    # als Nullen den Mittelwert verfaelschen.
    plaetze = [r["anchor_rank"] for r in results if r["anchor_ok"] is not None]
    if plaetze:
        print(f"NDCG@10 der Suche: {_mittel_ndcg(plaetze):.3f}  ({len(plaetze)} Faelle)")


def _vergleich(faelle: list[dict]) -> None:
    """Dieselben Faelle einmal je Suchweg, damit man sieht, welcher Weg traegt.

    Gemessen wird NUR der Platz in der Suche, nicht der Weg in den Prompt: die
    Verteilung des Budgets haengt nicht am Suchweg, und ein dreifacher Abruf des
    vollen Kontexts waere teuer ohne etwas dazu zu sagen.

    Der Anlass. Beim Vorbild dieser Messung hat das Zusammenlegen beider Wege die
    reine Vektorsuche VERSCHLECHTERT, weil der Stichwortweg auf jenen Daten schwach
    war. Ob unsere Seltenheitsgewichtung traegt oder bremst, sagt erst diese Tabelle.
    """
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


# ── Was dieser Satz NICHT misst ──────────────────────────────────────────────
#
# Die FIT-ABKUERZUNG in ``chat()``: passen alle aktiven Quellen zusammen ins Budget,
# wird gar nicht abgerufen, sondern der ganze Bestand geschickt. Dieser Satz ruft
# ``_retrieve_specific_context`` direkt und laeuft deshalb immer den Abrufweg. Wer die
# Abkuerzung pruefen will, nimmt ``rag_answer_eval.py``, der geht ueber die echte API.
#
# Am 16.08.2026 einmal durchgespielt: das Budget von 250.000 auf 320.000 Zeichen
# gesetzt, damit der Kurs WuK (302.831 Zeichen) vollstaendig hineinpasst. Hier aenderte
# sich NICHTS (15/15 vorher wie nachher), weil die Abkuerzung gar nicht erreicht wird.
# Am Antwort-Messsatz dagegen fiel das Ergebnis von 8/9 auf 6/9: die Ueberblicksantwort
# liess eine von 13 Aufzeichnungen aus, und die Fragestunden-Antwort verlor ihren Bezug
# zu den affinen Chiffren. Mehr Kontext war messbar SCHLECHTER. Budget wieder auf
# 250.000.
