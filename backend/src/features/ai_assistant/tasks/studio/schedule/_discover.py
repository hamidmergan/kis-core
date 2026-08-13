"""Termine finden, in jeder Sprache: ohne festes Datum und ausgeschrieben.

Die Phrasenliste in _regex.py kennt nur Deutsch und Englisch. Ein Zeitplan aus einem
tuerkischen oder spanischen Dokument verlor damit genau die Zeilen, die kein Datum
tragen ("tarih daha sonra duyurulacak"). Hier liest das Modell die Textbloecke selbst
und gibt die Stelle woertlich zurueck, es braucht dafuer keine Wortliste.

Dasselbe Loch gab es eine Ebene tiefer beim Datum selbst: Zahlformate wie 03.07.2026
sind sprachneutral, ausgeschriebene Monate standen dagegen als feste Liste im Code, auch
nur Deutsch und Englisch. "3 Temmuz 2026" fand niemand. Deshalb liest das Modell in
DERSELBEN Anfrage beides: offene Termine und ausgeschriebene Daten. Das kostet keine
zusaetzliche Anfrage.

Woertlich ist die Bedingung. Die zurueckgegebene Stelle wird im Block wiedergesucht,
was sich dort nicht findet, hat sich das Modell ausgedacht und faellt raus. Damit
zeigt auch ein Fund des Modells auf eine echte Stelle im Text, genau wie ein
Regex-Treffer, und die Ansicht kann ihn im Dokument markieren.

Beim Datum kommt eine zweite Pruefung dazu: das Modell nennt es zusaetzlich in Ziffern,
und zwar nur so genau, wie es dasteht. Ein Monat ohne Tag bleibt ein Monat ohne Tag,
erfunden wird nichts.
"""

import json
import re
import time as _time
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import AIA_SCHEDULE_TBD_DISCOVER_PROMPT


# Ein Block ist ein Chunk, der Chunker schneidet bei 1000 Zeichen. 24000 Zeichen je
# Anfrage liegen in derselben Groessenordnung wie die Klassifikation, die 30 Kandidaten
# mit je +/-450 Zeichen Umfeld schickt.
_MAX_CHARS_PER_CALL = 24000
_MAX_BLOCKS_PER_CALL = 30
# Ein einzelner Block, der aus der Reihe faellt, darf die Anfrage nicht sprengen.
_MAX_BLOCK_CHARS = 4000
# Notbremse fuer sehr lange Quellen. Ein 90-Minuten-Transkript hat rund 100k Zeichen und
# braucht damit rund 5 Anfragen. Was ueber der Grenze liegt, wird nicht mehr durchsucht.
_MAX_CALLS_PER_SOURCE = 12
# Gleiche Werte wie in _classify: 120s sind fuer langsame Anbieter zu knapp.
_TIMEOUT_SECS = 180
_RETRY_WAIT_SECS = 5
# Kuerzere Bloecke koennen keine Ankuendigung tragen. Das spart die Kopfzeilen-Schnipsel
# aus dem Ingest ("Folie 3", "Seite 4"), die rund ein Drittel aller Chunks ausmachen.
# Bewusst niedrig: "Tutorias: fecha a convenir" ist schon eine gueltige Ankuendigung.
_MIN_BLOCK_CHARS = 15
# Das Modell soll die Stelle nennen, nicht den halben Block zurueckgeben.
_MAX_PHRASE_CHARS = 120
# Mehr ausgeschriebene Daten hat kein Chunk, alles darueber ist Ausufern.
_MAX_DATES_PER_BLOCK = 6

# Die drei Genauigkeiten, in denen ein ausgeschriebenes Datum zurueckkommen darf.
_DATE_FULL = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DATE_DAY_MONTH = re.compile(r"^(\d{2})-(\d{2})$")


