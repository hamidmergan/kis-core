"""Baut einen breiten Messsatz fuer den Abruf aus einem echten Workspace.

Aufruf aus backend/:
    python scripts/build_retrieval_cases.py --workspace <uuid> --anzahl 100
    python scripts/build_retrieval_cases.py --workspace <uuid> --pruefen

Warum es das gibt. ``rag_retrieval_cases.json`` enthaelt 19 von Hand geschriebene
Faelle, und jeder einzelne entstand, NACHDEM etwas kaputt war. Der Satz bewacht
also die bekannten Schwachstellen, sagt aber nichts ueber den Normalfall. Gemessen
am 18.08.2026 liegt er bei NDCG@10 = 0.910, also fast an der Decke: eine
Verbesserung liesse sich daran kaum noch ablesen, nur noch ein Rueckschritt.

Dieser Bauer erzeugt den Gegensatz dazu: viele Faelle auf Material, das keiner
vorher angesehen hat. Das Verfahren ist bekannt und einfach. Man nimmt einen
Chunk, laesst ein Modell die Frage schreiben, die dieser Chunk beantwortet, und
haelt fest welcher Chunk das war. Damit hat man Frage, Beleg und Zuordnung, also
genau die drei Teile, die eine Abruf-Messung braucht.

Die bekannte Falle dabei: das Modell formuliert gern den ersten Satz des Chunks
um. Solche Fragen misst man dann als Wortgleichheit und nicht als Abruf, und die
Stichwortsuche sieht dadurch besser aus als sie ist. Dagegen steht die Anweisung
im Prompt, und dagegen steht die Sichtpruefung (--pruefen), die man vor dem
ersten Messlauf machen sollte.

Die Ausgabe hat dasselbe Format wie die Handfaelle und wird von
``rag_retrieval_eval.py --faelle`` gelesen. Bewusst eine EIGENE Datei: die 19
gewachsenen Faelle sollen nicht zwischen hundert erzeugten untergehen.
"""
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
    """Traegt dieser Chunk ueberhaupt eine beantwortbare Frage?

    Rund ein Drittel der Chunks im Bestand sind Kopfzeilen, Paragrafenkoepfe und
    Inhaltsverzeichnisse. Eine Frage dazu waere unbeantwortbar, der Fall damit
    stiller Unsinn, der die Messzahl nach unten zieht ohne etwas zu zeigen."""
    t = " ".join((text or "").split())
    if len(t) < _MIN_ZEICHEN:
        return False
    woerter = [w for w in t.split(" ") if len(re.sub(r"[^\w]", "", w, flags=re.UNICODE)) >= 3]
    return len(woerter) >= _MIN_WOERTER


def _beleg(text: str | None, laenge: int = _BELEG_LAENGE) -> str | None:
    """Ein kurzer, woertlich wiederfindbarer Ausschnitt als Anker des Falls.

    Drei Bedingungen. Er muss den Zwischenraum genauso glaetten wie die spaetere
    Suche, sonst macht ein Zeilenumbruch im PDF die Stelle unauffindbar. Er darf
    nicht am Chunk-Anfang liegen, weil dort oft der Paragrafenkopf steht, der
    wortgleich in vielen Chunks vorkommt. Und er muss auf ganzen Woertern
    beginnen und enden, sonst findet ILIKE zwar etwas, aber nichts Lesbares."""
    t = " ".join((text or "").split())
    if len(t) < laenge + 40:
        return None
    # Hinter dem ersten Fuenftel einsetzen, an der naechsten Wortgrenze.
    start = t.find(" ", len(t) // 5)
    if start == -1:
        return None
    schnitt = t[start + 1:start + 1 + laenge]
    if " " in schnitt:
        schnitt = schnitt.rsplit(" ", 1)[0]
    schnitt = schnitt.strip()
    return schnitt or None


def _frage_saeubern(roh: str | None) -> str | None:
    """Was von der Antwort des Modells als Frage uebrig bleibt, oder None.

    Modelle liefern Zierrat: Codezaeune, Anfuehrungszeichen, ein vorangestelltes
    "Frage:", manchmal noch eine Erlaeuterung in der zweiten Zeile. Und
    gelegentlich eine Aussage statt einer Frage, die als Suchanfrage untypisch
    waere und die Messung schoenen wuerde."""
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


# ── Alles darunter braucht Datenbank und Modell ───────────────────────────────

def _lade_kandidaten(ws_uuid: str, anzahl: int, seed: int) -> tuple[int, list[dict]]:
    """Zufaellige, aber wiederholbare Auswahl brauchbarer Chunks."""
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
    """Kommt der Beleg genau einmal im Workspace vor?

    Mehrdeutige Belege (Formulierungen, die in vielen Paragrafen gleich lauten)
    machen den Fall unscharf: die Messung wuesste nicht, welcher Chunk der
    richtige ist, und wuerde jeden Treffer gelten lassen."""
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
    """Vor dem ersten Modellaufruf pruefen, ob das Ergebnis spaeter ablegbar ist.

    Der Anlass: der Container haengt ``scripts/`` schreibgeschuetzt ein. Ohne
    diese Pruefung faellt das erst NACH hundert Modellaufrufen auf, und die sind
    dann verloren. Rechtebits allein reichen als Pruefung nicht, weil der
    Container als root laeuft und root sie umgeht: ein eingehaengter
    Nur-Lese-Bereich stoppt aber auch root. Deshalb wird wirklich geschrieben.

    Eine bereits vorhandene Datei bleibt unangetastet, und eine neue wird wieder
    entfernt: die Pruefung darf keine Spur hinterlassen."""
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
        # Die Ratengrenze des Anbieters gilt hochschulweit und ist der enge Punkt.
        # Deshalb der Reihe nach mit Pause, niemals nebenlaeufig.
        time.sleep(args.pause)

    Path(args.out).write_text(
        json.dumps(faelle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{len(faelle)} Faelle nach {args.out}", file=sys.stderr)
    print(f"verworfen: {verworfen}", file=sys.stderr)
    print("\nJetzt einmal durchsehen:  "
          f"python scripts/build_retrieval_cases.py --pruefen --out {args.out}", file=sys.stderr)
    return 0


def _pruefen(args) -> int:
    """Die erzeugten Fragen zum Durchsehen ausgeben, bevor sie als Massstab gelten."""
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
