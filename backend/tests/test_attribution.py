"""Post-hoc semantic attribution for GENERIC answers.

Instead of trusting the model's (often wrong) page citations in an overview answer,
we re-ground EACH answer line with the same semantic search that works perfectly for
specific questions: embed the line, search the active sources, and attach the best
chunk's citation — BUT only when it is close enough (distance gate). A line that is
not clearly supported gets NO chip (no fabricated attribution / post-rationalization).
"""
from src.features.ai_assistant.routes._helpers import (
    _pick_attribution,
    _attribution_chip,
    _attribute_generic_text,
    _names_many_laws,
    _enum_chip_unbacked,
    _cos_dist,
    _refusal_lines,
    is_refusal_answer,
)


def _hit(sid, page, content, dist, start=None):
    return {"source_id": sid, "page_number": page, "content": content,
            "vec_distance": dist, "start_time": start}


# ── _pick_attribution (distance gate) ────────────────────────────────────────

def test_picks_closest_within_gate():
    hits = [_hit(1, 5, "a", 0.45), _hit(1, 7, "b", 0.20)]
    assert _pick_attribution(hits, 0.6)["page_number"] == 7  # closest wins


def test_rejects_when_all_too_far():
    hits = [_hit(1, 5, "a", 0.80), _hit(1, 7, "b", 0.75)]
    assert _pick_attribution(hits, 0.6) is None


def test_empty_hits_returns_none():
    assert _pick_attribution([], 0.6) is None


def test_ignores_hits_without_distance():
    assert _pick_attribution([{"source_id": 1, "page_number": 5}], 0.6) is None


# ── _attribution_chip (nav-only: page or timestamp, no offset/keyword) ───────

def test_attribution_chip_is_nav_only_pdf():
    assert _attribution_chip(2, _hit(1, 12, "x", 0.2), "line") == ["[2, S. 12]"]


def test_attribution_chip_is_nav_only_media():
    chunk = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    assert _attribution_chip(3, chunk, "line") == ["[3, 01:32]"]


def test_attribution_chip_media_with_segment_page_uses_timestamp():
    # REAL audio/video: transcript chunks carry a page_number (segment index) AND a
    # start_time. The chip MUST be the timestamp, never "S. <segment-index>".
    chunk = {"source_id": 3, "page_number": 9, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    assert _attribution_chip(3, chunk, "line") == ["[3, 01:32]"]


# ── _attribute_generic_text (orchestration, injected search) ─────────────────

def _searcher(mapping):
    # mapping: line-substring -> hits
    def search_one(line):
        for key, hits in mapping.items():
            if key in line:
                return hits
        return []
    return search_one


def test_attributes_supported_line_nav_only():
    line = "Das Modul behandelt Audio Grafik und Video."
    search = _searcher({"Audio Grafik": [_hit(1, 12, "Audio Grafik und Video Kernmedien", 0.2)]})
    out = _attribute_generic_text(line, search, {1: 2}, max_distance=0.6)
    assert out == "Das Modul behandelt Audio Grafik und Video. [2, S. 12]"


def test_no_chip_when_unsupported():
    line = "Diese Aussage steht so nicht in den Quellen."
    search = _searcher({"Aussage": [_hit(1, 5, "irrelevant", 0.9)]})  # too far
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6) == line


def test_short_line_untouched():
    assert _attribute_generic_text("## Überblick", _searcher({}), {1: 1}) == "## Überblick"


def test_already_cited_line_untouched():
    line = "Fakt mit Quelle hier drin. [1, S. 3 | Fakt]"
    out = _attribute_generic_text(line, _searcher({"Fakt": [_hit(1, 9, "x", 0.1)]}), {1: 1})
    assert out == line


def test_unknown_source_qnum_no_chip():
    line = "Eine inhaltlich substanzielle Aussage zum Thema."
    search = _searcher({"substanzielle": [_hit(99, 5, "Aussage zum Thema", 0.2)]})
    # source_id 99 not in the qmap -> no chip
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6) == line