def _parse_model_date(value: str) -> dict | None:
    """Die Ziffernform des Modells in unsere Kandidatenfelder uebersetzen.

    Drei Formen, mehr nicht: ganzes Datum, Monat mit Jahr, Tag mit Monat ohne Jahr.
    Alles andere ist ein Missverstaendnis und faellt raus. Ein Monat ohne Tag bekommt
    den Monatsersten als Sortierpunkt und die Genauigkeit "month", damit die Ansicht
    keine Tagesnummer zeigt, die im Dokument nie stand.
    """
    value = (value or "").strip()

    m = _DATE_FULL.match(value)
    if m:
        jahr, monat, tag = int(m[1]), int(m[2]), int(m[3])
        try:
            date(jahr, monat, tag)
        except ValueError:
            return None
        return {"date_iso": f"{jahr:04d}-{monat:02d}-{tag:02d}",
                "partial_date": None, "date_precision": "day"}

    m = _DATE_MONTH.match(value)
    if m:
        jahr, monat = int(m[1]), int(m[2])
        if not 1 <= monat <= 12:
            return None
        return {"date_iso": f"{jahr:04d}-{monat:02d}-01",
                "partial_date": None, "date_precision": "month"}

    m = _DATE_DAY_MONTH.match(value)
    if m:
        monat, tag = int(m[1]), int(m[2])
        if not (1 <= monat <= 12 and 1 <= tag <= 31):
            return None
        return {"date_iso": None, "partial_date": [monat, tag], "date_precision": "day"}

    return None


def _locate(content: str, phrase: str) -> tuple[int, int] | None:
    """Die genannte Stelle im Blocktext wiederfinden.

    Erst woertlich, dann ohne Ruecksicht auf Gross- und Kleinschreibung, zuletzt mit
    beliebigem Abstand zwischen den Woertern. Im Chunk steht oft ein Zeilenumbruch, wo
    das Modell ein Leerzeichen geschrieben hat. Findet sich nichts davon, gibt es die
    Stelle nicht und der Fund wird verworfen.
    """
    phrase = (phrase or "").strip()
    if not phrase or len(phrase) > _MAX_PHRASE_CHARS:
        return None
    pos = content.find(phrase)
    if pos != -1:
        return pos, pos + len(phrase)
    pos = content.lower().find(phrase.lower())
    if pos != -1:
        return pos, pos + len(phrase)
    tokens = [re.escape(t) for t in phrase.split()]
    if not tokens:
        return None
    m = re.search(r"\s+".join(tokens), content, re.IGNORECASE)
    if m:
        return m.start(), m.end()
    return None


