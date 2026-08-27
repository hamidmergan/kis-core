"""The metric of the retrieval benchmark: a rank becomes a score."""
import math

import pytest

from scripts.rag_retrieval_eval import _ndcg_at_k, _mittel_ndcg


def test_platz_eins_ist_die_volle_punktzahl():
    assert _ndcg_at_k(1) == pytest.approx(1.0)


def test_platz_drei_gibt_die_haelfte():
    # 1 / log2(4) = 1/2, a good anchor for how strongly it is damped.
    assert _ndcg_at_k(3) == pytest.approx(0.5)


def test_die_daempfung_faellt_monoton():
    werte = [_ndcg_at_k(p) for p in range(1, 11)]
    assert werte == sorted(werte, reverse=True)
    assert werte[-1] == pytest.approx(1 / math.log2(11))


def test_jenseits_der_schranke_zaehlt_nichts():
    # What sits behind the cut-off the model does not see and counts zero.
    assert _ndcg_at_k(11) == 0.0
    assert _ndcg_at_k(80) == 0.0


def test_nicht_gefunden_zaehlt_wie_nicht_vorhanden():
    assert _ndcg_at_k(None) == 0.0


def test_schranke_ist_einstellbar():
    assert _ndcg_at_k(11, k=20) == pytest.approx(1 / math.log2(12))
    assert _ndcg_at_k(21, k=20) == 0.0


def test_mittel_ueber_mehrere_faelle():
    # One hit at rank 1, one at rank 3, one not at all.
    assert _mittel_ndcg([1, 3, None]) == pytest.approx((1.0 + 0.5 + 0.0) / 3)


def test_mittel_ohne_faelle_ist_null_statt_absturz():
    # The comparison run must not die on an empty --only.
    assert _mittel_ndcg([]) == 0.0
