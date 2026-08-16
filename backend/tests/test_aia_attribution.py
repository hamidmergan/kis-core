"""Tool-facing attribution: ranked search hits -> nav-only structured source chips.

Shares the chat's distance gate (_GENERIC_ATTRIB_MAX_DIST) and selector
(_pick_attribution) so a flashcard/quiz cites the SAME way a chat answer does:
the closest retrieved chunk within the gate, nav-only (page for PDFs, timestamp
for media), or NO chip when nothing is close enough."""

from src.services.aia_attribution import chips_for_claim, attribute_claims


def _hit(sid, page, dist, start=None, content=None):
    # Real chunk text is long; the attribution drops sub-100-char boilerplate fragments, so
    # tests use realistic content unless they specifically exercise that filter.
    return {"source_id": sid, "page_number": page, "content": content or ("lorem ipsum " * 12),
            "vec_distance": dist, "start_time": start}


def test_returns_single_nav_chip_for_close_pdf_hit():
    hits = [_hit(1, 12, 0.2)]
    chips = chips_for_claim(hits, {1: "Skript.pdf"})
    assert chips == [{"source_label": "Skript.pdf", "page_number": 12, "start_time": None}]


def test_boilerplate_magnet_chunk_is_ignored():
    # A short running-header/title fragment (a "magnet" close to any query) must NOT anchor a
    # citation, even at a tiny distance — it is filtered out before selection.
    magnet = {"source_id": 1, "page_number": 15, "content": "VON DER IDEE ZUR VERÖFFENTLICHUNG",
              "vec_distance": 0.1, "start_time": None}
    assert chips_for_claim([magnet], {1: "Skript.pdf"}) == []
    # but a real (long) chunk on another page still wins
    real = _hit(1, 6, 0.45)
    chips = chips_for_claim([magnet, real], {1: "Skript.pdf"})
    assert chips == [{"source_label": "Skript.pdf", "page_number": 6, "start_time": None}]


def test_no_chip_when_all_hits_beyond_gate():
    # Nothing close enough -> NO fabricated source (unlike the old whole-page guess).
    # Gate is the shared 0.6: a topically-adjacent page at ~0.62 stays uncited rather than
    # risk a wrong link (a looser 0.66 was tried and reverted, see module docstring).
    hits = [_hit(1, 5, 0.80), _hit(1, 7, 0.62)]
    assert chips_for_claim(hits, {1: "Skript.pdf"}) == []


def test_seen_pages_keeps_a_shown_page():
    # chat-style seen-check: a close hit on a page the LLM WAS shown is kept.
    chips = chips_for_claim([_hit(1, 4, 0.2)], {1: "A.pdf"}, seen_pages_by_source={1: {3, 4}})
    assert chips == [{"source_label": "A.pdf", "page_number": 4, "start_time": None}]


def test_seen_pages_rejects_an_unshown_page():
    # A close hit on a page NOT in the generation context -> no chip (never cite unseen).
    assert chips_for_claim([_hit(1, 9, 0.2)], {1: "A.pdf"}, seen_pages_by_source={1: {3, 4}}) == []


def test_media_hit_cites_timestamp_not_page():
    # Audio/video chunk: carries a transcript page_number (segment index) AND a start_time.
    # The chip must use the timestamp and drop the page, mirroring the chat.
    hits = [_hit(3, 9, 0.2, start=92.0)]
    chips = chips_for_claim(hits, {3: "Vorlesung.webm"})
    assert chips == [{"source_label": "Vorlesung.webm", "page_number": None, "start_time": 92.0}]


# ── Segment-genaue Zeitmarke, wie im Chat ────────────────────────────────────
# Ein Medien-Chunk fasst 1000 Zeichen zusammen, bei langsamem Sprechen ueber zwei
# Minuten. Die Chunk-Startzeit zeigt dann Minuten vor die zitierte Aussage.

_SEGMENTE = [
    {"start": 0.0, "end": 24.0, "text": "Ja, herzlich willkommen zur heutigen Konferenz."},
    {"start": 30.0, "end": 59.0, "text": "Heute geht es um wissenschaftliches Arbeiten."},
    {"start": 117.0, "end": 128.0, "text": "Beim Abdriften merken Sie, dass die Recherche wegfuehrt."},
]


def test_media_chip_points_at_the_segment_that_carries_the_claim():
    # Der Chunk-Text ist die Kette seiner Segmente, so baut ``segments_to_chunks`` ihn.
    hits = [_hit(3, 9, 0.2, start=0.0,
                 content=" ".join(s["text"] for s in _SEGMENTE))]
    hits[0]["end_time"] = _SEGMENTE[-1]["end"]
    chips = chips_for_claim(hits, {3: "Vorlesung.webm"},
                            claim="Beim Abdriften fuehrt die Recherche weg vom Thema",
                            segments_fn=lambda sid: _SEGMENTE)
    assert chips == [{"source_label": "Vorlesung.webm", "page_number": None, "start_time": 117.0}]


def test_pdf_chip_never_asks_for_segments():
    # Eine reine PDF-Sammlung darf die Ablage gar nicht erst anfassen.
    gefragt = []

    def segments_fn(sid):
        gefragt.append(sid)
        return []

    chips_for_claim([_hit(1, 12, 0.2)], {1: "Skript.pdf"}, claim="x", segments_fn=segments_fn)
    assert gefragt == []


def test_multi_adds_cosources_within_delta_only():
    hits = [
        _hit(1, 5, 0.20),   # best
        _hit(1, 9, 0.25),   # within the multi-chip delta of best -> kept
        _hit(2, 3, 0.55),   # within the 0.6 gate but beyond the delta -> dropped
    ]
    chips = chips_for_claim(hits, {1: "A.pdf", 2: "B.pdf"}, multi=True)
    assert chips == [
        {"source_label": "A.pdf", "page_number": 5, "start_time": None},
        {"source_label": "A.pdf", "page_number": 9, "start_time": None},
    ]


