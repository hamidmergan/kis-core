"""Source-text scanner: builds date/TBD candidates from a source's chunks."""

from loguru import logger

from src import database as db

from src.features.ai_assistant.tasks.studio.schedule._regex import (
    _MULTI_YEAR_SHORTHAND,
    _TBD_PATTERNS,
    _date_candidates_in_text,
    _date_in_neighbouring_column,
)
from src.features.ai_assistant.tasks.studio.schedule._discover import (
    _discover_in_blocks,
    _locate,
)
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _normalize_date,
    _normalize_month_date,
    _normalize_partial_date,
)


def _load_source_chunks(source_id: int) -> list[dict]:
    """Return ordered chunks with their positions (page or timestamp)."""
    chunks = db.get_aia_chunks_by_source(source_id)
    if not chunks:
        return []
    return sorted(
        chunks,
        key=lambda c: (c.get("start_time") or 0, c.get("page_number") or 0, c.get("id", 0)),
    )


def _model_finds_by_chunk(chunks: list[dict], client, model):
    """Was das Modell in den Chunks findet: offene Termine und ausgeschriebene Daten.

    Rueckgabe: (offene_stellen, daten_je_chunk).
      offene_stellen: {Chunk-Nummer: (start, ende, Wortlaut)}, hoechstens eine je Chunk.
      daten_je_chunk: {Chunk-Nummer: [{span, date_iso, partial_date, date_precision}]}.

    Bei den offenen Terminen kommt zuerst die Phrasenliste aus _regex zum Zug. Sie kostet
    nichts und deckt Deutsch und Englisch ab, ihr Treffer schlaegt den des Modells. Die
    Daten dagegen braucht jeder Chunk, deshalb gehen hier ALLE Chunks in die Anfrage und
    nicht nur die ohne Phrasentreffer. Ohne Modell (client=None) bleibt beides beim
    Regex-Weg.

    Als Fundstelle zaehlt immer der Text aus dem Chunk, nie die Antwort des Modells. Was
    sich im Chunk nicht wiederfindet, faellt raus.

    Eine offene Stelle, deren Zeile ihr Datum in der Nachbarspalte traegt, zaehlt nicht.
    Ein verworfener Treffer blockiert den Chunk nicht, dieselbe Tabelle kann eine Zeile
    weiter einen echten offenen Termin haben.
    """
    spans: dict[int, tuple[int, int, str]] = {}
    daten: dict[int, list[dict]] = {}
    blocks: list[tuple[int, str]] = []

    for i, c in enumerate(chunks):
        content = c.get("content") or ""
        if not content:
            continue
        blocks.append((i, content))
        hit = None
        for pat in _TBD_PATTERNS:
            for m in pat.finditer(content):
                if _date_in_neighbouring_column(content, m.start(), m.end()):
                    continue
                hit = (m.start(), m.end(), m.group("phrase"))
                break
            if hit:
                break
        if hit:
            spans[i] = hit

    for i, antwort in _discover_in_blocks(client, model, blocks).items():
        content = chunks[i].get("content") or ""

        phrase = antwort.get("tbd")
        if phrase and i not in spans:
            found = _locate(content, phrase)
            if found is None:
                logger.info("Terminsuche: Stelle nicht im Text, verworfen: {!r}", phrase)
            elif _date_in_neighbouring_column(content, *found):
                logger.info("Terminsuche: Datum in der Nachbarspalte, verworfen: {!r}", phrase)
            else:
                spans[i] = (found[0], found[1], content[found[0]:found[1]])

        for d in antwort.get("dates") or []:
            found = _locate(content, d["phrase"])
            if found is None:
                logger.info("Terminsuche: Datum nicht im Text, verworfen: {!r}", d["phrase"])
                continue
            daten.setdefault(i, []).append({
                "span": found,
                "date_iso": d["date_iso"],
                "partial_date": d["partial_date"],
                "date_precision": d["date_precision"],
            })

    return spans, daten