def _batches(blocks: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Bloecke zu Anfragen buendeln, begrenzt durch Zeichenzahl und Anzahl."""
    out: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    chars = 0
    for bid, text in blocks:
        if current and (len(current) >= _MAX_BLOCKS_PER_CALL
                        or chars + len(text) > _MAX_CHARS_PER_CALL):
            out.append(current)
            current = []
            chars = 0
        current.append((bid, text))
        chars += len(text)
    if current:
        out.append(current)
    return out


def _discover_batch(client, model, batch: list[tuple[int, str]]) -> dict[int, dict]:
    """Eine Anfrage, zwei Ausbeuten je Block: die offene Stelle und die Datumsfunde."""
    payload = [{"id": bid, "text": text} for bid, text in batch]
    user_msg = (
        "Two jobs on the blocks below.\n"
        '"results": places where a real event has no fixed date yet, at most one per '
        "block.\n"
        '"dates": dates written out in words, in any language, with their digit form. '
        "Numeric dates are handled elsewhere, skip them.\n"
        "Blocks with nothing to report are left out of an array, both arrays may be "
        "empty.\n\n"
        "Blocks:\n" + json.dumps(payload, ensure_ascii=False)
    )
    response = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AIA_SCHEDULE_TBD_DISCOVER_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=_TIMEOUT_SECS,
            )
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                raise
            if "timeout" in err_str.lower() and attempt == 0:
                logger.warning("Terminsuche: Zeitueberschreitung, ein Versuch in {}s",
                               _RETRY_WAIT_SECS)
                _time.sleep(_RETRY_WAIT_SECS)
                continue
            raise

    raw = _clean_llm_json((response.choices[0].message.content or "").strip())
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Terminsuche lieferte kein JSON-Objekt")
    results = parsed.get("results")
    dates = parsed.get("dates")
    if not isinstance(results, list) and not isinstance(dates, list):
        raise ValueError("Terminsuche lieferte weder 'results' noch 'dates'")

    valid_ids = {bid for bid, _ in batch}
    found: dict[int, dict] = {bid: {"tbd": None, "dates": []} for bid, _ in batch}

    for r in results if isinstance(results, list) else []:
        if not isinstance(r, dict):
            continue
        bid = r.get("id")
        phrase = r.get("phrase") if isinstance(r.get("phrase"), str) else ""
        phrase = (phrase or "").strip()
        if bid not in valid_ids or not phrase or found[bid]["tbd"]:
            continue
        found[bid]["tbd"] = phrase

    for r in dates if isinstance(dates, list) else []:
        if not isinstance(r, dict):
            continue
        bid = r.get("id")
        phrase = r.get("phrase") if isinstance(r.get("phrase"), str) else ""
        phrase = (phrase or "").strip()
        wert = r.get("date") if isinstance(r.get("date"), str) else ""
        if bid not in valid_ids or not phrase:
            continue
        if len(found[bid]["dates"]) >= _MAX_DATES_PER_BLOCK:
            continue
        felder = _parse_model_date(wert)
        if felder is None:
            logger.info("Terminsuche: unbrauchbare Ziffernform {!r} zu {!r}", wert, phrase)
            continue
        found[bid]["dates"].append({"phrase": phrase, **felder})

    return found


def _discover_in_blocks(client, model, blocks: list[tuple[int, str]]) -> dict[int, dict]:
    """Bloecke durchsuchen lassen.

    Gibt je Block {"tbd": woertliche Stelle oder None, "dates": [Datumsfunde]} zurueck.
    Bloecke ohne Fund fehlen im Ergebnis.

    Ein Fehler bleibt folgenlos fuer den Rest des Auftrags, der Zeitplan entsteht auch
    ohne diese Suche. Beim ersten Fehlschlag wird abgebrochen statt weiter angefragt,
    das Anfragebudget ist hochschulweit geteilt.
    """
    if client is None:
        return {}
    usable: list[tuple[int, str]] = []
    truncated = 0
    for bid, text in blocks:
        if len(text.strip()) < _MIN_BLOCK_CHARS:
            continue
        if len(text) > _MAX_BLOCK_CHARS:
            truncated += 1
        usable.append((bid, text[:_MAX_BLOCK_CHARS]))
    if truncated:
        logger.warning("Terminsuche: {} Bloecke auf {} Zeichen gekuerzt",
                       truncated, _MAX_BLOCK_CHARS)
    if not usable:
        return {}

    batches = _batches(usable)
    if len(batches) > _MAX_CALLS_PER_SOURCE:
        skipped = sum(len(b) for b in batches[_MAX_CALLS_PER_SOURCE:])
        logger.warning(
            "Terminsuche: Quelle zu lang, {} von {} Bloecken werden nicht durchsucht",
            skipped, len(usable),
        )
        batches = batches[:_MAX_CALLS_PER_SOURCE]

    found: dict[int, dict] = {}
    for i, batch in enumerate(batches):
        try:
            found.update(_discover_batch(client, model, batch))
        except Exception as e:  # noqa: BLE001 - der Zeitplan entsteht auch ohne diese Suche
            logger.warning(
                "Terminsuche: Anfrage {}/{} fehlgeschlagen, Rest wird uebersprungen: {}",
                i + 1, len(batches), e,
            )
            break
    offene = sum(1 for v in found.values() if v["tbd"])
    daten = sum(len(v["dates"]) for v in found.values())
    logger.info("Terminsuche: {} Bloecke in {} Anfragen, {} offene Stellen, {} Daten",
                len(usable), len(batches), offene, daten)
    return found
