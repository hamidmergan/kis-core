"""Open appointments are found by meaning, one search for the whole module."""

from src.features.ai_assistant.tasks.studio.schedule._open_search import (
    QUERIES, open_spots_for_workspace,
)


def _search_returning(*chunks):
    """A stand-in search that always answers with the same chunks."""
    calls = []

    def search(workspace_id, query_text, vector, source_ids, limit):
        calls.append(query_text)
        return list(chunks)

    return search, calls


def _embed(_text):
    return [0.1, 0.2, 0.3]


def test_every_query_wording_is_searched_once():
    search, calls = _search_returning()
    open_spots_for_workspace(7, [1], embed=_embed, search=search)
    assert calls == list(QUERIES)


def test_a_hit_becomes_an_open_spot():
    chunk = {"id": 42, "content": "Die Exkursion ist geplant. "
                                  "Der Termin wird noch bekannt gegeben. Bitte vormerken."}
    search, _ = _search_returning(chunk)
    spots = open_spots_for_workspace(7, [1], embed=_embed, search=search)
    assert 42 in spots


def test_the_quote_is_the_sentence_that_carries_the_wording():
    chunk = {"id": 42, "content": "Die Exkursion ist geplant. "
                                  "Der Termin wird noch bekannt gegeben. Bitte vormerken."}
    search, _ = _search_returning(chunk)
    start, end, phrase = open_spots_for_workspace(7, [1], embed=_embed, search=search)[42]
    assert phrase == "Der Termin wird noch bekannt gegeben."
    assert chunk["content"][start:end] == phrase


def test_the_same_chunk_from_two_queries_counts_once():
    chunk = {"id": 42, "content": "Der Termin wird noch bekannt gegeben."}
    search, calls = _search_returning(chunk, chunk)
    spots = open_spots_for_workspace(7, [1], embed=_embed, search=search)
    assert list(spots) == [42]


def test_a_chunk_without_the_wording_falls_back_to_its_first_sentence():
    """Whether it is really an appointment is decided later by the classification."""
    chunk = {"id": 9, "content": "Die Gewerbeordnung regelt das Recht. Weitere Hinweise folgen."}
    search, _ = _search_returning(chunk)
    _s, _e, phrase = open_spots_for_workspace(7, [1], embed=_embed, search=search)[9]
    assert phrase == "Die Gewerbeordnung regelt das Recht."


def test_nothing_found_means_nothing_returned():
    search, _ = _search_returning()
    assert open_spots_for_workspace(7, [1], embed=_embed, search=search) == {}
