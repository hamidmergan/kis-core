import math
import os
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2.extras import RealDictCursor


_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
# Min trigram word-similarity for the fuzzy keyword fallback in hybrid_search_chunks.
# 0.45 catches typos ("authoren" vs "Autoren" ≈ 0.55) without pulling unrelated words.
_FUZZY_WORD_SIM = 0.45
from src.core.db.pool import get_connection

# aia_chunks.embedding is 2560-dim (current global model qwen3-embedding-4b). That is over
# pgvector's 2000-dim limit for a `vector` ANN index, so the hnsw index is built on the
# halfvec(2560) form (halfvec indexes up to 4000 dims) as a PARTIAL index with predicate
# vector_dims=2560. Both the index and every query that wants it must use this exact dim.
# Changing the embedding model means re-embedding all chunks AND rebuilding the index.
_EMBED_INDEX_DIM = 2560
# hnsw scan tuning for the FILTERED workspace query: a selective source filter drops many of
# the global nearest neighbours, so iterative scan keeps pulling until it has a full top-80.
# relaxed_order is safe because callers re-sort candidates by vec_distance. This guarantees
# recall on the MAIN retrieval too (hybrid_search feeds context, not just chips). A plain scan
# with a big ef_search is ~10x faster on LARGE workspaces (~114ms -> ~10ms) at identical top-1,
# but can under-fill on very selective filters, so recall robustness wins over the ~10%
# end-to-end (vector search is only ~10% of a hybrid_search call anyway — the rest is the
# keyword/substring queries + RRF fusion).
_HNSW_EF_SEARCH = 100

# Fragewoerter und Fuellwoerter, die aus einer Suchanfrage fliegen. DE und EN in einer
# Liste, damit dieselbe Anfrage in beiden Sprachen gleich behandelt wird.
#
# Warum es das braucht. Die Volltextsuche laeuft mit der Konfiguration ``simple``, die
# KEINE Fuellwoerter kennt, und alle Woerter werden mit ODER verknuepft. "wann ist die
# fragestunde" passte damit auf 314 von 327 Chunks, weil "die" und "ist" ueberall
# vorkommen. Uebrig bleibt "fragestunde", und das passt auf genau einen.
#
# ``wann`` fehlte hier, obwohl ``wer``, ``was``, ``wie``, ``wo`` drinstanden. Der
# ILIKE-Arm verknuepft seine Woerter mit UND, suchte also nach "wann" UND
# "fragestunde" und verfehlte den einen Chunk, der das seltene Wort traegt: er sagt
# "da machen wir noch eine Fragestunde" und enthaelt "wann" natuerlich nicht. Jede
# Frage nach einem Zeitpunkt war davon betroffen.
_QUERY_STOPWORDS = {
    # Deutsch: Artikel, Praepositionen, Hilfsverben
    "der","die","das","ein","eine","und","oder","ist","hat","war","mit","von","für","fuer",
    "auf","aus","bei","den","dem","des","als","nach","über","ueber","vor","bis","wenn","dass",
    "aber","auch","noch","nur","doch","sehr","wird","sind","kann","mehr","nicht","sich","gibt",
    "diese","einer","einem","einen","muss","müssen","muessen","darf","dürfen","duerfen","soll",
    "sollen","im","am","um","zu","zur","zum","es","man","mir","mich","ich","sie","er","wir",
    # Deutsch: Fragewoerter. Sie stehen fast nie im Text, der die Antwort traegt.
    "wer","was","wie","wo","wann","warum","wieso","weshalb","wem","wen","wessen","woher","wohin",
    "welche","welcher","welches","welchem","welchen",
    # Englisch
    "the","and","or","of","is","in","to","a","an","that","this","for","with","on","at","by",
    "from","as","it","be","are","were","has","had","have","not","but","so","if","then","do",
    "does","did","what","which","who","when","where","why","how","can","must","should","would",
}


