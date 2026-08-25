"""Source-text scanner: builds date/TBD candidates from a source's chunks."""

from loguru import logger

from src import database as db

from src.features.ai_assistant.tasks.studio.schedule._regex import (
    _MULTI_YEAR_SHORTHAND,
    _TBD_PATTERNS,
    _date_candidates_in_text,
    _date_in_neighbouring_column,
    _looks_like_range,
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
from src.features.ai_assistant.routes._helpers import _load_transcript_segments
from src.services.aia_transcript_offsets import TranscriptIndex


def _spannen_ende(raw: str, has_year: bool, start_iso: str | None) -> dict | None:
    """Das zweite Datum einer Spanne als Ende, oder None wenn es sich nicht lesen laesst.

    Ohne eigene Jahreszahl erbt es das Jahr des Anfangs: "28.09.2026 bis 02.11." meint
    dasselbe Jahr. Faellt es damit vor den Anfang, ist der Jahreswechsel gemeint
    ("28.12.2026 bis 02.01."). Fehlt auch dem Anfang das Jahr, bleibt es beim
    Tag-Monat-Paar, beide legt der Auftrag spaeter gemeinsam auf das laufende Jahr.
    """
    if has_year:
        iso = _normalize_date(raw)
        return {"iso": iso, "partial": None} if iso else None
    teil = _normalize_partial_date(raw)
    if teil is None:
        return None
    if not start_iso:
        return {"iso": None, "partial": teil}
    jahr = int(start_iso[:4])
    iso = f"{jahr:04d}-{teil[0]:02d}-{teil[1]:02d}"
    if iso < start_iso:
        iso = f"{jahr + 1:04d}-{teil[0]:02d}-{teil[1]:02d}"
    return {"iso": iso, "partial": None}


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


def _transcript_index(src: dict, chunks: list[dict]) -> TranscriptIndex | None:
    """Die Zeitachse der Quelle, einmal je Quelle geladen.

    Nur fuer Medien: hat kein Chunk eine Startzeit, ist es ein PDF und die Ablage
    wird gar nicht angefasst. Ein fehlendes Transkript-Artefakt ist kein Fehler,
    dann bleibt es beim Chunk-Anfang wie bisher."""
    if not any(c.get("start_time") is not None for c in chunks):
        return None
    segmente = _load_transcript_segments(src)
    if not segmente:
        logger.info("Terminsuche: kein Transkript zu Quelle {}, Zeitmarken bleiben am "
                    "Chunk-Anfang", src.get("id"))
        return None
    return TranscriptIndex(segmente)


def _fundstelle_zeit(index: TranscriptIndex | None, chunk: dict,
                     offset: int) -> float | None:
    """Zeitmarke fuer eine Stelle im Chunk-Text.

    Ein Chunk umfasst ueber eine Minute gesprochene Zeit, der Chunk-Anfang zeigt
    also im schlimmsten Fall weit vor den Termin. Laesst sich die Stelle nicht
    zuordnen, bleibt der Chunk-Anfang als bekannter Rahmen."""
    st = chunk.get("start_time")
    if st is None or index is None:
        return st
    genau = index.start_at(chunk, offset)
    return genau if genau is not None else st


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
    zeitachse = _transcript_index(src, chunks)
    for chunk_idx, c in enumerate(chunks):
        content = c.get("content") or ""
        if not content:
            continue
        page = c.get("page_number")

        def st_bei(offset: int, _c=c) -> float | None:
            """Die Zeitmarke der Fundstelle, nicht die des ganzen Chunks."""
            return _fundstelle_zeit(zeitachse, _c, offset)

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
                    "start_time": st_bei(m.start()),
                    "source_uuid": src["uuid"],
                    "source_filename": src.get("filename") or "",
                })

        # Date-based candidates. Die Spannen werden mitgeschrieben, damit ein Fund des
        # Modells an derselben Stelle nicht ein zweites Mal denselben Termin erzeugt.
        date_spans: list[tuple[int, int]] = list(shorthand_spans)
        gefundene_daten = _date_candidates_in_text(content)
        # Wurde ein Datum schon als ENDE einer Spanne verbraucht, ist es kein eigener
        # Termin mehr. Genau hier entstanden bisher die Dubletten.
        als_ende_verbraucht: set[int] = set()
        for di, (s, e, raw_date, has_year, precision) in enumerate(gefundene_daten):
            if any(cs <= s < ce for cs, ce in shorthand_spans):
                continue
            if di in als_ende_verbraucht:
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

            # Steht direkt dahinter ein zweites Datum, ist das meist das Ende einer
            # Zeitspanne. Der Kandidat traegt es mit, bestaetigen muss es die
            # Klassifikation. Ein Monat ohne Tag taugt nicht als Ende, dort waere
            # unklar, ob der Erste oder der Letzte gemeint ist.
            ende_iso = ende_raw = None
            ende_partial = None
            e_bis = e
            if di + 1 < len(gefundene_daten):
                s2, e2, raw2, hy2, prec2 = gefundene_daten[di + 1]
                if prec2 == "day" and precision == "day" and _looks_like_range(content, e, s2):
                    ende = _spannen_ende(raw2, hy2, date_iso)
                    passt = ende is not None and (
                        (ende["iso"] and date_iso and ende["iso"] > date_iso)
                        or (ende["partial"] and partial and ende["partial"] > partial)
                    )
                    if passt:
                        ende_iso, ende_partial, ende_raw = ende["iso"], ende["partial"], raw2
                        als_ende_verbraucht.add(di + 1)
                        date_spans.append((s2, e2))
                        e_bis = e2

            # +/-450 chars so table headers with time (e.g. "17:30") at the top of a
            # schedule listing are visible to the classifier for every row below.
            ctx_start = max(0, s - 450)
            ctx_end = min(len(content), e_bis + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            # Short snippet for the frontend highlight search. Start AT the date
            # (no chars before) so the PDF-viewer match lands on the date and
            # doesn't bleed into the preceding bullet. Stop at the next newline
            # to catch exactly one bullet/line; cap at 200 chars for safety.
            nl_pos = content.find("\n", e_bis)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": raw_date,
                "date_iso": date_iso,
                "partial_date": partial,
                "date_precision": precision,
                "date_end_raw": ende_raw,
                "date_end_iso": ende_iso,
                "date_end_partial": ende_partial,
                "is_tbd": False,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st_bei(s),
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })

        # Ausgeschriebene Daten aus dem Modell ("3 Temmuz 2026", "im Juli 2026"). Der
        # Regex kennt nur Zahlformate und deutsche/englische Monatsnamen, deshalb kommt
        # hier alles dazu, was er nicht lesen konnte. Was er gelesen hat, steht schon
        # oben, deshalb faellt jede Stelle raus, die sich mit einem Regex-Fund ueberlappt.
        # Auch hier gilt die Spannen-Regel: "3 Temmuz 2026 kadar 17 Temmuz 2026" ist EIN
        # Termin. Sonst haetten nur deutsche und englische Quellen Zeitspannen.
        modell_treffer = sorted(modell_daten.get(chunk_idx) or [], key=lambda t: t["span"])
        modell_als_ende: set[int] = set()
        for mi, treffer in enumerate(modell_treffer):
            s, e = treffer["span"]
            if any(s < ce and cs < e for cs, ce in date_spans):
                continue
            if mi in modell_als_ende:
                continue
            date_spans.append((s, e))

            ende_iso = ende_raw = None
            ende_partial = None
            e_bis = e
            if treffer["date_precision"] == "day" and mi + 1 < len(modell_treffer):
                naechster = modell_treffer[mi + 1]
                s2, e2 = naechster["span"]
                if naechster["date_precision"] == "day" and _looks_like_range(content, e, s2):
                    kandidat = naechster["date_iso"]
                    passt = (
                        (kandidat and treffer["date_iso"] and kandidat > treffer["date_iso"])
                        or (naechster["partial_date"] and treffer["partial_date"]
                            and naechster["partial_date"] > treffer["partial_date"])
                    )
                    if passt:
                        ende_iso = kandidat
                        ende_partial = naechster["partial_date"] if not kandidat else None
                        ende_raw = content[s2:e2]
                        modell_als_ende.add(mi + 1)
                        date_spans.append((s2, e2))
                        e_bis = e2

            ctx_start = max(0, s - 450)
            ctx_end = min(len(content), e_bis + 450)
            ctx = content[ctx_start:ctx_end].replace("\n", " ").strip()
            nl_pos = content.find("\n", e_bis)
            hl_end = min(len(content), s + 200)
            if nl_pos != -1 and nl_pos < hl_end:
                hl_end = nl_pos
            quote = content[s:hl_end].replace("\n", " ").strip()
            candidates.append({
                "date_raw": content[s:e],
                "date_iso": treffer["date_iso"],
                "partial_date": treffer["partial_date"],
                "date_precision": treffer["date_precision"],
                "date_end_raw": ende_raw,
                "date_end_iso": ende_iso,
                "date_end_partial": ende_partial,
                "is_tbd": False,
                "context": ctx,
                "raw_quote": quote,
                "page_number": page,
                "start_time": st_bei(s),
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
                "start_time": st_bei(s),
                "source_uuid": src["uuid"],
                "source_filename": src.get("filename") or "",
            })
    return candidates
