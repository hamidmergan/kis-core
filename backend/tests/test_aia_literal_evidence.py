"""May a more distant chunk get a citation anyway?"""

from src.services.aia_literal_evidence import (
    adds_literal_evidence,
    distinctive_tokens,
    figure_runs,
    lookup_figures,
)

SPRECHSTUNDE = "**Wöchentliche Sprechstunde**: Mittwochs von 17:30 bis 18:30 Uhr"
PDF_KONTAKT = ("Lenka Kleinau • Kontakt: • Fachforum • E-Mail: lenka.kleinau@th-luebeck.de "
               "• Wöchentliche Sprechstunde (Mittwoch 17:30-18:30 Uhr) MENTORIN UND TUTORIN")
VIDEO_0649 = ("Genau, das ist so ein bisschen der Plan. Heute, nach diesen drei Inputblöcken, "
              "wird es dann mittwochs immer eine offene Sprechstunde geben. Da können Sie "
              "hinkommen und Fragen stellen. Sie müssen sich dafür nicht anmelden.")


def test_the_slide_that_states_the_time_earns_its_chip():
    assert adds_literal_evidence(SPRECHSTUNDE, PDF_KONTAKT, VIDEO_0649, [VIDEO_0649, PDF_KONTAKT])


def test_a_passage_that_only_talks_around_it_earns_nothing():
    assert not adds_literal_evidence(SPRECHSTUNDE, VIDEO_0649, PDF_KONTAKT, [PDF_KONTAKT, VIDEO_0649])


def test_a_thirty_in_a_clock_time_is_not_the_thirty_of_thirty_minutes():
    # Numbers are compared as whole sequences, never as fragments.
    line = "Die gesamte Zeit ist 30 Minuten."
    clock = "Die Sprechstunde ist mittwochs von 17:30 bis 18:30 Uhr im Fachforum."
    other = "Ein ganz anderer Text über Literaturrecherche und Fachzeitschriften."
    assert not adds_literal_evidence(line, clock, other, [other, clock])


def test_figures_keep_their_shape():
    assert figure_runs("von 17:30 bis 18:30 Uhr am 03.07.2026, 6-7 Seiten") == {
        "17:30", "18:30", "03.07.2026", "6-7"}


def test_two_words_matched_across_inflection_are_evidence():
    line = "Es gibt eine Fragerunde und eine Diskussion nach dem Vortrag."
    holds = "Präsentationsvorgaben: 20 Minuten PPT-Präsentation, 10 Minuten Fragerunden/Diskussionen"
    talks = "Danach kann man noch Fragen stellen, wenn man möchte, ganz zwanglos."
    assert adds_literal_evidence(line, holds, talks, [talks, holds])


def test_a_single_shared_word_is_not_evidence():
    # One word apart is a coincidence: it is how a filler adverb bought a chip.
    line = "Es gibt eine Fragerunde nach dem Vortrag."
    holds = "Präsentationsvorgaben: 20 Minuten PPT-Präsentation, 10 Minuten Fragerunden"
    talks = "Danach kann man noch Fragen stellen, wenn man möchte, ganz zwanglos."
    assert not adds_literal_evidence(line, holds, talks, [talks, holds])


def test_the_two_ends_of_a_range_are_found_written_apart():
    assert "17:30" in figure_runs("Sprechstunde (Mittwoch 17:30-18:30 Uhr)")
    assert "18:30" in figure_runs("Sprechstunde (Mittwoch 17:30-18:30 Uhr)")


def test_a_bare_digit_of_a_range_is_not_indexed():
    # "6-7 Seiten" must not be answerable by a stray 7 somewhere else.
    assert figure_runs("6-7 Seiten") == {"6-7"}


def test_a_token_the_whole_candidate_set_carries_says_nothing():
    # "Seminar" in every candidate cannot distinguish one from another.
    line = "Das Seminar behandelt das Seminar und nochmals das Seminar."
    a = "Seminar eins, mit viel Text drumherum und weiteren Worten."
    b = "Seminar zwei, mit viel Text drumherum und weiteren Worten."
    assert not adds_literal_evidence(line, a, b, [a, b])


def test_only_what_the_best_chunk_lacks_counts():
    # The primary already carries the time, so a second chunk repeating it adds nothing.
    line = "Die Sprechstunde ist mittwochs von 17:30 bis 18:30 Uhr."
    primary = "Sprechstunde: Mittwoch 17:30-18:30 Uhr, ohne Anmeldung, im Fachforum."
    other = "Sprechstunde 17:30-18:30 Uhr steht auch hier nochmal in dieser Quelle."
    assert not adds_literal_evidence(line, other, primary, [primary, other])


def test_a_line_without_anything_distinctive_earns_nothing():
    assert not adds_literal_evidence("Das ist so.", "Ein Text.", "Ein anderer Text.",
                                     ["Ein Text.", "Ein anderer Text."])


def test_distinctive_tokens_drop_what_the_corpus_is_full_of():
    line = "Die Sprechstunde ist um 17:30 Uhr im Fachforum."
    corpus = [f"Sprechstunde Nummer {i}, und noch etwas Text dazu." for i in range(12)]
    corpus.append("Sprechstunde dort um 17:30 Uhr")
    words, figures = distinctive_tokens(line, corpus)
    assert "sprechstunde" not in words
    assert "17:30" in figures
    assert "fachforum" in words


def test_a_filler_adverb_is_not_evidence():
    # Measured against the whole corpus a filler word is clearly common.
    line = "Insgesamt 30 Minuten, aufgeteilt in 20 Minuten Vortrag."
    corpus = [f"Insgesamt geht es hier um Thema {i} und weiteres Drumherum." for i in range(12)]
    chunk, primary = corpus[0], "Etwas ganz anderes ohne dieses Wort."
    assert not adds_literal_evidence(line, chunk, primary, corpus)


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