# Gewichte je Wort, gemerkt je Workspace. Eine Chat-Frage ruft die Suche einmal PRO
# QUELLE auf, bei 30 Gesetzen also 30 mal mit derselben Anfrage, und die Chips noch
# einmal je Antwortzeile. Ohne dieses Gedaechtnis zahlt jeder dieser Aufrufe die
# Zaehlung erneut: gemessen 78 ms statt 10 ms pro Aufruf, also gut zwei Sekunden nur
# fuers Zaehlen. Die Seltenheit ist ohnehin eine Eigenschaft des BESTANDES und nicht
# der einzelnen Quelle, sie gehoert also gar nicht in den Aufruf.
#
# Die Haltezeit ist kurz, damit frisch eingelesene Quellen zeitnah einfliessen. Ein
# veraltetes Gewicht macht die Rangfolge etwas ungenauer, nie falsch.
_IDF_TTL_SECONDS = 300.0
# Wie viele Woerter hoechstens in die Bewertung gehen, und ab welchem Gewicht sich ein
# Wort ueberhaupt lohnt. Jedes Wort kostet eine eigene Indexpruefung pro Zeile. Eine
# kurze Frage hat ohnehin ein bis zwei Inhaltswoerter, eine ganze Antwortzeile (so
# suchen die Quellenchips) hat sechs und mehr, und die haeufigen darunter tragen nichts
# zur Unterscheidung bei: sie stehen ja fast ueberall. Gemessen an fuenf echten
# Antwortzeilen kostete die ungekuerzte Fassung 795 ms statt 577 ms, mit denselben
# Treffern. Die seltensten Woerter entscheiden, so ist BM25 gebaut.
# 0.7 entspricht rund "steht in hoechstens der Haelfte der Chunks".
_KW_MAX_TERMS = 4
_KW_MIN_IDF = 0.7
_IDF_CACHE: dict[tuple[int, str], tuple[float, float]] = {}
_IDF_N_CACHE: dict[int, tuple[float, int]] = {}


def _term_idf(cur, workspace_id: int, terms: list[str]) -> list[tuple[str, float]]:
    """Gewicht je Anfragewort: ``ln(N / df)`` ueber den ganzen Workspace.

    Je seltener ein Wort im Bestand, desto schwerer wiegt ein Treffer darauf. Ein
    Wort, das in JEDEM Chunk steht, bekommt 0 und faellt von selbst weg. Woerter, die
    gar nicht vorkommen, fehlen im Ergebnis.

    Postgres kann das nicht selbst: ``ts_rank`` und ``ts_rank_cd`` bewerten die Dichte
    im einzelnen Text, nicht die Seltenheit im Bestand. Genau dieser Teil von BM25
    fehlt, und ohne ihn zaehlt "die" so viel wie ein Fachbegriff.
    """
    import time as _time
    jetzt = _time.monotonic()

    n_eintrag = _IDF_N_CACHE.get(workspace_id)
    if n_eintrag is None or jetzt - n_eintrag[0] > _IDF_TTL_SECONDS:
        cur.execute(
            """SELECT count(*) FROM aia_chunks c
                 JOIN aia_sources s ON s.id = c.source_id
                WHERE s.workspace_id = %s""",
            (workspace_id,),
        )
        n_chunks = int(cur.fetchone()[0] or 0)
        _IDF_N_CACHE[workspace_id] = (jetzt, n_chunks)
    else:
        n_chunks = n_eintrag[1]
    if not n_chunks:
        return []

    fehlend = [w for w in terms
               if (e := _IDF_CACHE.get((workspace_id, w.lower()))) is None
               or jetzt - e[0] > _IDF_TTL_SECONDS]
    if fehlend:
        cur.execute(
            """SELECT t.w,
                      (SELECT count(*) FROM aia_chunks c
                         JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s
                          AND c.search_vector @@ plainto_tsquery('simple', t.w)) AS df
                 FROM unnest(%s::text[]) AS t(w)""",
            (workspace_id, fehlend),
        )
        for row in cur.fetchall():
            _IDF_CACHE[(workspace_id, str(row["w"]).lower())] = (jetzt, float(row["df"] or 0))
        if len(_IDF_CACHE) > 20000:      # Deckel, damit das Gedaechtnis nicht waechst
            _IDF_CACHE.clear()

    out: list[tuple[str, float]] = []
    gesehen: set[str] = set()
    for w in terms:
        if w.lower() in gesehen:
            continue
        gesehen.add(w.lower())
        df = _IDF_CACHE.get((workspace_id, w.lower()), (0.0, 0.0))[1]
        if 0 < df <= n_chunks:
            out.append((w, math.log(n_chunks / df)))
    # Die seltensten zuerst, dann kuerzen. Traegt kein Wort genug, bleibt trotzdem das
    # beste stehen, sonst faende eine Frage aus lauter haeufigen Woertern gar nichts.
    out.sort(key=lambda t: t[1], reverse=True)
    stark = [t for t in out if t[1] >= _KW_MIN_IDF] or out[:1]
    return stark[:_KW_MAX_TERMS]