def test_offset_fn_positional_ignored():
    """offset_fn may still be passed as a positional arg (legacy caller) — must not crash."""
    line = "Das Modul behandelt Audio Grafik und Video."
    search = _searcher({"Audio Grafik": [_hit(1, 12, "Audio Grafik und Video Kernmedien", 0.2)]})
    dummy_offset_fn = lambda sid, page, ln: [" @5-30 | Audio Grafik und Video"]
    out = _attribute_generic_text(line, search, {1: 2}, dummy_offset_fn, max_distance=0.6)
    # offset_fn is ignored -> nav-only chip, NOT an offset chip
    assert out == "Das Modul behandelt Audio Grafik und Video. [2, S. 12]"


# ── cross-check: only chip when the source/page was actually retrieved ────────

def test_crosscheck_accepts_retrieved_page():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 12, "x", 0.2)]}),
                                  {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == f"{line} [2, S. 12]"


def test_crosscheck_drops_unretrieved_page():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 99, "x", 0.2)]}),
                                  {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == line


def test_crosscheck_drops_source_not_in_seen_map():
    # source 5 never appeared in retrieval -> seen_pages_by_source has no key for it -> reject
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(5, 3, "x", 0.2)]}),
                                  {5: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == line


def test_crosscheck_media_passes_when_source_retrieved():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    hit = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    out = _attribute_generic_text(line, _searcher({"substanzielle": [hit]}),
                                  {3: 1}, seen_pages_by_source={3: set()}, max_distance=0.6)
    assert out == f"{line} [1, 01:32]"


def test_crosscheck_media_with_segment_page_passes():
    # REGRESSION (audio/video had NO chips): real media chunks carry a page_number
    # (transcript segment index), and _pack_context_batches tracks media sources with an
    # EMPTY seen-page set (navigated by time, not page). The cross-check must still let the
    # chip through via start_time — keying on the segment page would reject every line.
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    hit = {"source_id": 3, "page_number": 9, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    out = _attribute_generic_text(line, _searcher({"substanzielle": [hit]}),
                                  {3: 1}, seen_pages_by_source={3: set()}, max_distance=0.6)
    assert out == f"{line} [1, 01:32]"


def test_no_crosscheck_when_not_passed():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 7, "x", 0.2)]}),
                                  {1: 2}, max_distance=0.6)
    assert out == f"{line} [2, S. 7]"


def test_table_header_not_cited_and_data_chip_inside_cell():
    # A table block: header is a label (never cited), delimiter untouched, and the data
    # row's chip goes INSIDE the last cell so GFM keeps the column count (table renders).
    table = (
        "| Datum der Veranstaltung | Termin und Uhrzeit |\n"
        "|---|---|\n"
        "| 01.04.2026 | Webkonferenz Einfuehrung zum Seminar |"
    )
    out = _attribute_generic_text(
        table,
        _searcher({"Datum": [_hit(1, 6, "x", 0.2)], "Webkonferenz": [_hit(1, 6, "x", 0.2)]}),
        {1: 1}, seen_pages_by_source={1: {6}}, max_distance=0.6,
    )
    lines = out.split("\n")
    assert lines[0] == "| Datum der Veranstaltung | Termin und Uhrzeit |"  # header NOT cited
    assert lines[1] == "|---|---|"                                         # delimiter untouched
    assert lines[2].rstrip().endswith("|")                                 # row still closes with a pipe
    assert "[1, S. 6]" in lines[2]                                         # chip present
    assert lines[2].count("|") == 3                                        # same column count as a clean 2-col row


