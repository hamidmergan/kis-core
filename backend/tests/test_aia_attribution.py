"""Tool-facing attribution: ranked search hits -> nav-only structured source chips.

Shares the chat's distance gate (_GENERIC_ATTRIB_MAX_DIST) and selector
(_pick_attribution) so a flashcard/quiz cites the SAME way a chat answer does:
the closest retrieved chunk within the gate, nav-only (page for PDFs, timestamp
for media), or NO chip when nothing is close enough."""

from src.services.aia_attribution import chips_for_claim, attribute_claims


def _hit(sid, page, dist, start=None, content="x"):
    return {"source_id": sid, "page_number": page, "content": content,
            "vec_distance": dist, "start_time": start}


def test_returns_single_nav_chip_for_close_pdf_hit():
    hits = [_hit(1, 12, 0.2)]
    chips = chips_for_claim(hits, {1: "Skript.pdf"})
    assert chips == [{"source_label": "Skript.pdf", "page_number": 12, "start_time": None}]


def test_no_chip_when_all_hits_beyond_gate():
    # Nothing close enough -> NO fabricated source (unlike the old whole-page guess).
    hits = [_hit(1, 5, 0.80), _hit(1, 7, 0.75)]
    assert chips_for_claim(hits, {1: "Skript.pdf"}) == []


def test_media_hit_cites_timestamp_not_page():
    # Audio/video chunk: carries a transcript page_number (segment index) AND a start_time.
    # The chip must use the timestamp and drop the page, mirroring the chat.
    hits = [_hit(3, 9, 0.2, start=92.0)]
    chips = chips_for_claim(hits, {3: "Vorlesung.webm"})
    assert chips == [{"source_label": "Vorlesung.webm", "page_number": None, "start_time": 92.0}]


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
