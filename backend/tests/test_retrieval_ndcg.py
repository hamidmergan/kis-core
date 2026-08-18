"""Die Kennzahl des Abruf-Messsatzes: aus einem Platz wird eine Punktzahl.

Warum eine Zahl und nicht nur "gefunden ja/nein". Ohne sie kann man zwei Staende
nur an einer Liste von Plaetzen vergleichen, und eine Verschiebung von Platz 2 auf
Platz 4 faellt dabei durch. Genau solche feinen Verschiebungen entscheiden aber,
ob die tragende Stelle spaeter noch ins Budget passt.

NDCG@10 ist der uebliche Massstab dafuer. Bei uns hat fast jeder Fall GENAU EINE
richtige Stelle, deshalb faellt die ideale Rangfolge auf 1 zusammen und die Formel
verkuerzt sich auf ``1 / log2(platz + 1)``. Das ist rechnerisch dasselbe wie der
mittlere gedaempfte Kehrwert des Platzes, der Name bleibt trotzdem richtig und
macht die Zahl mit der Literatur vergleichbar.
"""
import math

import pytest

from scripts.rag_retrieval_eval import _ndcg_at_k, _mittel_ndcg


def test_platz_eins_ist_die_volle_punktzahl():
    assert _ndcg_at_k(1) == pytest.approx(1.0)


def test_platz_drei_gibt_die_haelfte():
    # 1 / log2(4) = 1/2. Ein guter Anker fuer das Gefuehl, wie stark gedaempft wird.
    assert _ndcg_at_k(3) == pytest.approx(0.5)


def test_die_daempfung_faellt_monoton():
    werte = [_ndcg_at_k(p) for p in range(1, 11)]
    assert werte == sorted(werte, reverse=True)
    assert werte[-1] == pytest.approx(1 / math.log2(11))


def test_jenseits_der_schranke_zaehlt_nichts():
    # Was auf Platz 11 steht, sieht das Modell nicht. Halbe Punkte dafuer waeren
    # eine Luege ueber den Nutzen.
    assert _ndcg_at_k(11) == 0.0
    assert _ndcg_at_k(80) == 0.0


def test_nicht_gefunden_zaehlt_wie_nicht_vorhanden():
    assert _ndcg_at_k(None) == 0.0


def test_schranke_ist_einstellbar():
    assert _ndcg_at_k(11, k=20) == pytest.approx(1 / math.log2(12))
    assert _ndcg_at_k(21, k=20) == 0.0


def test_mittel_ueber_mehrere_faelle():
    # Ein Treffer auf Platz 1, einer auf Platz 3, einer gar nicht.
    assert _mittel_ndcg([1, 3, None]) == pytest.approx((1.0 + 0.5 + 0.0) / 3)


def test_mittel_ohne_faelle_ist_null_statt_absturz():
    # Der Vergleichslauf darf an einem leeren --only nicht sterben.
    assert _mittel_ndcg([]) == 0.0
