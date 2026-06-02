from src.features.ai_assistant.routes._helpers import _sanitize_citations


def test_sanitize_repairs_page_and_time():
    assert _sanitize_citations("Foo [1] S. 3 bar") == "Foo [1, S. 3] bar"
    assert _sanitize_citations("Clip [2] 05:32 end") == "Clip [2, 05:32] end"


from src.features.ai_assistant.routes._grounding import CitationGrounder
from src.features.ai_assistant.routes._citation_match import Unit


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