def test_guarantee_chips_grounded_answer_borderline_block():
    # Two SEPARATE bullets (= separate blocks). Answer IS grounded (bullet A at 0.2).
    # Bullet B's closest seen chunk is 0.7 (just past the normal gate) — it must STILL
    # get a chip (per-block guarantee), so no claim block is left without a source link.
    text = ("- Erste klar belegte Aussage zum Thema hier.\n"
            "- Zweite Aussage etwas vager formuliert hier.")
    search = _searcher({
        "klar belegte": [_hit(1, 5, "x", 0.2)],
        "vager formuliert": [_hit(1, 8, "y", 0.7)],
    })
    out = _attribute_generic_text(text, search, {1: 1},
                                  seen_pages_by_source={1: {5, 8}}, max_distance=0.6)
    assert "[1, S. 5]" in out
    assert "[1, S. 8]" in out          # guaranteed despite 0.7 > 0.6 gate


def test_chips_at_block_end_not_mid_bullet():
    # A bullet whose continuation spills onto a second (non-bullet) line: ALL chips go at
    # the END of the block, NEVER after the first line (mid-bullet). Same source on both
    # lines -> deduped to ONE chip at the end.
    text = ("- **Artikel 1 schützt die Würde des Menschen.**\n"
            " Dieser Artikel verpflichtet alle staatliche Gewalt dazu.")
    search = _searcher({
        "Würde des Menschen": [_hit(1, 1, "x", 0.2)],
        "staatliche Gewalt": [_hit(1, 1, "y", 0.3)],
    })
    out = _attribute_generic_text(text, search, {1: 2},
                                  seen_pages_by_source={1: {1}}, max_distance=0.6)
    lines = out.split("\n")
    assert "[2, S. 1]" not in lines[0]   # NO chip mid-bullet (after the first line)
    assert "[2, S. 1]" in lines[1]       # chip only at the block END
    assert out.count("[2, S. 1]") == 1   # deduped across the block


def test_multi_chip_two_close_pages_both_cited():
    # A synthesised line drawing from TWO retrieved pages at ~equal distance (genuine
    # co-sources, within the relative delta) -> two chips.
    line = "Eine zusammengesetzte Aussage aus mehreren Stellen zugleich."
    search = _searcher({"zusammengesetzte": [_hit(1, 5, "x", 0.30), _hit(1, 9, "y", 0.35)]})
    out = _attribute_generic_text(line, search, {1: 1},
                                  seen_pages_by_source={1: {5, 9}}, max_distance=0.6)
    assert "[1, S. 5]" in out and "[1, S. 9]" in out


def test_multi_chip_drops_far_secondary_relative_gate():
    # The HwO case: a clearly-best chunk (0.21) plus on-topic-ish near-misses (0.32) that
    # pass the absolute 0.6 gate but are NOT where the claim came from. The relative gate
    # (best + _MULTI_CHIP_MAX_DELTA) keeps ONLY the best -> one chip, no spurious extras.
    line = "Die Löschung der Eintragung in die Handwerksrolle ist unter Bedingungen möglich."
    search = _searcher({"Löschung der Eintragung": [
        _hit(1, 10, "real source", 0.21),
        _hit(1, 9, "weakly related", 0.32),
        _hit(1, 58, "off-topic noise", 0.33),
    ]})
    out = _attribute_generic_text(line, search, {1: 1},
                                  seen_pages_by_source={1: {9, 10, 58}}, max_distance=0.6)
    assert "[1, S. 10]" in out
    assert "[1, S. 9]" not in out and "[1, S. 58]" not in out
    assert out.count("[1,") == 1   # exactly one chip


def test_ungrounded_answer_borderline_gets_no_chip():
    # Honest "not contained" case: the only line's closest seen chunk is 0.7 (> gate)
    # -> the answer is NOT grounded -> no chip, even though 0.7 < the guarantee ceiling.
    line = "Diese Information ist nicht in den bereitgestellten Quellen enthalten."
    search = _searcher({"Information": [_hit(1, 5, "x", 0.7)]})
    out = _attribute_generic_text(line, search, {1: 1},
                                  seen_pages_by_source={1: {5}}, max_distance=0.6)
    assert out == line


