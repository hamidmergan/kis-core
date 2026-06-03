from src.features.ai_assistant.routes._citation_match import Unit
from src.features.ai_assistant.routes._grounding import CitationGrounder
from src.features.ai_assistant.routes._helpers import _sanitize_citations


def test_sanitize_repairs_page_and_time():
    assert _sanitize_citations("Foo [1] S. 3 bar") == "Foo [1, S. 3] bar"
    assert _sanitize_citations("Clip [2] 05:32 end") == "Clip [2, 05:32] end"


class _Loader:
    """Minimal SourceUnitLoader stand-in: only .units (no offsets/furniture),
    so chips ground to a page+keyword without @offset suffixes."""
    def __init__(self, by_id):
        self._by_id = by_id

    def units(self, source, *, is_media):
        return self._by_id[source["id"]]


def _sources(units_by_id):
    # qnum -> {source, is_media, pages}
    return {
        qn: {"source": {"id": qn}, "is_media": False,
             "pages": {u.page for u in units if u.page is not None}}
        for qn, units in units_by_id.items()
    }


def test_feed_line_grounds_existing_citation():
    units = {1: [Unit(3, None, None, "Dezimalbrueche sind Brueche mit Nenner 10")]}
    g = CitationGrounder(_sources(units), _Loader(units), [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}])
    out = g.feed_line("Es geht um Dezimalbrueche. [1, S. 9 | Dezimalbrueche]")
    # page corrected from the bogus 9 to the unit's real page 3
    assert "[1, S. 3" in out
    assert "S. 9" not in out


def test_feed_line_keeps_summary_chip_free_after_cited_body():
    units = {1: [Unit(2, None, None, "Die Methode nutzt einen Test")]}
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}])
    g.feed_line("Die Methode nutzt einen Test. [1, S. 2 | Test]")  # cited body
    g.feed_line("Zusammenfassung")                                  # heading
    out = g.feed_line("Die Methode nutzt einen Test. [1, S. 2 | Test]")  # recap
    assert "[1" not in out  # stripped inside summary


def _reg(entries):
    # cid -> registry entry; entries: {cid: (qnum, page, content)}
    return {cid: {"qnum": qn, "source": {"id": qn}, "is_media": False,
                  "page": page, "start_time": None, "end_time": None, "content": content}
            for cid, (qn, page, content) in entries.items()}


def test_feed_line_grounds_chunk_id_citation():
    # The model cites the CHUNK it used (`#7`); we resolve it to the chunk's real page.
    units = {1: [Unit(5, None, None, "Der Algorithmus sortiert schnell in n log n")]}
    reg = _reg({7: (1, 5, "Der Algorithmus sortiert schnell in n log n")})
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}], reg)
    out = g.feed_line("Der Algorithmus sortiert schnell. [1, #7 | Algorithmus sortiert]")
    assert "[1, S. 5" in out
    assert "#" not in out                       # no raw chunk marker leaks


def test_feed_line_chunk_id_page_is_authoritative_over_keyword_reground():
    # The same keyword text also lives on page 3, which the legacy keyword resolver
    # would pick. The chunk id pins the real page (5) and must win.
    units = {1: [Unit(3, None, None, "Der Algorithmus sortiert schnell"),
                 Unit(5, None, None, "Der Algorithmus sortiert schnell")]}
    reg = _reg({7: (1, 5, "Der Algorithmus sortiert schnell")})
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}], reg)
    out = g.feed_line("Der Algorithmus sortiert schnell. [1, #7 | Algorithmus sortiert]")
    assert "[1, S. 5" in out and "S. 3" not in out


def test_feed_line_unverified_chunk_dropped_then_filler_grounds():
    # The named chunk does NOT contain the claim -> chip dropped; the uncited-line
    # filler then grounds the line against the real units (page 2). Safety net intact.
    units = {1: [Unit(2, None, None, "die methode nutzt einen test zur pruefung")]}
    reg = _reg({7: (1, 9, "voellig anderes thema ohne jeden bezug")})
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}], reg)
    out = g.feed_line("Die Methode nutzt einen Test. [1, #7 | Methode Test]")
    assert "#" not in out
    assert "S. 9" not in out                     # the bogus chunk page never appears
    assert "[1, S. 2" in out                     # filler grounded to the real page


def test_feed_line_dedups_chips_resolving_to_same_position():
    # Two chips on one line ground to the SAME page -> the live grounder shows one.
    units = {1: [Unit(5, None, None, "Der Algorithmus sortiert schnell in n log n")]}
    g = CitationGrounder(_sources(units), _Loader(units),
                         [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}])
    out = g.feed_line("Der Algorithmus sortiert schnell. [1, S. 9 | Algorithmus] [1, S. 9 | sortiert]")
    assert out.count("[1, S. 5") == 1
    assert "S. 9" not in out


def test_feed_sequence_matches_full_pipeline_for_prose():
    # The line-by-line result joined equals the canonical batch grounding for a
    # plain prose answer (the common, must-be-flicker-free case).
    from src.features.ai_assistant.routes._helpers import (
        resolve_citation_positions, fill_uncited_lines, _sanitize_citations, _chipify_inline_refs,
    )
    units = {1: [Unit(4, None, None, "Der Algorithmus sortiert in n log n Schritten")]}
    src, loader = _sources(units), _Loader(units)
    qmap = [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}]
    answer = "Der Algorithmus sortiert schnell. [1, S. 1 | Algorithmus]\nDas ist wichtig."

    # canonical batch pipeline
    canon = _chipify_inline_refs(_sanitize_citations(answer), qmap)
    canon = resolve_citation_positions(canon, src, loader)
    canon = fill_uncited_lines(canon, src, loader)

    # incremental
    g = CitationGrounder(src, loader, qmap)
    inc = "\n".join(g.feed_line(line) for line in answer.split("\n"))
    assert inc == canon


def test_feed_sequence_matches_full_pipeline_with_summary():
    # Single closing "Zusammenfassung" after cited body: the incremental grounder
    # must match the FULL canonical pipeline incl. _strip_summary_citations.
    from src.features.ai_assistant.routes._helpers import (
        resolve_citation_positions, fill_uncited_lines, _strip_summary_citations,
        _sanitize_citations, _chipify_inline_refs,
    )
    units = {1: [Unit(2, None, None, "Die Methode nutzt einen Test zur Pruefung")]}
    src, loader = _sources(units), _Loader(units)
    qmap = [{"qnum": 1, "uuid": "u1", "filename": "f.pdf"}]
    answer = (
        "Die Methode nutzt einen Test. [1, S. 2 | Test]\n"
        "Zusammenfassung\n"
        "Die Methode nutzt einen Test zur Pruefung. [1, S. 2 | Test]"
    )

    canon = _chipify_inline_refs(_sanitize_citations(answer), qmap)
    canon = resolve_citation_positions(canon, src, loader)
    canon = fill_uncited_lines(canon, src, loader)
    canon = _strip_summary_citations(canon)

    g = CitationGrounder(src, loader, qmap)
    inc = "\n".join(g.feed_line(line) for line in answer.split("\n"))
    assert inc == canon
