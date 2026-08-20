"""Die Verschmelzung der beiden Trefferlisten, getrennt vom Datenbankzugriff.

Warum es das gibt. ``hybrid_search_chunks`` fragt zwei Wege ab (Vektor und
Stichwort) und rechnet die Plaetze per RRF zusammen. Um zu messen, WELCHER der
beiden Wege das Ergebnis traegt, muss man je einen davon abschalten koennen.
Diese Tests halten fest, was ``mode`` dabei bedeutet.

Ohne den Messsatz waere das eine Vermutung: im Video, aus dem die Idee stammt,
hat das Zusammenlegen die reine Vektorsuche sogar VERSCHLECHTERT, weil der
Stichwortweg auf jenen Daten schwach war. Ob das bei uns auch so ist, sagt erst
eine Zahl. Siehe backend/scripts/rag_retrieval_eval.py --vergleich.
"""
import pytest

from src.features.ai_assistant.repository.chunks import _rrf_fuse


VEC = [{"id": 1, "rank": 1}, {"id": 2, "rank": 2}]
KW = [{"id": 2, "rank": 1}, {"id": 3, "rank": 2}]


def test_hybrid_zaehlt_beide_wege():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="hybrid")
    assert set(scores) == {1, 2, 3}
    # Chunk 2 steht in beiden Listen (Vektor Platz 2, Stichwort Platz 1), bekommt
    # also beide Beitraege und fuehrt, obwohl er in keiner der beiden Listen vorn steht.
    # Genau das ist der Zweck der Verschmelzung.
    assert scores[2] == pytest.approx(1 / 62 + 1 / 61)
    assert max(scores, key=lambda i: scores[i]) == 2


def test_dense_laesst_reine_stichworttreffer_weg():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="dense")
    assert set(scores) == {1, 2}   # Chunk 3 kam nur ueber das Stichwort
    assert scores[1] == pytest.approx(1 / 61)
    assert scores[2] == pytest.approx(1 / 62)


def test_keyword_laesst_reine_vektortreffer_weg():
    scores, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="keyword")
    assert set(scores) == {2, 3}   # Chunk 1 kam nur ueber den Vektor


def test_kw_hit_meldet_nur_echte_stichworttreffer():
    # ``kw_hit`` trennt "steht das Wort wirklich drin" von "liegt semantisch nahe".
    # Bei mode="dense" gibt es keinen Stichwortweg, also darf niemand als
    # Stichworttreffer gelten.
    _, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="hybrid")
    assert kw_ids == {2, 3}
    _, kw_ids = _rrf_fuse(VEC, KW, rrf_k=60, mode="dense")
    assert kw_ids == set()


def test_unbekannter_modus_faellt_auf():
    # Ein Tippfehler im Messskript darf nicht stillschweigend als "hybrid"
    # durchgehen, sonst vergleicht man zwei gleiche Laeufe.
    with pytest.raises(ValueError):
        _rrf_fuse(VEC, KW, rrf_k=60, mode="densee")


def test_rrf_k_veraendert_die_gewichtung():
    # Kleineres k spreizt die Plaetze staerker. Der Messsatz variiert das.
    weit, _ = _rrf_fuse(VEC, [], rrf_k=60, mode="hybrid")
    eng, _ = _rrf_fuse(VEC, [], rrf_k=10, mode="hybrid")
    assert weit[1] / weit[2] < eng[1] / eng[2]
