"""May a more distant chunk get a citation anyway?"""

from src.services.aia_literal_evidence import (
    distinctive_tokens,
    figure_runs,
    lookup_figures,
)


def test_figures_keep_their_shape():
    assert figure_runs("von 17:30 bis 18:30 Uhr am 03.07.2026, 6-7 Seiten") == {
        "17:30", "18:30", "03.07.2026", "6-7"}


def test_the_two_ends_of_a_range_are_found_written_apart():
    assert "17:30" in figure_runs("Sprechstunde (Mittwoch 17:30-18:30 Uhr)")
    assert "18:30" in figure_runs("Sprechstunde (Mittwoch 17:30-18:30 Uhr)")


def test_a_bare_digit_of_a_range_is_not_indexed():
    # "6-7 Seiten" must not be answerable by a stray 7 somewhere else.
    assert figure_runs("6-7 Seiten") == {"6-7"}


def test_distinctive_tokens_drop_what_the_corpus_is_full_of():
    line = "Die Sprechstunde ist um 17:30 Uhr im Fachforum."
    corpus = [f"Sprechstunde Nummer {i}, und noch etwas Text dazu." for i in range(12)]
    corpus.append("Sprechstunde dort um 17:30 Uhr")
    words, figures = distinctive_tokens(line, corpus)
    assert "sprechstunde" not in words
    assert "17:30" in figures
    assert "fachforum" in words


# ── which figures are worth looking up ───────────────────────────────────────

CORPUS = [f"Irgendein Kapitel {i} mit Text, das von 2026 handelt und weiterem." for i in range(20)]


def test_a_clock_time_is_looked_up():
    assert "17:30" in lookup_figures("mittwochs von 17:30 bis 18:30 Uhr", CORPUS)


def test_a_date_is_looked_up():
    assert "03.07.2026" in lookup_figures("Abgabe der Hausarbeit am 03.07.2026", CORPUS)


def test_a_bare_count_is_not_looked_up():
    # Only structured numbers are worth looking up.
    assert lookup_figures("Die Präsentation dauert 20 Minuten und hat 7 Folien", CORPUS) == []


def test_a_year_everyone_carries_is_not_looked_up():
    # It stands in every second chunk of this corpus, so it distinguishes nothing.
    assert "2026" not in lookup_figures("Das Seminar läuft im Jahr 2026", CORPUS)


def test_a_range_is_looked_up_whole_and_by_its_ends():
    got = lookup_figures("Sprechstunde 17:30-18:30 Uhr", CORPUS)
    assert "17:30-18:30" in got and "17:30" in got


def test_at_most_a_handful_is_looked_up():
    line = "Termine: 01.04.2026, 15.04.2026, 22.04.2026, 28.05.2026, 29.05.2026, 03.07.2026"
    assert len(lookup_figures(line, CORPUS)) <= 3


# ── Pin words: what a claim hangs on ────────────────────────────────────────

# Reported case: two chips hung on the aside instead of on the claim.
_KORPUS = [
    "Wir machen nächste Woche noch affine Schifren. Dann haben wir noch Zeit, "
    "da machen wir noch eine Fragestunde. Da können Sie sich die Sachen angucken.",
    "Ich habe in der letzten Webkonferenz gesagt, was drankommt. Und dann kommt "
    "hier die affine Chiffre dran.",
    "Das ist im Grunde die Verallgemeinerung des Rechnens mit Rest. Und dann so "
    "gängige Verschlüsselungsverfahren, das Diffie-Hellmann-Verfahren.",
] + [f"Wir rechnen jetzt das Beispiel {i} zusammen durch und gucken uns das an."
     for i in range(20)]

_ZEILE = ("Es wird erwähnt, dass nach der Behandlung von affinen Chiffren noch Zeit "
          "für eine Fragestunde bleibt")


def test_pin_wort_ist_das_seltene_lange_wort():
    from src.services.aia_literal_evidence import pin_words
    assert pin_words(_ZEILE, _KORPUS) == {"fragestunde"}


def test_kurze_woerter_werden_nie_pin():
    """'Chiffren' has eight characters and fails, even though it is rare."""
    from src.services.aia_literal_evidence import pin_words
    assert "chiffren" not in pin_words(_ZEILE, _KORPUS)


def test_haeufiges_wort_wird_nie_pin():
    from src.services.aia_literal_evidence import pin_words
    zeile = "Wir rechnen das Beispiel zusammen durch und gucken uns die Sache an."
    assert pin_words(zeile, _KORPUS) == set()


def test_ohne_genug_material_gibt_es_keine_pin_woerter():
    """Below eight texts rarity cannot be measured, then nothing changes."""
    from src.services.aia_literal_evidence import pin_words
    assert pin_words(_ZEILE, _KORPUS[:3]) == set()


def test_traegt_der_chunk_das_pin_wort():
    from src.services.aia_literal_evidence import carries_pin
    assert carries_pin("fragestunde", _KORPUS[0])
    assert not carries_pin("fragestunde", _KORPUS[1])
    assert not carries_pin("fragestunde", _KORPUS[2])