def test_attribute_claims_batches_embeds_and_returns_chips_per_claim():
    calls = {"embed": 0}

    def embed_fn(texts):
        calls["embed"] += 1
        return [[1.0, 0.0] for _ in texts]

    hits_by_claim = {
        "What is X?": [_hit(1, 4, 0.2)],
        "What is Y?": [_hit(2, 7, 0.9)],  # beyond gate -> no chip
    }

    def search_fn(text, vec):
        return hits_by_claim[text]

    out = attribute_claims(
        claims=["What is X?", "What is Y?"],
        source_id_to_label={1: "A.pdf", 2: "B.pdf"},
        embed_fn=embed_fn,
        search_fn=search_fn,
    )
    assert out == [
        [{"source_label": "A.pdf", "page_number": 4, "start_time": None}],
        [],
    ]
    assert calls["embed"] == 1  # ONE batched embed for all claims, not one per claim


def test_attribute_claims_stricter_max_distance_abstains_on_weak_hit():
    # A hit at 0.55 passes the default 0.6 gate but not a tighter 0.5 gate — used by the
    # mindmap so a thin one-word label abstains instead of citing a near-but-wrong page.
    def embed_fn(texts):
        return [[1.0, 0.0] for _ in texts]

    def search_fn(text, vec):
        return [_hit(1, 4, 0.55)]

    default_gate = attribute_claims(["Poster"], {1: "A.pdf"}, embed_fn=embed_fn, search_fn=search_fn)
    strict_gate = attribute_claims(["Poster"], {1: "A.pdf"}, max_distance=0.5,
                                   embed_fn=embed_fn, search_fn=search_fn)
    assert default_gate == [[{"source_label": "A.pdf", "page_number": 4, "start_time": None}]]
    assert strict_gate == [[]]


def test_attribute_claims_returns_empty_on_embed_failure():
    # A flaky embedding provider must NOT crash card generation: degrade to no chips.
    def embed_fn(texts):
        raise RuntimeError("provider down")

    out = attribute_claims(
        claims=["a", "b"],
        source_id_to_label={},
        embed_fn=embed_fn,
        search_fn=lambda t, v: [_hit(1, 1, 0.1)],
    )
    assert out == [[], []]


# ── Kandidatenzahl: die Suche ordnet nach RRF, der Auswaehler nach Distanz ────

def test_closest_hit_wins_even_when_it_ranks_last_in_the_search_order():
    """Der Auswaehler folgt der DISTANZ, nicht der Reihenfolge der Suche.

    Beide Massstaebe existieren nebeneinander: die Suche ordnet nach RRF, also Vektor
    UND Stichwort gemischt, der Auswaehler nimmt den inhaltlich naechsten. Solange die
    Suche genug Kandidaten liefert, ist das gutartig. Kuerzt sie zu frueh, entscheidet
    faktisch das RRF darueber, wen der Auswaehler ueberhaupt sieht.
    """
    hits = [_hit(1, p, 0.40) for p in range(1, 12)] + [_hit(2, 3, 0.221)]
    chips = chips_for_claim(hits, {1: "Folien.pdf", 2: "Richtig.pdf"}, multi=True)
    assert chips[0] == {"source_label": "Richtig.pdf", "page_number": 3, "start_time": None}


def test_attribution_asks_for_enough_candidates():
    """Regression "die PDF-Folie bekam keinen Beleg" (16.08.2026).

    Im Kurs "Wiss. Seminar" ist die Folie mit "20 Minuten PPT-Praesentation, 10 Minuten
    Fragerunde/Diskussion" fuer genau diesen Antwortsatz der naechste Chunk ueberhaupt
    (Distanz 0,221 gegen 0,334 beim naechsten). Im RRF stand sie auf Platz 11, weil ihr
    der Stichworttreffer fehlte: die Antwort schreibt "PowerPoint-Praesentation" und
    "Fragerunde", die Folie "PPT-Praesentation" und "Fragerunde/Diskussion", und aus
    letzterem macht Postgres EIN Wort wie einen Dateipfad. Bei 10 Kandidaten fiel sie
    damit aus der Vorauswahl, und zitiert wurden drei Videostellen.

    Die Zahl haelt fest, dass die Vorauswahl weit genug reicht, damit der Auswaehler
    seinen eigenen Massstab anwenden kann.
    """
    from src.features.ai_assistant.routes._helpers import _ATTRIB_CANDIDATES
    assert _ATTRIB_CANDIDATES >= 30


def test_multi_chip_survives_a_keyword_only_hit_without_distance():
    """Ein reiner Stichworttreffer hat kein ``vec_distance``.

    Die Mehrfach-Auswahl sortierte die Kandidaten nach Abstand, BEVOR sie die ohne
    Abstand aussortierte, und stuerzte dann ab. Latent war das immer; seit die
    Vorauswahl 40 statt 10 Kandidaten liefert, sind Treffer ohne Abstand haeufig
    genug, um es auszuloesen.
    """
    ohne = {"source_id": 2, "page_number": 4, "content": "lorem ipsum " * 12,
            "vec_distance": None, "start_time": None}
    chips = chips_for_claim([_hit(1, 12, 0.2), ohne, _hit(1, 13, 0.24)],
                            {1: "Skript.pdf", 2: "Anderes.pdf"}, multi=True)
    assert chips and chips[0]["source_label"] == "Skript.pdf"
    assert all(c["source_label"] != "Anderes.pdf" for c in chips)