# ── refusal detection: a "not in the sources" line is never sourced ──────────
# Even inside a COMPOUND answer where ANOTHER line grounds the answer, the refusal
# sentence must not collect the loose GUARANTEE chip (the GG51 "S. 44" bug).

# The user's exact case: a compound question answered for part 1, refused for part 2.
# Two SEPARATE bullets (= separate blocks), as the answer actually renders — so each line
# is attributed on its own and the refusal sentence carries its own (spurious) chip.
_ANSWERED = "- Die Würde des Menschen ist unantastbar laut Grundgesetz Artikel 1 Absatz 1."
_REFUSAL = "- Informationen darüber sind nicht in den bereitgestellten Quellen enthalten."
_COMPOUND = f"{_ANSWERED}\n{_REFUSAL}"


def _compound_search():
    # Part 1 grounds at 0.3. The refusal sentence carries the query topic, so its closest
    # SEEN chunk (page 44) is in the 0.6-0.85 guarantee band — exactly where the loose
    # guarantee would (wrongly) chip it.
    return _searcher({
        "Würde des Menschen": [_hit(1, 1, "Art 1 Würde des Menschen unantastbar", 0.3)],
        "Informationen darüber": [_hit(1, 44, "Kündigung am Rande erwähnt", 0.7)],
    })


def test_compound_refusal_would_be_chipped_without_detection():
    # Documents the bug: with NO refusal filter the answered part grounds the whole answer,
    # so the guarantee chips the refusal sentence -> a spurious "S. 44" on a non-answer.
    out = _attribute_generic_text(_COMPOUND, _compound_search(), {1: 1},
                                  seen_pages_by_source={1: {1, 44}}, max_distance=0.6)
    assert "S. 44" in out


def test_compound_refusal_no_chip_with_detection():
    # The fix: mark the refusal line -> it gets NO chip, while the answered part keeps S. 1.
    out = _attribute_generic_text(_COMPOUND, _compound_search(), {1: 1},
                                  seen_pages_by_source={1: {1, 44}}, max_distance=0.6,
                                  refusal_lines={_REFUSAL})
    lines = out.split("\n")
    assert "[1, S. 1]" in lines[0]          # answered part keeps its source
    assert "S. 44" not in out               # refusal sentence is never sourced
    assert lines[1] == _REFUSAL             # refusal line left verbatim


def test_refusal_line_does_not_block_real_borderline_guarantee():
    # The fix must NOT regress the deliberate guarantee for a real-but-vague claim at 0.7:
    # only the line explicitly flagged as a refusal loses its chip.
    text = ("- Erste klar belegte Aussage zum Thema hier.\n"
            "- Zweite Aussage etwas vager formuliert hier.")
    search = _searcher({
        "klar belegte": [_hit(1, 5, "x", 0.2)],
        "vager formuliert": [_hit(1, 8, "y", 0.7)],
    })
    out = _attribute_generic_text(text, search, {1: 1}, seen_pages_by_source={1: {5, 8}},
                                  max_distance=0.6, refusal_lines={_REFUSAL})  # unrelated flag
    assert "[1, S. 5]" in out and "[1, S. 8]" in out   # borderline real claim still guaranteed


# ── _refusal_lines (embedding-proximity to the no-info sentinel) ─────────────

def test_refusal_lines_flags_line_near_sentinel():
    sentinels = [[1.0, 0.0, 0.0]]
    cands = ["near sentinel line", "orthogonal content line"]
    vbl = {"near sentinel line": [0.99, 0.02, 0.0],
           "orthogonal content line": [0.0, 1.0, 0.0]}
    flagged = _refusal_lines(cands, vbl, sentinels, max_dist=0.40)
    assert "near sentinel line" in flagged
    assert "orthogonal content line" not in flagged


def test_refusal_lines_empty_without_sentinels():
    # Embed batch failed (no sentinel vectors) -> filter off, behaviour unchanged.
    assert _refusal_lines(["x"], {"x": [1.0, 0.0]}, [], max_dist=0.40) == set()


