"""Checks the layout-aware PDF reader, pure logic without a PDF file."""

from src.services.pdf_layout import (
    LineBox,
    boilerplate_keys,
    is_boilerplate,
    drop_boilerplate_lines,
    merge_rows,
    page_reading_order,
    slide_groups,
    strip_boilerplate_text,
)


def L(text, x=30.0, y=100.0):
    return LineBox(text=text, x=x, y=y)


# ── reading order ────────────────────────────────────────────────────────────

def test_reading_order_is_top_to_bottom_not_extraction_order():
    # pdfium returns the slide title last, sorted it is back on top.
    lines = [L("erster Punkt", y=390), L("zweiter Punkt", y=356), L("TITEL", y=424)]
    assert [b.text for b in page_reading_order(lines)] == ["TITEL", "erster Punkt", "zweiter Punkt"]


def test_reading_order_breaks_ties_left_to_right():
    lines = [L("rechts", x=300, y=100), L("links", x=30, y=100)]
    assert [b.text for b in page_reading_order(lines)] == ["links", "rechts"]


def test_reading_order_treats_near_equal_y_as_one_row():
    # Without tolerance the right column sorted above the left one.
    lines = [L("rechts", x=300, y=100.0), L("links", x=30, y=100.4)]
    assert [b.text for b in page_reading_order(lines)] == ["links", "rechts"]


# ── boilerplate ──────────────────────────────────────────────────────────────

def test_drops_the_line_that_stands_on_every_page():
    pages = [[L("Seminar - Lenka Kleinau"), L(f"Inhalt {i}")] for i in range(6)]
    out = drop_boilerplate_lines(pages)
    assert [[b.text for b in p] for p in out] == [[f"Inhalt {i}"] for i in range(6)]


def test_keeps_a_line_that_repeats_only_twice():
    pages = [[L("Wiederholung"), L(f"Inhalt {i}")] for i in range(2)]
    pages += [[L(f"Inhalt {i}")] for i in range(2, 8)]
    out = drop_boilerplate_lines(pages)
    assert out[0][0].text == "Wiederholung"


def test_drops_the_bare_page_number_although_it_differs_per_page():
    pages = [[L(str(i + 1)), L(f"Inhalt {i}")] for i in range(6)]
    out = drop_boilerplate_lines(pages)
    assert [[b.text for b in p] for p in out] == [[f"Inhalt {i}"] for i in range(6)]


def test_keeps_a_number_that_is_part_of_a_sentence():
    pages = [[L(f"Kapitel {i} behandelt die Grundlagen")] for i in range(6)]
    out = drop_boilerplate_lines(pages)
    assert len(out[0]) == 1


def test_leaves_a_short_document_alone():
    # Below the minimum page count a repetition says nothing.
    pages = [[L("Überschrift"), L("Inhalt")] for _ in range(3)]
    out = drop_boilerplate_lines(pages)
    assert [b.text for b in out[0]] == ["Überschrift", "Inhalt"]


def test_never_empties_a_page_completely():
    # A page made of nothing but headers keeps its lines.
    pages = [[L("Kopfzeile")] for _ in range(8)]
    out = drop_boilerplate_lines(pages)
    assert all(p for p in out)


def test_ignores_case_and_spacing_when_matching_repeats():
    pages = [[L("  Wissenschaftliches  Seminar "), L(f"x{i}")] for i in range(4)]
    pages += [[L("wissenschaftliches seminar"), L(f"y{i}")] for i in range(4)]
    out = drop_boilerplate_lines(pages)
    assert all(len(p) == 1 for p in out)


def test_strips_furniture_from_plain_text_without_reordering_it():
    pages = [[L("Kopfzeile"), L(f"Zeile {i}")] for i in range(6)]
    keys = boilerplate_keys(pages)
    text = "Kopfzeile\nErster Absatz\n7\nZweiter Absatz"
    assert strip_boilerplate_text(text, keys) == "Erster Absatz\nZweiter Absatz"


def test_a_footer_glued_together_in_the_plain_text_is_still_recognised():
    # The footer arrives as three boxes and as one glued line.
    pages_lines = [[L("Wissenschaftliches Seminar"), L("Einführung"),
                    L("Lenka Kleinau, M.Sc."), L(f"Inhalt {i}")] for i in range(6)]
    page_texts = [f"Inhalt {i}\nWissenschaftliches Seminar - Einführung - Lenka Kleinau, M.Sc."
                  for i in range(6)]
    keys = boilerplate_keys(pages_lines, page_texts)
    assert strip_boilerplate_text(page_texts[0], keys) == "Inhalt 0"


