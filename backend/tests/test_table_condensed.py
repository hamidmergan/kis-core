"""The data table when the material does not fit: columns from the summaries, cells from search."""

from src.features.ai_assistant.tasks.studio import _table_condensed as tc


def _src(sid, label, summary):
    return {"id": sid, "label": label, "summary": summary}


def _chunk(label, page, text="Text"):
    return {"source_label": label, "page_number": page, "content": text}


_GERUEST = {"title": "Gesetze", "columns": ["Gesetz", "Bereich"],
            "rows": ["Kuendigungsschutz", "Arbeitszeit"]}
_FERTIG = {"title": "Gesetze", "columns": ["Gesetz", "Bereich"],
           "rows": [{"cells": ["KSchG", "Arbeitsrecht"]}]}


def _bauen(antworten, **over):
    calls = []

    def ask(messages):
        calls.append(messages)
        return antworten[len(calls) - 1]

    args = dict(sources=[_src(1, "a.pdf", "Ueber Alpha.")], language="Deutsch",
                adaptive_suffix="", ask=ask, embed=lambda t: [0.1],
                search=lambda q, vec, limit: [_chunk("a.pdf", 3)])
    args.update(over)
    return tc.build(**args), calls


def test_the_row_labels_become_the_search_topics():
    assert tc.row_topics(_GERUEST) == ["Kuendigungsschutz", "Arbeitszeit"]


def test_a_skeleton_without_rows_has_no_search_topic():
    assert tc.row_topics({"columns": ["A"]}) == []


def test_the_first_call_carries_the_summaries():
    _t, calls = _bauen([_GERUEST, _FERTIG])
    assert "Ueber Alpha." in calls[0][1]["content"]


def test_the_second_call_carries_the_columns_and_the_passages():
    _t, calls = _bauen([_GERUEST, _FERTIG])
    zweiter = calls[1][1]["content"]
    assert "Gesetz" in zweiter and "[a.pdf, S. 3]" in zweiter


def test_the_second_call_also_carries_the_summaries():
    """Measured: without them 77 of 162 cells stayed empty, the summaries hold the answers."""
    _t, calls = _bauen([_GERUEST, _FERTIG])
    assert "Ueber Alpha." in calls[1][1]["content"]


def test_the_finished_table_comes_back():
    tabelle, _calls = _bauen([_GERUEST, _FERTIG])
    assert tabelle == _FERTIG


def test_without_a_skeleton_there_is_no_second_call():
    tabelle, calls = _bauen([None])
    assert tabelle is None and len(calls) == 1


def test_a_skeleton_without_columns_is_no_skeleton():
    tabelle, calls = _bauen([{"rows": ["A"]}])
    assert tabelle is None and len(calls) == 1


def test_a_failed_filling_gives_no_half_table():
    tabelle, _calls = _bauen([_GERUEST, None])
    assert tabelle is None


def test_the_columns_of_the_skeleton_win_over_a_drifting_second_call():
    """The filling may not invent a column, the chips are built per cell."""
    abweichend = {"title": "X", "columns": ["Ganz", "Andere", "Spalten"],
                  "rows": [{"cells": ["a", "b", "c"]}]}
    tabelle, _calls = _bauen([_GERUEST, abweichend])
    assert tabelle["columns"] == ["Gesetz", "Bereich"]


def test_a_row_with_too_few_cells_is_padded_to_the_columns():
    kurz = {"title": "X", "columns": ["Gesetz", "Bereich"], "rows": [{"cells": ["KSchG"]}]}
    tabelle, _calls = _bauen([_GERUEST, kurz])
    assert tabelle["rows"][0]["cells"] == ["KSchG", ""]


def test_a_row_with_too_many_cells_is_cut_to_the_columns():
    lang = {"title": "X", "columns": ["Gesetz", "Bereich"],
            "rows": [{"cells": ["KSchG", "Arbeit", "zu viel"]}]}
    tabelle, _calls = _bauen([_GERUEST, lang])
    assert tabelle["rows"][0]["cells"] == ["KSchG", "Arbeit"]