def test_refusal_lines_skips_lines_without_vectors():
    assert _refusal_lines(["x"], {}, [[1.0, 0.0]], max_dist=0.40) == set()


def test_cos_dist_degenerate_vector_is_max():
    # A zero vector never falsely reads as "near" a sentinel.
    assert _cos_dist([0.0, 0.0], [1.0, 0.0]) == 1.0


# ── is_refusal_answer (whole-answer refusal for the single-page-scope anchor) ─
# The single-page-scope path appends ONE nav anchor without per-line attribution, so it
# must itself detect an honest "not in the sources" answer and suppress the chip.

def _fake_embed(mapping, fallback):
    # Returns the mapped vector per text (sentinels + the answer), else a fallback vector.
    return lambda texts: [mapping.get(t, fallback) for t in texts]


def test_refusal_answer_near_sentinel_is_flagged():
    sentinel = "Diese Information ist nicht in den bereitgestellten Quellen enthalten."
    answer = sentinel  # the model emits the sentinel verbatim
    embed = _fake_embed({sentinel: [1.0, 0.0, 0.0]}, fallback=[1.0, 0.0, 0.0])
    assert is_refusal_answer(answer, embed, [sentinel], max_dist=0.40) is True


def test_real_answer_far_from_sentinel_keeps_anchor():
    sentinel = "Diese Information ist nicht in den bereitgestellten Quellen enthalten."
    answer = "Ab dem dritten Juli gilt die neue Prüfungsordnung mit verkürzten Fristen."
    embed = _fake_embed({sentinel: [1.0, 0.0, 0.0], answer: [0.0, 1.0, 0.0]},
                        fallback=[0.0, 1.0, 0.0])
    assert is_refusal_answer(answer, embed, [sentinel], max_dist=0.40) is False


def test_refusal_answer_no_sentinels_is_false():
    # Embed batch failed upstream / no sentinels -> never strip the anchor.
    assert is_refusal_answer("anything", lambda t: [[1.0]], [], max_dist=0.40) is False


def test_refusal_answer_embed_failure_is_false():
    def _boom(texts):
        raise RuntimeError("embed down")
    assert is_refusal_answer("x", _boom, ["s"], max_dist=0.40) is False


def test_refusal_answer_empty_text_is_false():
    assert is_refusal_answer("   ", lambda t: [[1.0]], ["s"], max_dist=0.40) is False


def test_long_dash_delimiter_row_never_cited():
    # Regression: a real GFM delimiter renders as `|--------|--------|` (Docling / most
    # models emit padded dashes). Its dedup key is the dash/pipe string itself — 18 chars,
    # OVER the substantial-line threshold — so the gate used to treat it as a claim and
    # inject a chip INSIDE the delimiter, which makes GFM stop parsing the block as a table
    # (the whole table collapses to a paragraph in the UI). The delimiter must stay verbatim.
    table = (
        "| Inhalt | Termin |\n"
        "|--------|--------|\n"
        "| Webkonferenz | 25.03.2026 |"
    )
    out = _attribute_generic_text(
        table,
        _searcher({"Inhalt": [_hit(1, 2, "x", 0.2)],
                   "Webkonferenz": [_hit(1, 2, "x", 0.2)],
                   "--------": [_hit(1, 2, "x", 0.2)]}),
        {1: 1}, seen_pages_by_source={1: {2}}, max_distance=0.6,
    )
    lines = out.split("\n")
    assert lines[1] == "|--------|--------|"   # delimiter untouched -> table still parses


# ── overview mode: no loose guarantee chip, no chip on multi-law synthesis ────

