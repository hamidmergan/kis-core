"""Re-chunks a source without deleting and re-uploading it."""
import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import os

import psycopg2.extras

from src import database as db
from src.core.db.pool import get_connection
from src.limits import AIA_EMBEDDING_BATCH_SIZE
from src.services import aia_chunker
from src.storage import open_input_file


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _fragmentanteil(cur, workspace_id: int, source_id: int) -> tuple[int, int]:
    """How many chunks of this source start with a fragment."""
    cur.execute(
        """WITH erst AS (
             SELECT c.id, lower(substring(c.content from '^[^ ]+')) AS w
               FROM aia_chunks c WHERE c.source_id = %s)
           SELECT count(*) FILTER (WHERE e.w ~ '^[a-zäöüß]{5,}$'),
                  count(*) FILTER (WHERE e.w ~ '^[a-zäöüß]{5,}$' AND (
                      SELECT count(*) FROM aia_chunks c2
                        JOIN aia_sources s2 ON s2.id = c2.source_id
                       WHERE s2.workspace_id = %s
                         AND c2.search_vector @@ plainto_tsquery('simple', e.w)) = 1)
             FROM erst e""",
        (source_id, workspace_id),
    )
    row = cur.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def _sources(workspace_uuid: str) -> tuple[int, list[dict]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM aia_workspaces WHERE uuid = %s", (workspace_uuid,))
            row = cur.fetchone()
            if row is None:
                raise SystemExit(f"Workspace {workspace_uuid!r} nicht gefunden")
            ws_id = row["id"]
            cur.execute(
                """SELECT id, uuid, filename, file_path, file_type, chunk_count
                     FROM aia_sources
                    WHERE workspace_id = %s AND status = 'ready'
                    ORDER BY filename""",
                (ws_id,),
            )
            return ws_id, [dict(r) for r in cur.fetchall()]


def _neu_zerlegen(src: dict) -> list[dict]:
    """Chunk the same text again, with the repaired version."""
    suffix = os.path.splitext(src["filename"])[1] or f".{src['file_type']}"
    with open_input_file(src["file_path"], suffix=suffix) as local_path:
        return aia_chunker.extract_chunks(local_path, src["file_type"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="Workspace-UUID")
    ap.add_argument("--probe", action="store_true",
                    help="Nur zerlegen und vergleichen, nichts schreiben")
    ap.add_argument("--limit", type=int, help="Nur die ersten N Quellen")
    args = ap.parse_args()

    ws_id, quellen = _sources(args.workspace)
    if args.limit:
        quellen = quellen[: args.limit]
    medien = [s for s in quellen if aia_chunker.is_media_file(s["file_type"])]
    dokumente = [s for s in quellen if not aia_chunker.is_media_file(s["file_type"])]
    if medien:
        print(f"{len(medien)} Medienquellen uebersprungen (segments_to_chunks schneidet "
              f"nie in ein Wort, ein Neu-Zerlegen hiesse neu transkribieren)")

    from src.services.aia_embeddings import get_embedding_provider
    provider = get_embedding_provider() if not args.probe else None

    ges_alt = ges_neu = ges_frag_vor = 0
    for src in dokumente:
        try:
            neu = _neu_zerlegen(src)
        except Exception as e:                                  # noqa: BLE001
            print(f"  {src['filename']:22s} FEHLER beim Zerlegen: {e}")
            continue
        if not neu:
            print(f"  {src['filename']:22s} uebersprungen: Zerlegen ergab nichts, "
                  f"die alten Chunks bleiben stehen")
            continue

        with get_connection() as conn:
            with conn.cursor() as cur:
                _gepr, frag_vor = _fragmentanteil(cur, ws_id, src["id"])
        ges_alt += src["chunk_count"]
        ges_neu += len(neu)
        ges_frag_vor += frag_vor
        marke = "PROBE" if args.probe else "neu"
        # The after value needs the same set as reference and therefore comes later.
        print(f"  {src['filename']:22s} {src['chunk_count']:5d} -> {len(neu):5d} Chunks | "
              f"Bruchstuecke vorher {frag_vor:4d} | {marke}")

        if args.probe:
            continue

        # Chunk first, delete after, so a failure leaves the old chunks in place.
        db.delete_aia_chunks_by_source(src["id"])
        ids = [db.create_aia_chunk(source_id=src["id"], page_number=c["page_number"],
                                   content=c["content"], start_time=c.get("start_time"),
                                   end_time=c.get("end_time")) for c in neu]
        for i in range(0, len(neu), AIA_EMBEDDING_BATCH_SIZE):
            teil = neu[i: i + AIA_EMBEDDING_BATCH_SIZE]
            vektoren = provider.embed([c["content"] for c in teil])
            for cid, v in zip(ids[i: i + AIA_EMBEDDING_BATCH_SIZE], vektoren):
                db.update_chunk_embedding(cid, v)
        db.update_aia_source_status(src["uuid"], "ready", chunk_count=len(neu))

    print(f"\n{len(dokumente)} Dokumente | Chunks {ges_alt} -> {ges_neu} | "
          f"Bruchstuecke vorher {ges_frag_vor}"
          + ("  (Probe, nichts geschrieben)" if args.probe else ""))
    if not args.probe:
        with get_connection() as conn:
            with conn.cursor() as cur:
                nach = sum(_fragmentanteil(cur, ws_id, s2["id"])[1] for s2 in dokumente)
        print(f"Bruchstuecke nach dem Neu-Zerlegen: {nach}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