def _build_candidates_for_source(src: dict, client=None, model=None) -> list[dict]:
    """Find all date candidates in a source. Year-full matches produce date_iso;
    year-less matches produce partial_date=(month, day), resolved to current year.
    'To-be-arranged'-style phrases produce is_tbd=True with no date.

    date_precision sagt, wie genau das Datum im Dokument steht: "day" ist der Normalfall,
    "month" heisst, dass dort nur ein Monat genannt war ("im Juli 2026"). Dann traegt
    date_iso den Monatsersten als Sortierpunkt und die Ansicht zeigt keine Tagesnummer.
    """
    candidates: list[dict] = []
    chunks = _load_source_chunks(src["id"])
    tbd_spans, modell_daten = _model_finds_by_chunk(chunks, client, model)
    for chunk_idx, c in enumerate(chunks):
        content = c.get("content") or ""
        if not content:
            continue
        page = c.get("page_number")
        st = c.get("start_time")

        # German shorthand "DD.MM.YYYY/YYYY/..." -> one candidate per year.
        # Tracked so the standard scanner below skips matches inside these spans.
        # Hard cap to keep adversarial input from generating a flood of candidates.
        _MAX_SHORTHAND_YEARS = 20
        shorthand_spans: list[tuple[int, int]] = []
        for m in _MULTI_YEAR_SHORTHAND.finditer(content):
            dm = m.group("dm")
            years = [y.strip() for y in m.group("years").split("/")][:_MAX_SHORTHAND_YEARS]
            shorthand_spans.append((m.start(), m.end()))
            ctx_start = max(0, m.start() - 450)
            ctx_end = min(len(content), m.end() + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            nl_pos = content.find("\n", m.end())
            hl_end = min(len(content), m.start() + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[m.start():hl_end].replace("\n", " ").strip()
            for y in years:
                raw = f"{dm}{y}"
                norm = _normalize_date(raw)
                if not norm:
                    continue
                candidates.append({
                    "date_raw": raw,
                    "date_iso": norm,
                    "partial_date": None,
                    "date_precision": "day",
                    "is_tbd": False,
                    "context": ctx,
                    "raw_quote": quote,
                    "page_number": page,
                    "start_time": st,
                    "source_uuid": src["uuid"],
                    "source_filename": src.get("filename") or "",
                })

        # Date-based candidates. Die Spannen werden mitgeschrieben, damit ein Fund des
        # Modells an derselben Stelle nicht ein zweites Mal denselben Termin erzeugt.
        date_spans: list[tuple[int, int]] = list(shorthand_spans)
        for s, e, raw_date, has_year, precision in _date_candidates_in_text(content):
            if any(cs <= s < ce for cs, ce in shorthand_spans):
                continue
            date_spans.append((s, e))
            if precision == "month":
                norm = _normalize_month_date(raw_date)
                if not norm:
                    continue
                partial = None
                date_iso = norm
            elif has_year:
                norm = _normalize_date(raw_date)
                if not norm:
                    continue
                partial = None
                date_iso = norm
            else:
                partial = _normalize_partial_date(raw_date)
                if partial is None:
                    continue
                date_iso = None
            # +/-450 chars so table headers with time (e.g. "17:30") at the top of a
            # schedule listing are visible to the classifier for every row below.
            ctx_start = max(0, s - 450)
            ctx_end = min(len(content), e + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            # Short snippet for the frontend highlight search. Start AT the date
            # (no chars before) so the PDF-viewer match lands on the date and
            # doesn't bleed into the preceding bullet. Stop at the next newline
            # to catch exactly one bullet/line; cap at 200 chars for safety.
            nl_pos = content.find("\n", e)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": raw_date,
                "date_iso": date_iso,
                "partial_date": partial,
                "date_precision": precision,
                "is_tbd": False,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st,
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })

        # Ausgeschriebene Daten aus dem Modell ("3 Temmuz 2026", "im Juli 2026"). Der
        # Regex kennt nur Zahlformate und deutsche/englische Monatsnamen, deshalb kommt
        # hier alles dazu, was er nicht lesen konnte. Was er gelesen hat, steht schon
        # oben, deshalb faellt jede Stelle raus, die sich mit einem Regex-Fund ueberlappt.
        for treffer in modell_daten.get(chunk_idx) or []:
            s, e = treffer["span"]
            if any(s < ce and cs < e for cs, ce in date_spans):
                continue
            date_spans.append((s, e))
            ctx_start = max(0, s - 450)
            ctx_end = min(len(content), e + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            nl_pos = content.find("\n", e)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": content[s:e],
                "date_iso": treffer["date_iso"],
                "partial_date": treffer["partial_date"],
                "date_precision": treffer["date_precision"],
                "is_tbd": False,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st,
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })

        # TBD candidates ("nach Vereinbarung" etc.): no date, but a real event
        # whose scheduling is still open. One TBD candidate per chunk, even if the
        # chunk names several. Found by phrase list or, in any other language, by
        # the model (_model_finds_by_chunk).
        span = tbd_spans.get(chunk_idx)
        if span:
            s, e, phrase = span
            ctx_start = max(0, s - 300)
            ctx_end = min(len(content), e + 300)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            # Start AT the TBD phrase; stop at next newline (bullet end).
            nl_pos = content.find("\n", e)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": phrase,
                "date_iso": None,
                "partial_date": None,
                "date_precision": "day",
                "is_tbd": True,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st,
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })
    return candidates