def test_names_many_laws_detects_enumeration():
    assert _names_many_laws("Form (ZPO), Marken (MarkenG) und Anwalt (BRAO).") is True
    # section-style + comma-list parens count too
    assert _names_many_laws("Doku (z. B. § 21 StBerG), Behörden (§ 55 GwG), (UWG, UmwG)") is True
    assert _names_many_laws("nur das (MarkenG) wird genannt") is False
    assert _names_many_laws("zwei (ZPO) und (InsO) reichen nicht") is False
    # a descriptive Title-case paren is NOT a law list -> single-law line keeps its chip
    assert _names_many_laws("Das Markengesetz (MarkenG) schützt Zeichen (Wortmarken, Bildmarken).") is False


def test_enum_chip_unbacked_content_gated():
    # >= 4 spelled-out items, cited chunk backs only one (Bauwirtschaft) -> unbacked.
    items = "In den Ausbildungsordnungen für Maler, Flugtechnik, Heimarbeiter, Bauwirtschaft …"
    assert _enum_chip_unbacked(items, "Bauwirtschaft Dämmungen Trockenbau Prüfung") is True
    # same shape, but the cited chunk literally enumerates all items -> in-source list, keep.
    assert _enum_chip_unbacked(items, "Maler Flugtechnik Heimarbeiter Bauwirtschaft Liste") is False
    # in-source example list (the real false-positive case) -> backed, keep the chip.
    health = "In den Gesundheitsdienstberufen (Ärzte, Zahnärzte, Tierärzte, Apotheker) ist …"
    assert _enum_chip_unbacked(health, "zuständig: Ärzte, Zahnärzte, Tierärzte, Apotheker, Kammern") is False
    # only 3 items -> below the bar, never an enumeration suppression
    assert _enum_chip_unbacked("Themen: Mathematik, Physik, Chemie.", "nichts davon") is False
    # no tight comma-run at all
    assert _enum_chip_unbacked("Anforderungen an Prüfungen, Berichte und Gewichtung.", "x") is False


def test_overview_drops_enum_chip_when_chunk_backs_one_item():
    line = "- In den Ausbildungsordnungen für Maler, Flugtechnik, Heimarbeiter, Bauwirtschaft gelten Regeln."
    search = _searcher({"Ausbildungsordnungen": [_hit(1, 36, "Bauwirtschaft Dämmungen Trockenbau", 0.2)]})
    # SPECIFIC still cites it; overview drops the chip because S.36 backs only "Bauwirtschaft".
    assert "[1, S. 36]" in _attribute_generic_text(line, search, {1: 1}, max_distance=0.6)
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6, overview=True) == line


def test_overview_keeps_enum_chip_when_chunk_backs_all_items():
    # In-source example list: the cited chunk enumerates all four professions -> chip stays.
    line = "- In den Gesundheitsdienstberufen Ärzte, Zahnärzte, Tierärzte, Apotheker sind Kammern zuständig."
    search = _searcher({"Gesundheitsdienstberufen": [
        _hit(2, 40, "zuständige Stellen Ärzte Zahnärzte Tierärzte Apotheker Kammern", 0.2)]})
    out = _attribute_generic_text(line, search, {2: 2}, max_distance=0.6, overview=True)
    assert "[2, S. 40]" in out


def test_overview_drops_loose_guarantee_chip():
    # Block 1 grounds the answer (0.2). Block 2 sits in the loose band (0.72):
    # SPECIFIC guarantees a chip there, overview drops it (a pseudo-source link).
    text = ("- Klar belegte Kernaussage zum Thema steht hier drin.\n"
            "- Eine weitere eher lose verbundene Aussage zum Sachverhalt.")
    search = _searcher({
        "Kernaussage": [_hit(1, 5, "Kernaussage Thema", 0.2)],
        "lose verbundene": [_hit(2, 8, "lose", 0.72)],
    })
    out_spec = _attribute_generic_text(text, search, {1: 1, 2: 2}, max_distance=0.6)
    assert "[2, S. 8]" in out_spec                       # guarantee chip in SPECIFIC
    out_ov = _attribute_generic_text(text, search, {1: 1, 2: 2}, max_distance=0.6, overview=True)
    assert "[2, S. 8]" not in out_ov                     # dropped in overview
    assert "[1, S. 5]" in out_ov                         # the close line still cited


