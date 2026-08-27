"""Builds a broad retrieval benchmark from a real workspace."""
import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_MIN_ZEICHEN = 200          # kuerzere Chunks tragen keine eigenstaendige Frage
_MIN_WOERTER = 25
_MAX_FRAGE_ZEICHEN = 200    # laenger ist keine Nutzerfrage mehr
_BELEG_LAENGE = 60          # kurz genug, um keine Chunk-Grenze zu kreuzen
_ETIKETT = re.compile(r"^\s*(frage|question|q|antwort|answer)\s*[:\-]\s*", re.I)

PROMPT = """Du bist eine Person, die eine Frage an eine Sammlung von Dokumenten stellt.
Der folgende Auszug enthaelt die Antwort auf deine Frage.

Schreibe GENAU EINE realistische Frage, so wie eine Person sie stellen wuerde.

Regeln:
- Die Frage muss sich allein aus dem Auszug beantworten lassen.
- Schreibe in derselben Sprache wie der Auszug.
- Benutze eigene Worte. Formuliere NICHT den ersten Satz des Auszugs um.
- Uebernimm keine langen Wortfolgen woertlich aus dem Auszug.
- Hoechstens 20 Woerter.
- Antworte nur mit der Frage, ohne Einleitung und ohne Anfuehrungszeichen.

Auszug:
{auszug}

Frage:"""


def _taugt_als_quelle(text: str | None) -> bool:
    """Does this chunk carry an answerable question at all?"""
    t = " ".join((text or "").split())
    if len(t) < _MIN_ZEICHEN:
        return False
    woerter = [w for w in t.split(" ") if len(re.sub(r"[^\w]", "", w, flags=re.UNICODE)) >= 3]
    return len(woerter) >= _MIN_WOERTER


