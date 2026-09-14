"""The numbered source legend of an exercise set."""

import pytest

from src.features.ai_assistant.routes.language_training.exercises import _numbered_sources

FILES = {
    "uuid-a": "01_Einfuehrung.pdf",
    "uuid-b": "02_Publizieren.pdf",
    "uuid-c": "03_Schreiben.pdf",
    "uuid-d": "VL1.webm",
    "uuid-e": "VL2.webm",
    "uuid-f": "VL3.webm",
}


@pytest.fixture(autouse=True)
def _sources(monkeypatch):
    monkeypatch.setattr(
        "src.database.get_aia_source",
        lambda uuid: {"filename": FILES[uuid]} if uuid in FILES else None,
    )


def test_no_sources_means_no_legend():
    assert _numbered_sources({"source_uuids": [], "source_uuid": None}) == []
    assert _numbered_sources({}) == []


def test_numbers_follow_the_order_the_learner_picked():
    out = _numbered_sources({"source_uuids": ["uuid-c", "uuid-a", "uuid-b"]})
    assert out == [
        {"number": 1, "filename": "03_Schreiben.pdf"},
        {"number": 2, "filename": "01_Einfuehrung.pdf"},
        {"number": 3, "filename": "02_Publizieren.pdf"},
    ]


def test_a_set_from_before_the_column_falls_back_to_its_single_source():
    out = _numbered_sources({"source_uuids": [], "source_uuid": "uuid-b"})
    assert out == [{"number": 1, "filename": "02_Publizieren.pdf"}]


def test_the_legend_lists_every_source_the_set_used():
    # The numbers in the exercises count all sources, so the legend must not stop earlier.
    out = _numbered_sources({"source_uuids": list(FILES)})
    assert len(out) == len(FILES)
    assert [e["number"] for e in out] == list(range(1, len(FILES) + 1))


def test_a_deleted_source_drops_out_and_the_numbers_close_the_gap():
    """A legend entry the learner cannot open is worse than a renumbering."""
    out = _numbered_sources({"source_uuids": ["uuid-a", "weg", "uuid-c"]})
    assert out == [
        {"number": 1, "filename": "01_Einfuehrung.pdf"},
        {"number": 2, "filename": "03_Schreiben.pdf"},
    ]