def _content_words(query_text: str) -> list[str]:
    """Die inhaltstragenden Woerter einer Anfrage, Fuellwoerter raus.

    Eine Zeichenkette, keine Sprachlogik: kurze Woerter und die Liste oben fallen weg.
    Bleibt nichts uebrig ("was ist das"), gibt es eine leere Liste und der Aufrufer
    faellt auf die ganze Anfrage zurueck, damit eine reine Fuellwort-Frage nicht
    ploetzlich gar nichts mehr findet."""
    return [w for w in (t.strip(".,;:!?\"'()[]") for t in query_text.split())
            if len(w) >= 2 and w.lower() not in _QUERY_STOPWORDS]


def _vector_search_sql(source_filter: str) -> str:
    """Top-80 cosine vector search in the form that uses idx_chunks_embedding_hnsw.

    Casts to halfvec(2560) (the indexed expression) and carries the partial-index predicate
    vector_dims=2560 so the planner picks the hnsw index; without the cast it would full-scan.
    The predicate also means a future different-dim model neither breaks this query nor the
    index (those rows are simply not indexed and not returned). ``source_filter`` is a trusted
    fragment built by the caller, never user input."""
    d = _EMBED_INDEX_DIM
    return f"""SELECT c.id, c.page_number,
                    c.embedding::halfvec({d}) <=> %s::halfvec({d}) AS distance,
                    ROW_NUMBER() OVER (
                        ORDER BY c.embedding::halfvec({d}) <=> %s::halfvec({d})
                    ) AS rank
                FROM aia_chunks c
                JOIN aia_sources s ON s.id = c.source_id
                WHERE s.workspace_id = %s {source_filter}
                  AND c.embedding IS NOT NULL
                  AND vector_dims(c.embedding) = {d}
                ORDER BY c.embedding::halfvec({d}) <=> %s::halfvec({d})
                LIMIT 80"""


