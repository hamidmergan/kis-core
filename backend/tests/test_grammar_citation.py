"""Layered origin of the source chip, because the sentences are newly invented."""

import pytest

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips_cited
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _boom(*args, **kwargs):
    raise AssertionError("attribution must not search here")


def _one_source_ctx():
    return QuelleContext(
        context="",
        first_label="A.pdf",
        multi_label="A.pdf",
        source_hint="x",
        sections={1: "A.pdf"},
        source_by_name={"A.pdf": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {4, 5, 9}},
    )


def _two_source_ctx():
    return QuelleContext(
        context="",
        first_label="A.pdf",
        multi_label="2 Sources",
        source_hint="x",
        sections={1: "A.pdf", 2: "B.pdf"},
        source_by_name={
            "A.pdf": {"id": 1, "workspace_id": 7},
            "B.pdf": {"id": 2, "workspace_id": 7},
        },
        seen_pages_by_source={1: {4, 5}, 2: {7, 8}},
    )


def _media_ctx():
    return QuelleContext(
        context="",
        first_label="V.mp4",
        multi_label="V.mp4",
        source_hint="x",
        sections={1: "V.mp4"},
        source_by_name={"V.mp4": {"id": 3, "workspace_id": 7}},
        seen_pages_by_source={3: {7, 8}},
        media_start_by_page={3: {7: 91.5, 8: 140.0}},
    )


def _embed(texts):
    return [[1.0, 0.0] for _ in texts]


def _no_segments(source_id):
    """Without known segments the timestamp stays at the chunk start."""
    return []


def _hit(source_id, page, distance=0.2, start_time=None):
    return {"source_id": source_id, "page_number": page, "content": "lorem ipsum " * 20,
            "vec_distance": distance, "start_time": start_time}


# ─── Stage 1: the page the model names itself ─────────────────────────────────

def test_the_page_the_model_cited_becomes_the_chip_without_any_search():
    """If the model names the page, the search does not even run."""
    items = [{"front": "S", "back": "T", "_page": 5}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["sources"] == [{"source_label": "A.pdf", "page_number": 5, "start_time": None}]
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 5


def test_a_cited_page_is_matched_to_the_source_that_actually_has_it():
    # Two sources, the model names only the page, only B.pdf showed page 8.
    items = [{"front": "S", "back": "T", "_page": 8}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 8


def test_the_named_section_decides_when_two_sources_share_a_page_number():
    # Both sources would have page 4, the section resolves it.
    ctx = _two_source_ctx()
    ctx.seen_pages_by_source = {1: {4}, 2: {4}}
    items = [{"front": "S", "back": "T", "_page": 4, "_section": 2}]
    out = attach_chips_cited(items, ["T"], ctx, embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 4


def test_a_page_the_model_never_saw_is_not_trusted():
    """A page never shown would be invented, then the search wins."""
    items = [{"front": "S", "back": "T", "_page": 42}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [_hit(1, 4)])
    assert out[0]["page_number"] == 4


@pytest.mark.parametrize("cited", ["Seite 4", None, "", -1, 0, True])
def test_a_page_that_is_not_a_plain_number_falls_through(cited):
    items = [{"front": "S", "back": "T", "_page": cited}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [_hit(1, 9)])
    assert out[0]["page_number"] == 9


def test_a_page_written_as_a_string_of_digits_still_counts():
    # Models regularly return numbers in JSON as text.
    items = [{"front": "S", "back": "T", "_page": "5"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["page_number"] == 5


# ─── Stage 2: the old back-search ─────────────────────────────────────────────

def test_search_runs_only_for_the_items_the_model_could_not_place():
    """The search may only see the sentences stage 1 left open."""
    embedded, searched = [], []

    def embed_fn(texts):
        embedded.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def search_fn(text, vec):
        searched.append(text)
        return [_hit(1, 4)]

    items = [
        {"front": "a", "back": "A", "_page": 5},
        {"front": "b", "back": "B"},
        {"front": "c", "back": "C", "_page": 9},
    ]
    out = attach_chips_cited(items, ["A", "B", "C"], _one_source_ctx(),
                             embed_fn=embed_fn, search_fn=search_fn)
    assert embedded == ["B"]
    assert searched == ["B"]
    assert [i["page_number"] for i in out] == [5, 4, 9]


# ─── Stage 3: the section as a safety net ─────────────────────────────────────

def test_without_a_page_and_without_a_search_hit_the_chip_points_at_the_source():
    """With one source the file is fixed, so no sentence stays chip free."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 4


def test_the_named_section_carries_the_chip_when_everything_else_fails():
    items = [{"front": "S", "back": "T", "_section": 2}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 7


def test_a_multi_source_item_with_no_signal_at_all_stays_without_a_chip():
    """The one open gap: guessing a source would be worse than no chip."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert "sources" not in out[0]
    assert out[0]["source_label"] is None
    assert out[0]["page_number"] is None


# ─── Audio and video ──────────────────────────────────────────────────────────

def test_a_cited_segment_number_is_not_trusted_for_media():
    """For media only the search counts, the model's section number is wrong there."""
    items = [{"front": "S", "back": "T", "_page": 7}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed,
                             search_fn=lambda t, v: [_hit(3, 8, start_time=140.0)],
                             segments_fn=_no_segments)
    assert out[0]["start_time"] == 140.0
    assert out[0]["page_number"] is None


def test_a_search_hit_still_cites_media_by_timestamp():
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed,
                             search_fn=lambda t, v: [_hit(3, 7, start_time=91.5)],
                             segments_fn=_no_segments)
    assert out[0]["sources"] == [
        {"source_label": "V.mp4", "page_number": None, "start_time": 91.5}]


def test_media_without_a_search_hit_cites_the_file_and_no_time():
    """A wrong minute is worse than none, then the chip names only the file."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["sources"] == [
        {"source_label": "V.mp4", "page_number": None, "start_time": None}]
    assert out[0]["source_label"] == "V.mp4"
    assert out[0]["start_time"] is None
    assert out[0]["page_number"] is None


def test_a_pdf_in_the_same_set_keeps_the_cited_page():
    # The split runs per source, not per sentence.
    ctx = _media_ctx()
    ctx.sections = {1: "V.mp4", 2: "A.pdf"}
    ctx.source_by_name["A.pdf"] = {"id": 1, "workspace_id": 7}
    ctx.seen_pages_by_source[1] = {4, 5}
    items = [{"front": "S", "back": "T", "_page": 5}]
    out = attach_chips_cited(items, ["T"], ctx, embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 5


# ─── Cleanup ──────────────────────────────────────────────────────────────────

def test_the_cited_page_never_reaches_the_database_row():
    # The helper fields should not reach the caller in the first place.
    items = [{"front": "S", "back": "T", "_page": 5, "_section": 1}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert "_page" not in out[0]


def test_a_failing_embedding_call_still_leaves_every_item_with_a_chip():
    """On a provider refusal the section catches the chip."""
    def embed_fn(texts):
        raise RuntimeError("429 rate limit")

    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=embed_fn, search_fn=_boom)
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 4
