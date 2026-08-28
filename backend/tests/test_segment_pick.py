"""The timestamp points at the spot carrying the rare word."""

from src.features.ai_assistant.routes._chips import _line_segment_start, _segment_stems
from src.features.ai_assistant.routes._text import _norm_for_match
from src.services.aia_segment_pick import best_index, rarity_weights


def _gewichte(segmente, source_id=None):
    return rarity_weights(source_id, segmente, _segment_stems, _norm_for_match)


# ── Seltenheit ──────────────────────────────────────────────────────────────

def test_seltenes_wort_wiegt_schwerer_als_haeufiges():
    segmente = [{"start": float(i), "end": float(i + 1),
                 "text": "Wir rechnen hier wieder mit Zurücklegen weiter."}
                for i in range(20)]
    segmente.append({"start": 20.0, "end": 21.0,
                     "text": "Jetzt zur hypergeometrischen Betrachtung."})
    g = _gewichte(segmente)
    assert g["hyperg"] > g["zurück"]


def test_ohne_segmente_keine_gewichte():
    assert _gewichte([]) == {}


def test_gedaechtnis_haelt_je_quelle_und_faellt_bei_anderer_laenge():
    segmente = [{"start": 0.0, "end": 1.0, "text": "Ein erster Satz zur Sache."},
                {"start": 1.0, "end": 2.0, "text": "Ein zweiter Satz zur Sache."}]
    erst = rarity_weights(4711, segmente, _segment_stems, _norm_for_match)
    assert rarity_weights(4711, segmente, _segment_stems, _norm_for_match) is erst
    laenger = segmente + [{"start": 2.0, "end": 3.0, "text": "Noch ein dritter Satz."}]
    assert rarity_weights(4711, laenger, _segment_stems, _norm_for_match) is not erst


# ── The choice of the segment ───────────────────────────────────────────────

def test_bei_gleichstand_gewinnt_nicht_das_erste_sondern_das_seltenere():
    """Two spots with two hits each, far apart, only one has the technical term."""
    treffer = [["ziehen", "zuruck"], [], [], [], ["hyperg", "vertei"], []]
    gewichte = {"ziehen": 1.0, "zuruck": 1.0, "hyperg": 5.0, "vertei": 4.0}
    assert best_index(treffer, gewichte) == 4


def test_unbekannter_stamm_zaehlt_als_selten_nicht_als_haeufig():
    """A stem that only occurs inside a compound is missing from the table."""
    treffer = [["ziehen", "zuruck"], [], [], [], ["im-kompositum"], []]
    gewichte = {"ziehen": 1.0, "zuruck": 1.0, "haeufig": 1.0, "selten": 9.0}
    assert best_index(treffer, gewichte) == 4


def test_ein_lauf_ueber_drei_segmente_schlaegt_ein_einzelnes_dichtes():
    """A spoken sentence spreads out, the timestamp belongs at its start."""
    treffer = [["a", "b"], [], [], ["c"], ["d"], ["e"]]
    gewichte = {k: 1.0 for k in "abcde"}
    assert best_index(treffer, gewichte) == 3


def test_leeres_anfangssegment_rueckt_auf_den_ersten_treffer():
    treffer = [[], ["a"], ["b"]]
    assert best_index(treffer, {"a": 1.0, "b": 1.0}) == 1


def test_ohne_segmente_index_null():
    assert best_index([], {}) == 0


# ── The measured case, through the real function ─────────────────────────────

# Verbatim from a real recording, both lines carried three word stems.
_WUK = [
    {"start": 1530.0, "end": 1548.0,
     "text": "vertütet. Die Binomialverteilung ist ein Modell für formal gesehen "
             "Bernoulli-Experimente oder in Verallgemeinerung mit entsprechenden "
             "Mehrfachergebnissen."},
    {"start": 1548.0, "end": 1557.0,
     "text": "Und etwas anschaulicher formuliert ein Modell für das Ziehen mit "
             "Zurücklegen ohne Beachtung der Reihenfolge."},
    {"start": 1557.0, "end": 1560.0, "text": "Vielen Dank."},
    {"start": 1560.0, "end": 1571.0,
     "text": "Wir werden auch da bei den Kindern deutlich gemacht, dass man das "
             "Zurücklegen nicht zu deutlich nehmen darf,"},
    {"start": 1571.0, "end": 1580.0,
     "text": "sondern immer mit einem Experiment, immer wenn man ein Experiment "
             "hat, bei dem die Wahrscheinlichkeiten auf jeder Stufe die gleichen sind,"},
    {"start": 1580.0, "end": 1583.0, "text": "dass wir dann die Epidemiaberteilung anwenden."},
    {"start": 1583.0, "end": 1590.0,
     "text": "Dann kommen wir jetzt, wenn da keine Fragen, keine Bemerkungen mehr "
             "zu sind, keine Unklarheiten,"},
    {"start": 1590.0, "end": 1593.0, "text": "zur hypergeometrischen Verteilung."},
    {"start": 1593.0, "end": 1598.0,
     "text": "Die hypergeometrische Verteilung ist ein Modell für das Ziehen."},
    {"start": 1601.0, "end": 1605.0,
     "text": "Ohne Zurücklegen, ohne Beachtung der Reihenfolge."},
    {"start": 1606.0, "end": 1613.0,
     "text": "Ein Standardbeispiel ist immer das Ziehen, das Lottospielen."},
    {"start": 1615.0, "end": 1619.0,
     "text": "Das könnt ihr sich ja hier angucken, Sonnabend sorgt das ja"},
]
_CHUNK = {
    "id": 204389,
    "source_id": 6001,
    "start_time": 1530.496,
    "end_time": 1619.695,
    "content": " ".join(s["text"] for s in _WUK),
}


def test_hypergeometrische_verteilung_zeigt_nicht_auf_mit_zuruecklegen():
    zeile = ("Die hypergeometrische Verteilung wird für das ungeordnete Ziehen ohne "
             "Zurücklegen verwendet, beispielsweise beim Lottospiel.")
    assert _line_segment_start(zeile, _CHUNK, _WUK) == 1593.0


def test_ohne_unterscheidendes_wort_bleibt_es_beim_chunk_anfang():
    """If no segment carries two word stems, there is no guessed minute."""
    assert _line_segment_start("Völlig anderes Thema.", _CHUNK, _WUK) is None