def _seen_pages_filter(seen_pages: dict[int, set] | None) -> tuple[str, list]:
    """WHERE-Fragment, das die Suche auf ABGERUFENE Quellen und Seiten einschraenkt.

    Fuer die Beleg-Suche nach der Antwort. Ein Chip darf nur auf eine Stelle zeigen,
    die das Modell auch gelesen hat, sonst schickt er den Leser auf eine Seite, die an
    der Antwort nicht beteiligt war. Bisher stand diese Pruefung als ``_is_seen`` NACH
    der Suche in Python: die Datenbank rankte den ganzen Workspace und die Liste wurde
    hinterher zerrissen. Hier steht dieselbe Regel, nur frueher, damit die Kandidaten
    von vornherein alle gueltig sind und der Suchraum auf die paar Dutzend Chunks der
    gesehenen Seiten faellt.

    ``seen_pages`` bildet Quelle auf Seitenmenge ab, genau wie ``seen_pages_by_source``
    aus ``_pack_context_batches``. Eine LEERE Menge heisst Medienquelle: dort zeigt der
    Chip auf eine Zeitmarke, es gibt keine Seite zu pruefen, also kommt die Quelle ganz
    durch. Ohne Angabe gibt es kein Fragment, der Hauptabruf sucht unveraendert breit.

    Eine ODER-Kette je Quelle, keine Mengenoperation. Das ist gemessen, nicht Geschmack:
    die kuerzere Fassung ``EXISTS (SELECT 1 FROM unnest(...))`` wird zu einem Semi-Join,
    den der Planer nicht auf einen Index abbilden kann, und faellt auf den vollen
    Durchlauf zurueck (675 ms). Die Kette wird zu einem BitmapOr ueber
    ``idx_chunks_source_page`` und braucht 6,8 ms. Ohne diesen Index bringt der Filter
    ueberhaupt nur ein Drittel (64 ms -> 40 ms statt -> 7 ms).

    Das Fragment wird an ``source_filter`` gehaengt und ist keine Nutzereingabe: alle
    Werte reisen als Parameter, nicht im Text.
    """
    if not seen_pages:
        return "", []
    teile: list[str] = []
    params: list = []
    # Sortiert, damit dieselbe Eingabe dieselbe Abfrage ergibt und Postgres den Plan
    # wiederverwenden kann.
    for sid in sorted(seen_pages):
        pages = seen_pages[sid]
        if not pages:
            teile.append("(c.source_id = %s)")
            params.append(sid)
        else:
            teile.append("(c.source_id = %s AND c.page_number = ANY(%s))")
            params += [sid, sorted(pages)]
    # Kein Zweig fuer ``c.page_number IS NULL``: die Spalte ist NOT NULL. Die Nachsicht
    # in _is_seen deckt Stellen ab, die gar nicht aus dieser Tabelle kommen.
    return " AND (" + " OR ".join(teile) + ")", params


_SEARCH_MODES = ("hybrid", "dense", "keyword")


def _rrf_fuse(vec_rows, kw_rows, rrf_k: int, mode: str = "hybrid"):
    """Reciprocal Rank Fusion ueber die beiden Trefferlisten.

    Rueckgabe ``(scores, kw_ids)``. Zwei Listen, deren Rohwerte man nicht
    vergleichen kann (Kosinus-Abstand gegen Wortgewicht), werden ueber ihre
    PLAETZE zusammengelegt: jeder Treffer steuert ``1 / (rrf_k + Platz)`` bei.

    ``mode`` blendet einen der beiden Wege aus. Nur fuer die Messung gedacht
    (backend/scripts/rag_retrieval_eval.py --vergleich), der Chat laeuft immer
    auf "hybrid". Ein unbekannter Wert ist ein Fehler statt eines stillen
    Rueckfalls, sonst vergleicht ein Tippfehler zwei gleiche Laeufe."""
    if mode not in _SEARCH_MODES:
        raise ValueError(f"unbekannter Suchmodus: {mode!r}")

    scores: dict[int, float] = {}
    if mode != "keyword":
        for row in vec_rows:
            scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
    # Keyword hits (BM25 + exact-substring): the actual term-overlap signal.
    # A chunk matched by vector ONLY is merely "semantically near" and may
    # be off-topic — callers use kw_hit to tell the two apart.
    kw_ids: set[int] = set()
    if mode != "dense":
        kw_ids = {row["id"] for row in kw_rows}
        for row in kw_rows:
            scores[row["id"]] = scores.get(row["id"], 0) + 1.0 / (rrf_k + row["rank"])
    return scores, kw_ids