def test_the_ocr_spelling_of_the_same_footer_counts_as_the_same_line():
    # Text recognition writes the footer differently, that has to count too.
    pages_lines = [[L("Wissenschaftliches Seminar"), L(f"Inhalt {i}")] for i in range(8)]
    page_texts = [f"Inhalt {i}\nWissenschaftliches Seminar - Einführung - Lenka Kleinau, M.Sc."
                  for i in range(6)]
    page_texts += [f"Inhalt {i}\nWissenschaftliches Seminar Einführung Lenka Kleinau, M.Sc."
                   for i in range(6, 8)]
    keys = boilerplate_keys(pages_lines, page_texts)
    assert strip_boilerplate_text(page_texts[7], keys) == "Inhalt 7"


def test_the_geometry_variant_is_recognised_just_as_well():
    pages_lines = [[L("Wissenschaftliches Seminar"), L(f"Inhalt {i}")] for i in range(6)]
    page_texts = [f"Inhalt {i}\nWissenschaftliches Seminar" for i in range(6)]
    keys = boilerplate_keys(pages_lines, page_texts)
    assert is_boilerplate("Wissenschaftliches Seminar", keys)


def test_plain_text_stripping_never_empties_a_page():
    pages = [[L("Kopfzeile")] for _ in range(8)]
    keys = boilerplate_keys(pages)
    assert strip_boilerplate_text("Kopfzeile", keys) == "Kopfzeile"


# ── rows ─────────────────────────────────────────────────────────────────────

def test_a_bullet_glyph_and_its_text_become_one_line():
    # Geometry verbatim from the real deck: the glyph sits 7.8pt ABOVE its own words.
    boxes = [L("•", x=30.5, y=391.3), L("Upload-Bereich im Kurs", x=57.9, y=383.5)]
    rows = merge_rows(boxes)
    assert [b.text for b in rows] == ["• Upload-Bereich im Kurs"]


def test_a_merged_row_keeps_the_left_edge_that_carries_the_indent():
    boxes = [L("•", x=66.5, y=143.6), L("20 Minuten", x=93.7, y=138.8)]
    assert merge_rows(boxes)[0].x == 66.5


def test_neighbouring_bullets_do_not_glue_together():
    boxes = [
        L("•", x=30.5, y=391.3), L("erster Punkt", x=57.9, y=383.5),
        L("•", x=30.5, y=355.8), L("zweiter Punkt", x=57.9, y=348.0),
    ]
    assert [b.text for b in merge_rows(boxes)] == ["• erster Punkt", "• zweiter Punkt"]


def test_a_bold_word_inside_a_line_stays_in_that_line():
    boxes = [L("Der", x=30, y=200.0), L("wichtige", x=52, y=200.0), L("Teil", x=95, y=200.0)]
    assert [b.text for b in merge_rows(boxes)] == ["Der wichtige Teil"]


def test_a_dangling_glyph_is_never_dropped():
    assert [b.text for b in merge_rows([L("•", x=30, y=100)])] == ["•"]


def test_rows_come_back_top_to_bottom():
    boxes = [L("unten", y=100), L("oben", y=400)]
    assert [b.text for b in merge_rows(boxes)] == ["oben", "unten"]


# ── slide grouping ───────────────────────────────────────────────────────────

BULLET_PAGE = [
    L("ORGANISATORISCHES", x=30.1, y=502),
    L("PRÜFUNGSLEISTUNG", x=29.7, y=424),
    L("• Upload-Bereich im Kurs freigeschaltet", x=30.5, y=391),
    L("• Paper-Vorlage für die wissenschaftliche Ausarbeitung", x=30.5, y=355),
    L("• Vorgaben für die Ausarbeitung", x=30.5, y=320),
    L("• 6-7 Seiten Länge zuzüglich Literaturverzeichnis", x=66.5, y=289),
    L("• Kein: Inhalts-, Abbildungs-, Tabellenverzeichnis", x=66.5, y=259),
    L("• Präsentationsvorgaben", x=30.5, y=174),
    L("• 20 Minuten PPT-Präsentation", x=66.5, y=143),
    L("• 10 Minuten Fragerunde/Diskussion", x=66.5, y=113),
]


def test_a_top_level_bullet_keeps_its_sub_bullets_together():
    groups = slide_groups(BULLET_PAGE, min_chars=60)
    last = groups[-1]
    assert "Präsentationsvorgaben" in last
    assert "20 Minuten PPT-Präsentation" in last
    assert "10 Minuten Fragerunde/Diskussion" in last


def test_the_fact_bearing_group_is_not_diluted_by_the_rest_of_the_slide():
    groups = slide_groups(BULLET_PAGE, min_chars=60)
    last = groups[-1]
    assert "Upload-Bereich" not in last
    assert "Literaturverzeichnis" not in last


def test_every_group_carries_the_slide_title():
    groups = slide_groups(BULLET_PAGE, min_chars=60)
    assert all("PRÜFUNGSLEISTUNG" in g for g in groups)


def test_no_text_of_the_page_is_lost():
    groups = slide_groups(BULLET_PAGE, min_chars=60)
    joined = " ".join(groups)
    for box in BULLET_PAGE:
        assert box.text.lstrip("• ") in joined


