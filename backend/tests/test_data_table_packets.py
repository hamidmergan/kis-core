"""The data table in packets: columns fixed once, every further packet only adds rows."""

from src.features.ai_assistant.tasks.studio import _table_packets as tp


def _table(**over):
    base = {"title": "Begriffe", "columns": ["Begriff", "Bedeutung"],
            "rows": [{"cells": ["A", "B"]}]}
    base.update(over)
    return base


# --- packets ----------------------------------------------------------------

def test_parts_that_fit_together_make_one_packet():
    assert tp.packets(["a" * 100, "b" * 100], 1000) == [["a" * 100, "b" * 100]]


def test_the_budget_starts_a_new_packet():
    out = tp.packets(["a" * 600, "b" * 600], 1000)
    assert [len(p) for p in out] == [1, 1]


def test_an_oversize_part_travels_alone():
    out = tp.packets(["a" * 50, "b" * 5000, "c" * 50], 1000)
    assert [len(p) for p in out] == [1, 1, 1]


def test_no_parts_make_no_packet():
    assert tp.packets([], 1000) == []


# --- merge_tables -----------------------------------------------------------

def test_title_and_columns_come_from_the_first_table():
    spaet = _table(title="Anders", columns=["X", "Y"], rows=[{"cells": ["c", "d"]}])
    out = tp.merge_tables([_table(), spaet])
    assert out["title"] == "Begriffe" and out["columns"] == ["Begriff", "Bedeutung"]


def test_the_rows_of_every_packet_are_kept():
    zweite = _table(rows=[{"cells": ["C", "D"]}, {"cells": ["E", "F"]}])
    out = tp.merge_tables([_table(), zweite])
    assert [r["cells"] for r in out["rows"]] == [["A", "B"], ["C", "D"], ["E", "F"]]


def test_a_row_that_does_not_fit_the_columns_is_dropped():
    # A later packet may answer with its own idea of the table.
    schief = _table(rows=[{"cells": ["C", "D", "E"]}, {"cells": ["F", "G"]}])
    out = tp.merge_tables([_table(), schief])
    assert [r["cells"] for r in out["rows"]] == [["A", "B"], ["F", "G"]]


def test_a_packet_without_a_usable_answer_is_skipped():
    out = tp.merge_tables([_table(), None, {}, {"rows": [{"cells": ["C", "D"]}]}])
    assert [r["cells"] for r in out["rows"]] == [["A", "B"], ["C", "D"]]


def test_nothing_usable_at_all_gives_nothing():
    assert tp.merge_tables([None, {}]) is None


def test_the_first_table_without_columns_does_not_set_them():
    out = tp.merge_tables([{"rows": [{"cells": ["A", "B"]}]}, _table()])
    assert out["columns"] == ["Begriff", "Bedeutung"]
    assert [r["cells"] for r in out["rows"]] == [["A", "B"], ["A", "B"]]


# --- run_packets ------------------------------------------------------------

def _asker(calls: list, antworten=None):
    """Records what each packet was asked and answers in packet order."""
    def ask(text: str, columns):
        calls.append((text, columns))
        if antworten is None:
            return _table(rows=[{"cells": [text, "x"]}])
        return antworten[len(calls) - 1]
    return ask


def test_the_first_packet_is_asked_without_columns():
    calls = []
    tp.run_packets([["a"], ["b"]], _asker(calls))
    assert calls[0][1] is None


def test_every_further_packet_is_asked_with_the_fixed_columns():
    calls = []
    tp.run_packets([["a"], ["b"], ["c"]], _asker(calls))
    assert calls[1][1] == ["Begriff", "Bedeutung"]
    assert calls[2][1] == ["Begriff", "Bedeutung"]


def test_the_rows_of_every_packet_end_up_in_the_table():
    out = tp.run_packets([["a"], ["b"]], _asker([]))
    assert [r["cells"][0] for r in out["rows"]] == ["a", "b"]


def test_a_failing_packet_does_not_cost_the_others_their_rows():
    def ask(text, columns):
        if text == "b":
            raise RuntimeError("provider down")
        return _table(rows=[{"cells": [text, "x"]}])
    out = tp.run_packets([["a"], ["b"], ["c"]], ask)
    assert [r["cells"][0] for r in out["rows"]] == ["a", "c"]


def test_a_failing_first_packet_still_lets_the_rest_build_the_table():
    def ask(text, columns):
        if text == "a":
            raise RuntimeError("provider down")
        return _table(rows=[{"cells": [text, "x"]}])
    out = tp.run_packets([["a"], ["b"]], ask)
    assert [r["cells"][0] for r in out["rows"]] == ["b"]


def test_no_packet_gives_no_table():
    assert tp.run_packets([], _asker([])) is None


def test_the_packets_stop_at_the_cap():
    # Without a cap a module of statutes would burn twenty calls and still hit the timeout.
    out = tp.packets(["a" * 600] * 30, 1000, max_packets=3)
    assert len(out) == 3
    assert out[0] == ["a" * 600]


def test_without_a_cap_every_part_travels():
    assert len(tp.packets(["a" * 600] * 30, 1000)) == 30
