# backend/tests/test_citation_match.py
from src.features.ai_assistant.routes._citation_match import Unit, match_query, match_query_multi


def _seg(text, start):
    return Unit(page=None, start_time=start, end_time=start + 10, norm_text=None, raw_text=text)


def test_exact_substring_wins():
    units = [_seg("the scientific seminar is in the second semester", 227.0),
             _seg("citation styles apae and ieee", 60.0)]
    r = match_query("scientific seminar", units)
    assert r.match_type == "exact"
    assert r.unit.start_time == 227.0


def test_fuzzy_matches_paraphrase():
    units = [_seg("literature database management tools zotero citavi mendeley", 905.0),
             _seg("where to research web books journals", 60.0)]
    r = match_query("literature management software zotero citavi", units)
    assert r.match_type == "fuzzy"
    assert r.unit.start_time == 905.0


def test_ambiguous_below_margin_returns_none():
    units = [_seg("peer review feedback among students", 476.0),
             _seg("peer review feedback among students again", 1650.0)]
    r = match_query("peer review feedback students", units)
    assert r.match_type == "none"  # two near-equal hits -> not confident


def test_no_tokens_returns_none():
    units = [_seg("anything", 1.0)]
    assert match_query("", units).match_type == "none"


def test_typed_pos_disambiguates_exact_duplicates():
    units = [_seg("peer review", 476.0), _seg("peer review", 1650.0)]
    r = match_query("peer review", units, typed_pos=1600.0)
    assert r.unit.start_time == 1650.0


def _pg(text, page):
    return Unit(page=page, start_time=None, end_time=None, norm_text=None, raw_text=text)


def test_fuzzy_near_tie_typed_pos_picks_nearest_with_its_own_score():
    # query has 7 tokens; A matches 6/7≈0.857, B matches 5/7≈0.714 -> within the 0.15 margin.
    # Not an exact substring (last token "golf" is absent), so the fuzzy near-tie branch runs.
    units = [_seg("alpha bravo charlie delta echo foxtrot", 100.0),
             _seg("alpha bravo charlie delta echo", 1600.0)]
    r = match_query("alpha bravo charlie delta echo foxtrot golf", units, typed_pos=1500.0)
    assert r.match_type == "fuzzy"
    assert r.unit.start_time == 1600.0          # nearest to typed_pos
    assert abs(r.score - 5 / 7) < 1e-9          # score is the CHOSEN unit's, not the best (6/7)


def test_typed_pos_disambiguates_page_units():
    # exercises the page branch of _nearest (start_time is None -> uses page)
    units = [_pg("zotero citavi", 13), _pg("zotero citavi", 15)]
    r = match_query("zotero citavi", units, typed_pos=15)
    assert r.unit.page == 15


def test_tokenizer_splits_punctuation_and_hyphens():
    # Fuzzy must match across hyphen/punctuation differences: query "review prozess
    # teilnehmen" vs unit text "Review-Prozess teilzunehmen." — review+prozess match.
    units = [_seg("gerade an diesem review-prozess, dringend.", 100.0),
             _seg("etwas ganz anderes ohne bezug hier", 900.0)]
    r = match_query("review prozess dringend", units)
    assert r.unit.start_time == 100.0
    assert r.match_type in ("exact", "fuzzy")


def _pg2(text, page):
    return Unit(page=page, start_time=None, end_time=None, norm_text=None, raw_text=text)


def test_multi_returns_one_per_near_tie_page():
    # Same text on two pages -> both returned (near-tie), best first, capped at 2.
    units = [_pg2("audio engineering society aes", 440),
             _pg2("audio engineering society norm", 441),
             _pg2("voellig anderes thema", 12)]
    rs = match_query_multi("audio engineering society", units)
    pages = {r.unit.page for r in rs}
    assert pages == {440, 441}
    assert len(rs) == 2


def test_multi_single_clear_winner():
    # A clear winner returns exactly one result; a weakly-overlapping page is excluded.
    units = [_pg2("zotero citavi literaturverwaltung mendeley tools", 15),
             _pg2("ganz anderes thema ohne bezug", 3)]
    rs = match_query_multi("zotero citavi literaturverwaltung", units)
    assert len(rs) == 1 and rs[0].unit.page == 15


def test_multi_below_threshold_returns_empty():
    units = [_pg2("komplett unzusammenhaengender text", 5)]
    assert match_query_multi("voellig anderes hier", units) == []


def test_multi_dedups_same_page():
    # Two chunks on the SAME page collapse to one result (no double chip per page).
    units = [_pg2("audio engineering society aes", 440),
             _pg2("audio engineering society again", 440)]
    rs = match_query_multi("audio engineering society", units)
    assert len(rs) == 1 and rs[0].unit.page == 440


def test_stem_match_media_morphological_variant():
    # Media paraphrase: the bullet says "Schneeballsystem", the transcript says
    # "Schneeballprinzip" (shared stem). With stem matching the segment is found.
    units = [_seg("von einer quelle ausgehend schneeballprinzip weitere literatur", 1040.0),
             _seg("ganz anderes thema ohne jeden bezug hier", 60.0)]
    r = match_query("schneeballsystem literatur quelle", units, stem_match=True)
    assert r.unit is not None and r.unit.start_time == 1040.0


def test_stem_match_catches_inflection_compound():
    # "Qualitätsprüfung" (bullet) vs "Qualität" (transcript) -> shared stem.
    units = [_seg("achtet auf die qualität der ausgewaehlten quellen genau", 320.0)]
    r = match_query("qualitätsprüfung der quellen", units, stem_match=True)
    assert r.unit is not None and r.unit.start_time == 320.0


def test_stem_match_off_by_default_keeps_exact():
    # Default (PDF path): NO stem matching -> the morphological variant must not match.
    units = [_pg("von einer quelle ausgehend schneeballprinzip weitere literatur", 5)]
    r = match_query("schneeballsystem voellig andere fremde woerter", units)
    assert r.unit is None   # exact-only: 'schneeballsystem' != 'schneeballprinzip'


def test_stem_match_short_tokens_not_overmatched():
    # Short tokens (<5) require exact match -> 'kosten' must NOT stem-match 'kostuem'.
    units = [_seg("das kostuem war wirklich sehr teuer damals", 10.0)]
    r = match_query("kosten preis betrag", units, stem_match=True)
    assert r.unit is None


def test_stem_match_no_false_tie_on_short_shared_prefix():
    # 'schnell' shares only the 5-char fragment 'schne' with 'schneeball...' — that is
    # NOT the same stem. A too-loose prefix rule would make both segments tie at 1.0
    # and drop the chip. The real 'Schneeballprinzip' segment must win uniquely.
    units = [_seg("von einer quelle ausgehend schneeballprinzip relevante literatur", 2329.0),
             _seg("das geht schnell und einfach voran im seminar", 60.0)]
    r = match_query("schneeballsystem", units, stem_match=True)
    assert r.unit is not None and r.unit.start_time == 2329.0