def create_aia_chunk(
    source_id: int,
    page_number: int,
    content: str,
    start_time: float | None = None,
    end_time: float | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_chunks
                   (source_id, page_number, content, search_vector, start_time, end_time)
                   VALUES (%s, %s, %s, to_tsvector('simple', %s), %s, %s)
                   RETURNING id""",
                (source_id, page_number, content, content, start_time, end_time),
            )
            chunk_id = cur.fetchone()[0]
        conn.commit()
    return chunk_id

def get_aia_chunks_by_source(source_id: int) -> list[dict]:
    """Return all chunks for a source (without embeddings), ordered by page/time."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM aia_chunks
                   WHERE source_id = %s
                   ORDER BY COALESCE(start_time, 0), page_number""",
                (source_id,),
            )
            return [dict(row) for row in cur.fetchall()]

def find_chunks_containing(workspace_id: int, needle: str,
                           source_ids: list[int] | None = None,
                           limit: int = 4) -> list[dict]:
    """Chunks of a workspace whose text carries ``needle`` verbatim, oldest page first.

    A citation lookup, not a search: vector retrieval ranks by what a passage is ABOUT,
    and the passage that merely talks about office hours beats the slide that states
    "17:30-18:30 Uhr" — measured 0.398 against 0.656, i.e. the slide was not even inside
    the citation gate. A reader checking a time looks the time up; this is that lookup.
    Deliberately dumb (case-insensitive containment) so it holds for a clock time, a date,
    a section sign or a formula alike.
    """
    if not needle:
        return []
    where = ["s.workspace_id = %s", "c.content ILIKE %s"]
    params: list = [workspace_id, f"%{needle}%"]
    if source_ids:
        where.append("c.source_id = ANY(%s)")
        params.append(list(source_ids))
    params.append(limit)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT c.id, c.source_id, c.page_number, c.content,
                           c.start_time, c.end_time
                    FROM aia_chunks c JOIN aia_sources s ON s.id = c.source_id
                    WHERE {' AND '.join(where)}
                    ORDER BY c.page_number NULLS LAST, c.id
                    LIMIT %s""",
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def get_page_text(source_id: int, page_number: int | None) -> str:
    """Concatenated chunk text of ONE page of a source (ordered), or "" when the
    page has no text chunk. Used to give the glossary definition prompt the real
    surrounding context of a marked term instead of the bare word."""
    if page_number is None:
        return ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content FROM aia_chunks
                   WHERE source_id = %s AND page_number = %s
                   ORDER BY id""",
                (source_id, page_number),
            )
            return "\n".join(r[0] for r in cur.fetchall() if r[0])


def get_source_page_numbers(source_id: int) -> set[int]:
    """Return the set of REAL page numbers for a source: the pages that have a
    text/OCR chunk. Used to validate citation pages against pages that actually
    exist (covers image/scanned pages that were OCR'd, while rejecting fully
    hallucinated numbers)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT page_number FROM aia_chunks WHERE source_id = %s",
                (source_id,),
            )
            return {row[0] for row in cur.fetchall() if row[0] is not None}

def update_chunk_embedding(chunk_id: int, embedding: list[float]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE aia_chunks SET embedding = %s::vector WHERE id = %s",
                (str(embedding), chunk_id),
            )
        conn.commit()

