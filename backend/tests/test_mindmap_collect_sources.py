"""The file name must follow the source itself, never the position in a list."""

import pytest

from src.features.ai_assistant.tasks.studio import mindmap as mm


_QUELLEN = {
    "uuid-gmbhg": {"id": 36, "filename": "GmbHG36.pdf", "workspace_id": 1},
    "uuid-famfg": {"id": 77, "filename": "FamFG77.pdf", "workspace_id": 1},
}
_CHUNKS = {
    36: [{"content": "Das Stammkapital betraegt", "page_number": 6}],
    77: [{"content": "Ehesachen und Familienstreitsachen", "page_number": 1}],
}


@pytest.fixture
def _db(monkeypatch):
    monkeypatch.setattr(mm.db, "get_aia_source", lambda u: _QUELLEN.get(u))
    monkeypatch.setattr(mm.db, "get_chunks_by_source", lambda i: _CHUNKS.get(i, []))
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks._context_budget.fill_sources_evenly",
        lambda vorhanden, budget=None: [(sid, label, chunks) for sid, label, chunks in vorhanden])


def _labels_to_text(gesammelt):
    return {label: alle[0]["content"] for _sid, label, alle, _p in gesammelt}


def test_the_file_name_belongs_to_its_own_chunks(_db):
    gesammelt = mm._collect_sources([36, 77], ["uuid-gmbhg", "uuid-famfg"])
    assert _labels_to_text(gesammelt) == {
        "GmbHG36.pdf": "Das Stammkapital betraegt",
        "FamFG77.pdf": "Ehesachen und Familienstreitsachen"}


def test_a_shuffled_id_list_does_not_swap_the_file_names(_db):
    """The ids arrive sorted, the uuids in pick order, the pairing must still hold."""
    gesammelt = mm._collect_sources([36, 77], ["uuid-famfg", "uuid-gmbhg"])
    assert _labels_to_text(gesammelt) == {
        "GmbHG36.pdf": "Das Stammkapital betraegt",
        "FamFG77.pdf": "Ehesachen und Familienstreitsachen"}


def test_an_unknown_uuid_is_skipped_instead_of_shifting_the_rest(_db):
    gesammelt = mm._collect_sources([36, 77], ["uuid-weg", "uuid-gmbhg"])
    assert _labels_to_text(gesammelt) == {"GmbHG36.pdf": "Das Stammkapital betraegt"}