def _beleg(text: str | None, laenge: int = _BELEG_LAENGE) -> str | None:
    """A short, verbatim findable excerpt as the anchor of the case."""
    t = " ".join((text or "").split())
    if len(t) < laenge + 40:
        return None
    # Start after the first fifth, at the next word boundary.
    start = t.find(" ", len(t) // 5)
    if start == -1:
        return None
    schnitt = t[start + 1:start + 1 + laenge]
    if " " in schnitt:
        schnitt = schnitt.rsplit(" ", 1)[0]
    schnitt = schnitt.strip()
    return schnitt or None


def _frage_saeubern(roh: str | None) -> str | None:
    """Whatever is left of the model's answer as a question, or None."""
    t = (roh or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    t = t.splitlines()[0].strip() if t else ""
    t = _ETIKETT.sub("", t)
    t = t.strip().strip('"').strip("'").strip("„").strip("“").strip("»").strip("«").strip()
    if not t or len(t) > _MAX_FRAGE_ZEICHEN or "?" not in t:
        return None
    return t


# ── Everything below needs the database and the model ─────────────────────────

def _lade_kandidaten(ws_uuid: str, anzahl: int, seed: int) -> tuple[int, list[dict]]:
    """Random but repeatable pick of usable chunks."""
    import psycopg2.extras
    from src.core.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM aia_workspaces WHERE uuid = %s", (ws_uuid,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Workspace {ws_uuid!r} nicht gefunden")
            ws_id = row["id"]
            cur.execute(
                """SELECT c.id, c.content, s.filename
                     FROM aia_chunks c
                     JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.workspace_id = %s AND s.status = 'ready'
                    ORDER BY c.id""",
                (ws_id,),
            )
            alle = [dict(r) for r in cur.fetchall()]

    brauchbar = [c for c in alle if _taugt_als_quelle(c["content"])]
    print(f"{len(alle)} Chunks, davon {len(brauchbar)} brauchbar "
          f"({100 * len(brauchbar) // max(len(alle), 1)}%)", file=sys.stderr)
    random.Random(seed).shuffle(brauchbar)
    return ws_id, brauchbar[:anzahl * 3]      # Vorrat, weil unten noch aussortiert wird


def _beleg_ist_eindeutig(ws_id: int, beleg: str) -> bool:
    """Does the evidence occur exactly once in the workspace?"""
    import psycopg2.extras
    from src.core.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT count(*) AS n FROM aia_chunks c
                     JOIN aia_sources s ON s.id = c.source_id
                    WHERE s.workspace_id = %s
                      AND regexp_replace(c.content, '\\s+', ' ', 'g') ILIKE %s""",
                (ws_id, f"%{beleg}%"),
            )
            return int(cur.fetchone()["n"]) == 1


def _frage_erzeugen(client, model, auszug: str) -> str | None:
    antwort = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(auszug=auszug)}],
        temperature=0.3,
        max_tokens=120,
    )
    return _frage_saeubern(antwort.choices[0].message.content)


def _pruefe_schreibbar(pfad) -> None:
    """Checks before the first model call whether the result can be stored."""
    pfad = Path(pfad)
    gab_es_schon = pfad.exists()
    try:
        with pfad.open("a", encoding="utf-8"):
            pass
        if not gab_es_schon:
            pfad.unlink()
    except OSError as e:
        raise SystemExit(f"Ergebnis waere nicht ablegbar: {pfad} ({e})\n"
                         "Im Container ist scripts/ nur lesbar. Mit --out auf einen "
                         "schreibbaren Pfad zeigen, etwa --out /tmp/faelle.json.")


def _bauen(args) -> int:
    from src.features.ai_assistant.tasks._helpers import _get_llm_client

    _pruefe_schreibbar(args.out)
    ws_id, kandidaten = _lade_kandidaten(args.workspace, args.anzahl, args.seed)
    client, model, provider = _get_llm_client()
    print(f"Modell: {model} ({provider})", file=sys.stderr)

    faelle: list[dict] = []
    verworfen = {"beleg": 0, "mehrdeutig": 0, "frage": 0, "fehler": 0}

    for chunk in kandidaten:
        if len(faelle) >= args.anzahl:
            break
        beleg = _beleg(chunk["content"])
        if not beleg:
            verworfen["beleg"] += 1
            continue
        if not _beleg_ist_eindeutig(ws_id, beleg):
            verworfen["mehrdeutig"] += 1
            continue
        try:
            frage = _frage_erzeugen(client, model, " ".join(chunk["content"].split()))
        except Exception as e:                      # noqa: BLE001
            print(f"  Modellfehler bei Chunk {chunk['id']}: {e}", file=sys.stderr)
            verworfen["fehler"] += 1
            time.sleep(args.pause * 4)
            continue
        if not frage:
            verworfen["frage"] += 1
            continue

        faelle.append({
            "id": f"auto-{len(faelle) + 1:03d}",
            "workspace": args.workspace,
            "question": frage,
            "note": f"maschinell erzeugt aus {chunk['filename']}, Chunk {chunk['id']}",
            "expect_text": [beleg],
        })
        print(f"  {len(faelle):3d}/{args.anzahl}  {frage}", file=sys.stderr)
        # One after another with a pause, the rate limit applies campus wide.
        time.sleep(args.pause)

    Path(args.out).write_text(
        json.dumps(faelle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{len(faelle)} Faelle nach {args.out}", file=sys.stderr)
    print(f"verworfen: {verworfen}", file=sys.stderr)
    print("\nJetzt einmal durchsehen:  "
          f"python scripts/build_retrieval_cases.py --pruefen --out {args.out}", file=sys.stderr)
    return 0


def _pruefen(args) -> int:
    """Print the generated questions for review before they count as a benchmark."""
    faelle = json.loads(Path(args.out).read_text(encoding="utf-8"))
    for f in faelle:
        print(f"\n{f['id']}  ({f['note']})")
        print(f"  Frage: {f['question']}")
        print(f"  Beleg: {f['expect_text'][0]}")
    print(f"\n{len(faelle)} Faelle. Was nach Umformulierung des Belegs aussieht, "
          "von Hand loeschen.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", help="UUID des Workspace, aus dem gezogen wird")
    ap.add_argument("--anzahl", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42, help="gleiche Auswahl bei gleichem Wert")
    ap.add_argument("--pause", type=float, default=0.5, help="Sekunden zwischen Modellaufrufen")
    ap.add_argument("--out", default=str(Path(__file__).parent / "rag_retrieval_cases_auto.json"))
    ap.add_argument("--pruefen", action="store_true", help="Erzeugte Faelle nur anzeigen")
    args = ap.parse_args()

    if args.pruefen:
        return _pruefen(args)
    if not args.workspace:
        ap.error("--workspace wird zum Bauen gebraucht")
    return _bauen(args)


if __name__ == "__main__":
    sys.exit(main())
