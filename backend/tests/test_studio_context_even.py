"""Mindmap and data table give every source a share and repeat themselves."""

import pytest

from src.features.ai_assistant.tasks.studio import data_table, mindmap


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


@pytest.fixture
def welt(monkeypatch):
    """Three equal sources in one module, budget and marks under test control."""
    state = {"budget": 100000, "rotation": {}, "cursors": {}}
    quellen = {f"u{i}": {"id": i, "filename": f"q{i}.pdf", "workspace_id": 7}
               for i in (1, 2, 3)}

    monkeypatch.setattr("src.database.get_aia_source", lambda u: quellen.get(u))
    monkeypatch.setattr("src.database.get_chunks_by_source", lambda sid: _chunks(sid, 60, 500))
    monkeypatch.setattr("src.database.get_context_cursors",
                        lambda w, s, t: state["cursors"].get((w, s, t), []))
    monkeypatch.setattr("src.database.set_context_cursors",
                        lambda w, s, t, c: state["cursors"].__setitem__((w, s, t), list(c)))
    monkeypatch.setattr("src.database.get_context_rotation",
                        lambda w, t: state["rotation"].get((w, t)))
    monkeypatch.setattr("src.database.set_context_rotation",
                        lambda w, t, s: state["rotation"].__setitem__((w, t), s))
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks._context_budget.tool_context_budget",
        lambda tool="": state["budget"])
    return state


_IDS = [1, 2, 3]
_UUIDS = ["u1", "u2", "u3"]
_MAP = {"1": {"filename": "q1.pdf"}, "2": {"filename": "q2.pdf"}, "3": {"filename": "q3.pdf"}}


def _mindmap_labels(gesammelt) -> list[str]:
    return [label for _sid, label, _all, _picked in gesammelt]


# --- mindmap -----------------------------------------------------------------

def test_the_mindmap_takes_every_source_that_fits(welt):
    assert _mindmap_labels(mindmap._collect_sources(_IDS, _UUIDS)) == [
        "q1.pdf", "q2.pdf", "q3.pdf"]


def test_the_mindmap_keeps_every_source_when_the_budget_is_full(welt):
    # The umbrella topic can only span the sources the model actually sees.
    welt["budget"] = 32000
    assert _mindmap_labels(mindmap._collect_sources(_IDS, _UUIDS)) == [
        "q1.pdf", "q2.pdf", "q3.pdf"]


def test_the_mindmap_keeps_all_chunks_for_the_timestamps(welt):
    # The picked window shrinks, the full list has to stay for media citations.
    welt["budget"] = 20000
    _sid, _label, alle, picked = mindmap._collect_sources(_IDS, _UUIDS)[0]
    assert len(alle) == 60
    assert len(picked) < 60


def test_the_mindmap_reads_the_same_material_twice(welt):
    welt["budget"] = 32000
    erster = mindmap._collect_sources(_IDS, _UUIDS)
    zweiter = mindmap._collect_sources(_IDS, _UUIDS)
    assert ([(c["source_id"], c["page_number"]) for _s, _l, _a, p in erster for c in p]
            == [(c["source_id"], c["page_number"]) for _s, _l, _a, p in zweiter for c in p])


def test_the_mindmap_remembers_nothing(welt):
    welt["budget"] = 32000
    mindmap._collect_sources(_IDS, _UUIDS)
    assert welt["rotation"] == {}
    assert welt["cursors"] == {}


def test_the_mindmap_spends_its_depth_from_the_front(welt):
    # Every source keeps its base, the room that is left is not smeared evenly.
    welt["budget"] = 32000
    mengen = [len(picked) for _sid, _label, _alle, picked in mindmap._collect_sources(_IDS, _UUIDS)]
    assert mengen[0] > mengen[-1]


# --- data table --------------------------------------------------------------

def test_the_table_keeps_every_source(welt):
    gesammelt = data_table._collect_sources(_IDS, _MAP)
    assert [label for _sid, label, _chunks in gesammelt] == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_the_table_hands_over_every_chunk_because_the_packets_do_the_cutting(welt):
    # A row must not be missing because a sample skipped its page.
    welt["budget"] = 32000
    gesammelt = data_table._collect_sources(_IDS, _MAP)
    assert [len(chunks) for _sid, _label, chunks in gesammelt] == [60, 60, 60]


def test_the_table_remembers_nothing(welt):
    data_table._collect_sources(_IDS, _MAP)
    assert welt["rotation"] == {}
    assert welt["cursors"] == {}
