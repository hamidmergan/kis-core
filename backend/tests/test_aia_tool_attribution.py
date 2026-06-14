"""Tool-side wiring of the shared attribution: build search inputs from a QuelleContext
and attach nav-only chips to generated items. Shared by flashcards/quiz/karteikarten."""

from src.features.ai_assistant.tasks.language_training._attribution import (
    attach_chips,
    attribution_inputs,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _ctx():
    return QuelleContext(
        context="",
        first_label="A.pdf",
        multi_label="A.pdf",
        source_hint="x",
        source_by_name={
            "A.pdf": {"id": 1, "workspace_id": 7},
            "B.pdf": {"id": 2, "workspace_id": 7},
        },
    )


def test_attribution_inputs_from_ctx():
    wid, sids, lbl = attribution_inputs(_ctx())
    assert wid == 7
    assert sorted(sids) == [1, 2]
    assert lbl == {1: "A.pdf", 2: "B.pdf"}


def test_attach_chips_sets_sources_and_primary_fields():
    items = [{"front": "X", "back": "def x"}, {"front": "Y", "back": "def y"}]
    claims = ["X", "Y"]

    def embed_fn(texts):
        return [[1.0, 0.0] for _ in texts]

    def search_fn(text, vec):
        if text == "X":
            return [{"source_id": 1, "page_number": 4, "content": "x",
                     "vec_distance": 0.2, "start_time": None}]
        return []  # Y grounds nowhere -> no chip

    out = attach_chips(items, claims, _ctx(), multi=False, embed_fn=embed_fn, search_fn=search_fn)
    assert out[0]["sources"] == [{"source_label": "A.pdf", "page_number": 4, "start_time": None}]
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 4
    assert out[0]["start_time"] is None
    assert "sources" not in out[1]