def test_overview_skips_multi_law_enumeration_line():
    line = "- Regelungen zur Form von Urteilen (ZPO), zu Marken (MarkenG) und zur Anwaltschaft (BRAO)."
    search = _searcher({"Regelungen": [_hit(1, 98, "Regelungen Form Urteilen", 0.2)]})
    assert "[1, S. 98]" in _attribute_generic_text(line, search, {1: 1}, max_distance=0.6)
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6, overview=True) == line


def test_overview_keeps_close_single_source_chip():
    line = "- Das Markengesetz schützt eingetragene Zeichen als eine Marke."
    search = _searcher({"Markengesetz": [_hit(3, 8, "Markengesetz Zeichen Marke", 0.2)]})
    out = _attribute_generic_text(line, search, {3: 3}, max_distance=0.6, overview=True)
    assert "[3, S. 8]" in out


# ── NO cross-block chip dedup: each claim keeps its own best source ───────────
# Cross-block dedup was removed. It gave a shared best source to the FIRST block and left a
# later, DISTINCT claim with only a wrong leftover (the seminar/project bug: a "Theorie"
# bullet and a "Praxis" bullet both grounded in the same passage, but the second showed an
# unrelated timestamp). Genuine restatements are collapsed upstream (line-dedup +
# answer-cleanup), so a citation is never sacrificed for tidiness. Each claim keeps its own
# closest source(s) even when an earlier block already cited the same one.

def test_distinct_blocks_each_keep_shared_best_source_pdf():
    # Two DISTINCT bullets about overlapping content share the SAME best PDF page (S. 4).
    # Each must keep it; before the fix bullet 2 lost S. 4 to bullet 1 and showed only the
    # far leftover S. 9.
    b1 = "- Das wissenschaftliche Seminar vermittelt die theoretischen Grundlagen hier."
    b2 = "- Im wissenschaftlichen Projekt steht die praktische Umsetzung im Vordergrund hier."
    text = b1 + "\n\n" + b2
    search = _searcher({
        "Seminar": [_hit(1, 4, "Seminar Theorie Grundlagen", 0.20),
                    _hit(1, 5, "Einblick Wissenschaft", 0.30)],
        "Projekt": [_hit(1, 4, "Seminar Projekt Praxis Umsetzung", 0.22),
                    _hit(1, 9, "ganz anderes Thema", 0.50)],
    })
    out = _attribute_generic_text(text, search, {1: 1}, max_distance=0.6,
                                  seen_pages_by_source=None)
    first, second = out.split("\n\n")
    assert "[1, S. 4]" in first       # bullet 1 keeps the shared best source
    assert "[1, S. 4]" in second      # bullet 2 ALSO keeps it (was lost to dedup before)


def test_distinct_blocks_each_keep_shared_best_media():
    # The real screenshot case (media/timestamps): bullet 2 must keep 03:47 (its true best),
    # not fall back to the far leftover 26:04 because bullet 1 already showed 03:47.
    b1 = "- Das wissenschaftliche Seminar vermittelt die theoretischen Grundlagen hier."
    b2 = "- Im wissenschaftlichen Projekt steht die praktische Umsetzung im Vordergrund hier."
    text = b1 + "\n\n" + b2
    search = _searcher({
        "Seminar": [_hit(1, 12, "Seminar Theorie", 0.20, start=227.0),     # 03:47
                    _hit(1, 14, "Einblick", 0.30, start=245.0)],            # 04:05
        "Projekt": [_hit(1, 12, "Seminar Projekt Praxis", 0.22, start=227.0),  # 03:47 best
                    _hit(1, 80, "ganz anderes Thema", 0.50, start=1564.0)],     # 26:04 leftover
    })
    out = _attribute_generic_text(text, search, {1: 1}, max_distance=0.6,
                                  seen_pages_by_source=None)
    first, second = out.split("\n\n")
    assert "[1, 03:47]" in first
    assert "[1, 03:47]" in second     # was missing (only 26:04 showed) before the fix


