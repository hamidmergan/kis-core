"""Mind map context: every source contributes its outline, the rest of the budget is depth."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


def _chunk(page: int, text: str) -> dict:
    return {"page_number": page, "content": text}


def _prose(pages: int, chars: int = 500) -> list[dict]:
    return [_chunk(p, "Dies ist ein ganzer Satz mit Punkt am Ende. " * (chars // 44))
            for p in range(1, pages + 1)]


def _with_headings(pages: int) -> list[dict]:
    out = []
    for p in range(1, pages + 1):
        out.append(_chunk(p, f"Kapitel {p}\nDies ist ein ganzer Satz mit einem Punkt am Ende. " * 12))
    return out


def _sources(*chunk_lists) -> list[tuple[int, str, list[dict]]]:
    return [(i, f"q{i}.pdf", chunks) for i, chunks in enumerate(chunk_lists, start=1)]


def _labels(picked) -> list[str]:
    return [label for _sid, label, _chunks in picked]


@pytest.fixture
def budget(monkeypatch):
    state = {"budget": 20000}
    monkeypatch.setattr(cb, "tool_context_budget", lambda: state["budget"])
    return state


# --- outline_chunks ---------------------------------------------------------

def test_a_short_line_without_final_punctuation_is_a_heading():
    out = cb.outline_chunks([_chunk(3, "Qualifikationsziele\nDas Modul vermittelt die Grundlagen.")])
    assert [(c["page_number"], c["content"]) for c in out] == [(3, "Qualifikationsziele")]


def test_a_full_sentence_is_no_heading():
    assert cb.outline_chunks([_chunk(1, "Das Modul vermittelt die Grundlagen des Projektmanagements.")]) == []


def test_a_line_of_digits_alone_is_no_heading():
    assert cb.outline_chunks([_chunk(1, "12\n34")]) == []


def test_a_very_long_line_is_no_heading():
    assert cb.outline_chunks([_chunk(1, "Wort " * 40)]) == []


# --- fill_sources_with_outline ----------------------------------------------

def test_every_source_is_represented_even_when_the_budget_is_tiny(budget):
    budget["budget"] = 3000
    picked = cb.fill_sources_with_outline(_sources(_with_headings(40), _with_headings(40),
                                                   _with_headings(40)))
    assert _labels(picked) == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_a_source_without_headings_still_contributes_its_beginning(budget):
    budget["budget"] = 3000
    picked = cb.fill_sources_with_outline(_sources(_with_headings(40), _prose(40)))
    letzte = [chunks for _sid, label, chunks in picked if label == "q2.pdf"][0]
    assert letzte and letzte[0]["page_number"] == 1


def test_the_rest_of_the_budget_goes_into_depth_from_the_front(budget):
    budget["budget"] = 30000
    picked = cb.fill_sources_with_outline(_sources(_with_headings(40), _with_headings(40)))
    erste, zweite = [len(chunks) for _sid, _label, chunks in picked]
    assert erste > zweite


def test_the_result_keeps_the_selection_order(budget):
    picked = cb.fill_sources_with_outline(_sources(_with_headings(5), _with_headings(40)))
    assert _labels(picked) == ["q1.pdf", "q2.pdf"]


def test_a_source_that_fits_whole_is_not_reduced_to_its_outline(budget):
    budget["budget"] = 100000
    picked = cb.fill_sources_with_outline(_sources(_with_headings(3)))
    assert len(picked[0][2]) == 3


def test_no_sources_means_no_context(budget):
    assert cb.fill_sources_with_outline([]) == []


def test_a_source_without_headings_is_not_sent_twice(budget):
    # Its base is the front of the source, and depth starts at the front too.
    budget["budget"] = 10000
    picked = cb.fill_sources_with_outline(_sources(_prose(40)))
    seiten = [c["page_number"] for c in picked[0][2]]
    assert len(seiten) == len(set(seiten))


# --- page chrome ------------------------------------------------------------

def test_a_line_that_comes_back_on_every_page_is_kept_once():
    chunks = [_chunk(p, f"Thema {p} des Tages\nMit KI erzeugtes Demo-Material Seite {p}")
              for p in range(1, 9)]
    zeilen = [c["content"] for c in cb.outline_chunks(chunks)]
    assert sum(1 for z in zeilen if z.startswith("Mit KI")) == 1


_PARAGRAFEN = ["Begriffsbestimmungen", "Zuständigkeit", "Antragsfrist", "Nachweise",
               "Widerspruch", "Kosten", "Übergangsregelung", "Inkrafttreten"]


def test_numbered_headings_with_their_own_wording_are_all_kept():
    # A statute is nothing but numbered headings, they must not collapse into one.
    chunks = [_chunk(p, f"§ {p} {titel}\nEin ganzer Satz mit Punkt am Ende.")
              for p, titel in enumerate(_PARAGRAFEN, start=1)]
    zeilen = [c["content"] for c in cb.outline_chunks(chunks)]
    assert sum(1 for z in zeilen if z.startswith("§")) == 8