def test_tiny_bullets_travel_with_a_group_that_carries_them():
    # Bullet points that are too thin travel with the next group.
    page = [
        L("TITEL", x=30, y=400),
        L("• kurz", x=30.5, y=320),
        L("• auch kurz", x=30.5, y=300),
        L("• ein Punkt mit reichlich Text, der fuer sich alleine stehen kann und genug traegt", x=30.5, y=280),
        L("• noch ein Punkt mit reichlich Text, der ebenfalls fuer sich alleine stehen kann", x=30.5, y=260),
    ]
    groups = slide_groups(page, min_chars=60)
    assert len(groups) == 2
    assert "kurz" in groups[0] and "auch kurz" in groups[0]
    assert all(len(g) >= 60 for g in groups)


def test_a_thin_group_next_to_a_full_one_is_not_left_stranded():
    # Without a floor, fragments of 29 characters would stay in the index.
    page = [
        L("• PERSÖNLICHER ZEIT UND MEILENSTEINPLAN", x=30.5, y=400),
        L("• Zeit und Meilensteinplan erstellen", x=30.5, y=380),
        L("• Realistische Ziele stecken", x=66.5, y=360),
        L("• Pufferzeiten einplanen und Fortschritt regelmaessig kontrollieren", x=66.5, y=340),
        L("• Zeitfresser und Gegenmittel", x=30.5, y=300),
    ]
    groups = slide_groups(page, min_chars=120)
    assert all(len(g) >= 120 for g in groups)


def test_no_group_lands_under_the_floor_it_was_cut_for():
    # The floor counts the finished text including the title.
    page = [
        L("ORGANISATORISCHES PRÜFUNGSLEISTUNG", x=30, y=400),
        L("• 20 Minuten Präsentation", x=30.5, y=300),
        L("• 10 Minuten anschließende Fragerunde", x=30.5, y=280),
        L("• Termine werden individuell während der Prüfungswochen vereinbart", x=30.5, y=260),
    ]
    assert all(len(g) >= 120 for g in slide_groups(page, min_chars=120))


def test_a_page_that_folds_back_into_one_group_gains_nothing():
    # If only one group remains there is nothing to do.
    page = [
        L("TITEL", x=30, y=400),
        L("• kurz", x=30.5, y=300),
        L("• auch kurz", x=30.5, y=280),
    ]
    assert slide_groups(page, min_chars=60) == []


def test_a_page_without_bullets_yields_nothing_to_group():
    page = [L("Dies ist ein Fließtext ohne jede Aufzählung.", x=30, y=300)]
    assert slide_groups(page, min_chars=60) == []


def test_a_page_with_a_single_bullet_is_left_to_the_normal_splitter():
    page = [L("TITEL", x=30, y=400), L("• nur ein Punkt", x=30.5, y=300)]
    assert slide_groups(page, min_chars=60) == []


def test_dashes_and_digits_count_as_bullets_too():
    page = [
        L("TITEL", x=30, y=400),
        L("- erster Punkt mit genug Text um zu zaehlen", x=30.5, y=300),
        L("- zweiter Punkt mit genug Text um zu zaehlen", x=30.5, y=280),
        L("- dritter Punkt mit genug Text um zu zaehlen", x=30.5, y=260),
    ]
    assert len(slide_groups(page, min_chars=40)) > 1


# ── prose pages must stay whole ──────────────────────────────────────────────

def test_a_prose_page_with_a_few_dashes_is_not_a_slide():
    # A prose page with a few dashes must not be cut.
    page = [L("Art 144 (1) " + "Dieses Grundgesetz bedarf der Annahme durch die Volksvertretungen. " * 12,
              x=30, y=500)]
    page += [L(f"Zwischentext ohne Aufzählungszeichen Nummer {i}, in ganzen Sätzen.", x=30, y=480 - i * 10)
             for i in range(10)]
    page += [L(f"- EinigVtr v. 31.8.1990 II 889, Randnotiz {i}", x=49, y=360 - i * 10) for i in range(4)]
    assert slide_groups(page, min_chars=120) == []


def test_a_long_lead_paragraph_is_never_used_as_a_title():
    lead = "Dieser Absatz ist viel zu lang um eine Überschrift zu sein. " * 4
    page = [L(lead, x=30, y=500)]
    page += [L(f"• Punkt {i}: " + "mit reichlich Text, damit diese Gruppe die Untergrenze "
                "aus eigener Kraft ueberschreitet und nicht gefaltet wird. " * 2,
                x=30.5, y=400 - i * 20) for i in range(4)]
    groups = slide_groups(page, min_chars=120)
    assert groups
    # it may lead into the FIRST group, but it must not ride on every one of them
    assert sum(lead[:40] in g for g in groups) == 1
    # and it must not be lost either
    assert lead[:40] in groups[0]


def test_a_short_heading_still_rides_along():
    assert all("PRÜFUNGSLEISTUNG" in g for g in slide_groups(BULLET_PAGE, min_chars=60))