def hybrid_search_chunks(
    workspace_id: int,
    query_text: str,
    query_embedding: list[float],
    source_ids: list[int] | None = None,
    limit: int = 15,
    rrf_k: int = 60,
    fuzzy: bool = False,
    mode: str = "hybrid",
    seen_pages: dict[int, set] | None = None,
) -> list[dict]:
    """Hybrid search: combines vector similarity + BM25 keyword search via RRF.

    ``mode`` schaltet einen der beiden Wege ab ("dense" / "keyword") und dient
    NUR der Messung, welcher Weg das Ergebnis traegt. Der Chat laeuft immer auf
    dem Vorgabewert "hybrid". Siehe _rrf_fuse und scripts/rag_retrieval_eval.py.

    ``fuzzy`` adds a trigram word-similarity fallback so a MISSPELLED query word
    ("authoren") still anchors the right chunk. It is a per-row word_similarity
    scan (no index), so enable it ONLY for the short user query — NOT for the
    post-hoc attribution, which fires once per answer line over clean text and
    would otherwise pay seconds of needless fuzzy scans (slow citation chips).

    ``seen_pages`` schraenkt die Suche auf abgerufene Quellen und Seiten ein, siehe
    ``_seen_pages_filter``. Nur die Beleg-Suche setzt das, der Hauptabruf sucht breit."""

    if mode not in _SEARCH_MODES:
        raise ValueError(f"unbekannter Suchmodus: {mode!r}")

    source_filter = ""
    source_param: list = []
    if source_ids is not None:
        source_filter = "AND s.id = ANY(%s)"
        source_param = [source_ids]

    # An source_filter angehaengt statt eigenstaendig eingebaut: so erbt JEDER der vier
    # Arme (Vektor, Stichwort, Teilstring, Fuzzy) den Filter an derselben Stelle im Text
    # UND in der Parameterliste, ohne dass unten eine Zeile anzufassen waere.
    _seen_sql, _seen_param = _seen_pages_filter(seen_pages)
    source_filter += _seen_sql
    source_param += _seen_param

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Iterative hnsw scan so the FILTERED workspace query still gets a full top-80
            # (harmless no-op on the keyword/substring queries below and when no hnsw index
            # exists yet — the vector query then just full-scans).
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = %s", (_HNSW_EF_SEARCH,))
            # 1) Vector search (top 80). Keep the raw cosine distance: it is the
            # stopword-immune relevance signal (embeddings capture meaning, so a
            # conversational query like "erkläre mir bitte die X" still focuses on
            # X). Callers use it to tell a genuinely on-topic source from one that
            # only shares filler words. Uses the halfvec hnsw index (see _vector_search_sql).
            vec_rows, vec_distance = [], {}
            if mode != "keyword":
                cur.execute(
                    _vector_search_sql(source_filter),
                    [str(query_embedding), str(query_embedding), workspace_id] + source_param + [str(query_embedding)],
                )
                vec_rows = cur.fetchall()
                vec_distance = {row["id"]: float(row["distance"]) for row in vec_rows}

            # 2) Keyword search (top 80). Content words only, OR-joined, ranked by the
            # RARITY of the matched terms.
            #
            # Warum nicht ts_rank_cd allein: Postgres kennt kein IDF. ts_rank und
            # ts_rank_cd bewerten die DICHTE eines Treffers im Text, nicht die
            # SELTENHEIT des Wortes im Bestand. Damit zaehlt ein Wort, das in einem
            # von 11.162 Chunks steht, genauso viel wie eines, das in allen steht.
            # Gemessen: der einzige Chunk mit "Fragestunde" landete auf Platz 247.
            # Genau diese Gewichtung ist der Kern von BM25, und sie ist der Grund,
            # weshalb ein seltener Fachbegriff die richtige Stelle nach oben zieht.
            #
            # Die Gewichte kommen aus ``_term_idf`` und sind je Workspace gemerkt, weil
            # eine Frage diese Suche einmal PRO QUELLE ausloest.
            # Bei mode="dense" bleiben beide Listen leer, dann entfallen die drei
            # Stichwort-Abfragen unten (2a/2b/2c) samt ihrer Laufzeit.
            words = _content_words(query_text) if mode != "dense" else []
            # Rueckfall Wort fuer Wort, nicht die ganze Zeichenkette: ``plainto_tsquery``
            # verbindet eine mehrwortige Eingabe mit UND, eine Frage aus lauter
            # Fuellwoertern ("was ist das") faende damit fast nichts. Einzelne Woerter
            # bleiben ODER-verknuepft wie vorher.
            _terms = (_term_idf(cur, workspace_id, words or query_text.split())
                      if mode != "dense" else [])
            if _terms:
                # Summe der Gewichte aller getroffenen Woerter, bei Gleichstand die
                # Dichte. Die Gewichte sind gerechnete Zahlen, keine Nutzereingabe.
                _score = " + ".join(
                    f"(CASE WHEN c.search_vector @@ plainto_tsquery('simple', %s) THEN {idf:.6f} ELSE 0 END)"
                    for _w, idf in _terms
                )
                _any = " OR ".join(["c.search_vector @@ plainto_tsquery('simple', %s)"] * len(_terms))
                _wparams = [w for w, _i in _terms]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY ({_score}) DESC,
                                     ts_rank_cd(c.search_vector,
                                         plainto_tsquery('simple', %s)) DESC
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s {source_filter}
                          AND c.search_vector IS NOT NULL
                          AND ({_any})
                        LIMIT 80""",
                    _wparams + [" ".join(_wparams), workspace_id] + source_param + _wparams,
                )
                kw_rows = cur.fetchall()
            else:
                kw_rows = []

            # 2b) Exact substring fallback (catches proper names / out-of-vocab terms).
            # Content words only (see _QUERY_STOPWORDS) so an ILIKE search stays on the
            # topical terms regardless of source / query language.
            if words:
                ilike_clauses = " AND ".join(["c.content ILIKE %s"] * len(words))
                ilike_params = [f"%{w}%" for w in words]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY c.id
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s {source_filter}
                          AND {ilike_clauses}
                        LIMIT 40""",
                    [workspace_id] + source_param + ilike_params,
                )
                ilike_rows = cur.fetchall()
                if ilike_rows:
                    kw_rows = kw_rows + ilike_rows

            # 2c) Fuzzy (typo-tolerant) fallback. A misspelled query word still
            # matches a trigram-similar WORD in the text ("authoren" -> "Autoren"),
            # so the answer-bearing chunk is retrieved even when the exact token (and
            # thus its high BM25 rank) is lost. Language-agnostic (character trigrams,
            # no word lists). Only words >= 4 chars — shorter ones match too loosely.
            # Ranked by best similarity so the closest match leads the RRF fusion.
            fuzzy_words = [w for w in words if len(w) >= 4]
            if fuzzy and fuzzy_words:
                best_sim = "GREATEST(" + ", ".join(["word_similarity(%s, c.content)"] * len(fuzzy_words)) + ")"
                sim_clauses = " OR ".join(["word_similarity(%s, c.content) >= %s"] * len(fuzzy_words))
                sim_params: list = []
                for w in fuzzy_words:
                    sim_params += [w, _FUZZY_WORD_SIM]
                cur.execute(
                    f"""SELECT c.id, c.page_number, ROW_NUMBER() OVER (
                            ORDER BY {best_sim} DESC
                        ) AS rank
                        FROM aia_chunks c
                        JOIN aia_sources s ON s.id = c.source_id
                        WHERE s.workspace_id = %s {source_filter}
                          AND ({sim_clauses})
                        LIMIT 40""",
                    list(fuzzy_words) + [workspace_id] + source_param + sim_params,
                )
                fuzzy_rows = cur.fetchall()
                if fuzzy_rows:
                    kw_rows = kw_rows + fuzzy_rows

            # 3) RRF fusion (siehe _rrf_fuse, dort auch die Bedeutung von mode)
            scores, kw_ids = _rrf_fuse(vec_rows, kw_rows, rrf_k, mode)

            if not scores:
                return []

            # Fetch full chunk data for top results
            top_ids = sorted(scores, key=lambda i: scores[i], reverse=True)[:limit]
            cur.execute(
                """SELECT id, source_id, page_number, content, start_time, end_time
                   FROM aia_chunks WHERE id = ANY(%s)""",
                (top_ids,),
            )
            chunk_map = {r["id"]: dict(r) for r in cur.fetchall()}

            # Return in score order
            results = []
            for cid in top_ids:
                if cid in chunk_map:
                    chunk = chunk_map[cid]
                    chunk["hybrid_score"] = scores[cid]
                    chunk["kw_hit"] = cid in kw_ids
                    chunk["vec_distance"] = vec_distance.get(cid)  # cosine distance, None if kw-only
                    results.append(chunk)

    return results


# --- KI Tutor: Messages ---

def get_chunks_by_source(source_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, page_number, content, start_time, end_time
                   FROM aia_chunks
                   WHERE source_id = %s
                   ORDER BY page_number, id""",
                (source_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- KI Tutor: Glossary ---

