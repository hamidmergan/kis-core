"""The fusion of the two hit lists, separate from the database access."""
import pytest

from src.features.ai_assistant.repository.chunks import _rrf_fuse


VEC = [{"id": 1, "rank": 1}, {"id": 2, "rank": 2}]
KW = [{"id": 2, "rank": 1}, {"id": 3, "rank": 2}]


def test_hybrid_zaehlt_beide_wege():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="hybrid")
    assert set(scores) == {1, 2, 3}
    # A chunk in both lists leads, even though it is first in neither.
    assert scores[2] == pytest.approx(1 / 62 + 1 / 61)
    assert max(scores, key=lambda i: scores[i]) == 2


def test_dense_laesst_reine_stichworttreffer_weg():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="dense")
    assert set(scores) == {1, 2}   # chunk 3 came only via keyword
    assert scores[1] == pytest.approx(1 / 61)
    assert scores[2] == pytest.approx(1 / 62)


def test_keyword_laesst_reine_vektortreffer_weg():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="keyword")
    assert set(scores) == {2, 3}   # chunk 1 came only via vector


def test_kw_hit_meldet_nur_echte_stichworttreffer():
    # Without the keyword path nobody may count as a keyword hit.
    _, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="hybrid")
    assert kw_ids == {2, 3}
    _, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="dense")
    assert kw_ids == set()


def test_unbekannter_modus_faellt_auf():
    # A typo must not silently pass as hybrid.
    with pytest.raises(ValueError):
        _rrf_fuse(VEC, KW, rrf_k=60, mode="densee")


def test_rrf_k_veraendert_die_gewichtung():
    # A smaller k spreads the ranks more, the benchmark varies it.
    weit, _ = _rrf_fuse(VEC, [], rrf_k=60, mode="hybrid")
    eng, _ = _rrf_fuse(VEC, [], rrf_k=10, mode="hybrid")
    assert weit[1] / weit[2] < eng[1] / eng[2]
