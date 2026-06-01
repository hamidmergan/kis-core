# backend/tests/test_citation_match.py
from src.features.ai_assistant.routes._citation_match import Unit, match_query


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
