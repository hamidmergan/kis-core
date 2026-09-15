"""The podcast when the material does not fit: topics from the summaries, text from search."""

import pytest

from src.features.podcast import outline


def _src(label, summary):
    return {"label": label, "summary": summary}


def _chunk(label, text, page=1):
    return {"source_label": label, "content": text, "page_number": page}


def test_the_topics_come_out_of_the_answer():
    assert outline.topic_list({"themen": ["Alpha", "Beta"]}) == ["Alpha", "Beta"]


def test_an_answer_without_topics_gives_none():
    assert outline.topic_list({"was": "anderes"}) == []


def test_a_topic_named_twice_travels_once():
    assert outline.topic_list({"themen": ["Alpha", "Alpha"]}) == ["Alpha"]


def test_the_number_of_topics_is_capped():
    viele = {"themen": [f"T{i}" for i in range(30)]}
    assert len(outline.topic_list(viele)) == outline._MAX_TOPICS


def test_a_source_without_a_summary_blocks_the_way():
    assert outline.usable([_src("a.pdf", "Alpha"), _src("b.pdf", "")]) is False


def test_with_a_summary_everywhere_the_way_is_open():
    assert outline.usable([_src("a.pdf", "Alpha"), _src("b.pdf", "Beta")]) is True


def test_the_found_text_is_grouped_under_its_topic():
    text = outline.as_text({"Alpha": [_chunk("a.pdf", "Erster Satz")]})
    assert "Alpha" in text and "Erster Satz" in text and "a.pdf" in text


def test_the_same_passage_under_two_topics_travels_once():
    c = _chunk("a.pdf", "Doppelt")
    text = outline.as_text({"Alpha": [c], "Beta": [c]})
    assert text.count("Doppelt") == 1


@pytest.mark.asyncio
async def test_the_call_carries_the_summaries_and_the_result_carries_the_passages():
    calls = []

    async def ask(messages):
        calls.append(messages)
        return {"themen": ["Alpha"]}

    def suche(frage, limit):
        return [_chunk("a.pdf", "Alpha steht hier")]

    text = await outline.build(sources=[_src("a.pdf", "Ueber Alpha.")], ask=ask, search=suche)
    assert "Ueber Alpha." in calls[0][1]["content"]
    assert "Alpha steht hier" in text


@pytest.mark.asyncio
async def test_without_topics_there_is_no_text():
    async def ask(messages):
        return {"themen": []}

    text = await outline.build(sources=[_src("a.pdf", "A")], ask=ask,
                               search=lambda f, l: [])
    assert text == ""