def test_normal_mode_keeps_per_block_chips_no_cross_dedup():
    # Neither mode dedups chips across blocks: a source that legitimately backs two distinct
    # claims must stay linkable from BOTH, so the same chip may repeat.
    line1 = "Die Abgabe der Hausarbeit ist am 03.07.2026 faellig und steht hier."
    line2 = "Der Abgabetermin der Hausarbeit ist der 03.07.2026 wie hier erneut steht."
    text = line1 + "\n\n" + line2
    search = _searcher({"Hausarbeit": [_hit(1, 6, "Abgabe 03.07.2026", 0.20)]})
    out = _attribute_generic_text(text, search, {1: 1}, max_distance=0.6)
    assert out.count("[1, S. 6]") == 2  # per-block, not deduped across the message


# ── clause-level coverage: each FACT in a multi-fact line earns its own source ─
# One sentence can bundle several facts. The whole-line vector is closest to ONE fact's
# segment, so line-level attribution cites only that and the relative-delta gate trims the
# rest. Each fact's clause, searched on its OWN focused vector, finds its OWN segment, so
# every fact earns a chip. Punctuation-only clause split keeps this language-agnostic.

def test_clause_coverage_multi_fact_line_media():
    # The bullet-4 case (media): "... sechs bis sieben Seiten, sowie eine zwanzig Minuten
    # Praesentation ...". The whole line is closest to the Seiten segment (14:53); the
    # 20-minute presentation lives at 15:31 and was lost. Its clause must recover it.
    line = ("- Die Pruefungsleistung umfasst sechs bis sieben Seiten, "
            "sowie eine zwanzig Minuten Praesentation mit anschliessendem Fragegespraech.")
    search = _searcher({
        "Seiten": [_hit(1, 90, "sechs bis sieben Seiten Literaturverzeichnis", 0.20, start=893.0)],   # 14:53
        "zwanzig Minuten": [_hit(1, 93, "zwanzig Minuten Praesentation Fragekontext", 0.25, start=931.0)],  # 15:31
    })
    out = _attribute_generic_text(line, search, {1: 1}, max_distance=0.6, seen_pages_by_source=None)
    assert "[1, 14:53]" in out   # fact 1 (Seiten) cited as before
    assert "[1, 15:31]" in out   # fact 2 (20-min presentation) now ALSO cited (was missing)


def test_clause_coverage_multi_fact_line_pdf():
    # Same, PDF pages: each clause grounds its own page.
    line = ("- Die Pruefungsleistung umfasst sechs bis sieben Seiten, "
            "sowie eine muendliche Praesentation mit anschliessendem Fragegespraech.")
    search = _searcher({
        "Seiten": [_hit(1, 7, "sechs bis sieben Seiten", 0.20)],
        "muendliche Praesentation": [_hit(1, 12, "muendliche Praesentation Fragekontext", 0.25)],
    })
    out = _attribute_generic_text(line, search, {1: 1}, max_distance=0.6,
                                  seen_pages_by_source={1: {7, 12}})
    assert "[1, S. 7]" in out
    assert "[1, S. 12]" in out


def test_clause_coverage_no_inflation_when_clauses_share_source():
    # Both clauses ground in the SAME page -> still ONE chip (dedup by target), no inflation.
    line = "Die Regel betrifft die Anmeldung, sowie auch die Abmeldung im selben Abschnitt."
    search = _searcher({"Anmeldung": [_hit(1, 5, "Anmeldung Abmeldung Abschnitt", 0.20)],
                        "Abmeldung": [_hit(1, 5, "Anmeldung Abmeldung Abschnitt", 0.22)]})
    out = _attribute_generic_text(line, search, {1: 1}, max_distance=0.6,
                                  seen_pages_by_source={1: {5}})
    assert out.count("[1, S. 5]") == 1


