"""One model call per packet: hit blocks in, real appointments out, pairs per source."""

import json
import types
from datetime import date

import pytest

from src.features.ai_assistant.tasks.studio.schedule._extract import (
    extract_packet, hit_blocks, items_to_pairs, packets,
)
from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_EXTRACT_PROMPT

HEUTE = date(2026, 9, 14)
SRC = {"id": 7, "uuid": "u7", "filename": "plan.pdf"}


def _chunk(cid, text, page=1, start=None):
    return {"id": cid, "content": text, "page_number": page, "start_time": start}


def _block(cid, text, source_id=7, page=1, start=None):
    return {"id": cid, "text": text, "source_id": source_id, "source_uuid": f"u{source_id}",
            "source_filename": f"q{source_id}.pdf", "page_number": page, "start_time": start}


def _item(cid, **over):
    base = {"id": cid, "date": "2026-03-14", "end_date": None, "time": None, "end_time": None,
            "type": "termin", "title": "Klausur Wirtschaftsrecht", "description": None,
            "quote": "Klausur am 14.03.2026", "open_ended": False, "optional": False}
    base.update(over)
    return base


# --- hit_blocks -------------------------------------------------------------

def test_a_chunk_with_a_date_becomes_a_block_with_its_source_fields():
    out = hit_blocks(SRC, [_chunk(10, "Klausur am 14.03.2026", page=3)], {})
    assert [b["id"] for b in out] == [10]
    b = out[0]
    assert (b["source_id"], b["source_uuid"], b["source_filename"], b["page_number"]) == (7, "u7", "plan.pdf", 3)
    assert b["text"] == "Klausur am 14.03.2026"


def test_a_chunk_without_a_date_or_open_spot_is_left_out():
    assert hit_blocks(SRC, [_chunk(11, "Hier steht kein Datum.")], {}) == []


def test_a_chunk_the_open_search_found_is_a_block_too():
    out = hit_blocks(SRC, [_chunk(12, "Der Termin wird noch bekannt gegeben.")],
                     {12: (0, 10, "Der Termin wird noch bekannt gegeben.")})
    assert [b["id"] for b in out] == [12]


def test_blocks_keep_the_chunk_order():
    chunks = [_chunk(3, "am 1.1.2027"), _chunk(1, "nichts"), _chunk(2, "am 2.2.2027")]
    assert [b["id"] for b in hit_blocks(SRC, chunks, {})] == [3, 2]


# --- packets ----------------------------------------------------------------

def test_packets_are_cut_at_the_budget_in_block_order():
    blocks = [_block(i, "x" * 400) for i in range(3)]
    out = packets(blocks, 900)
    assert [[b["id"] for b in p] for p in out] == [[0, 1], [2]]


def test_an_oversize_block_travels_alone():
    blocks = [_block(0, "x" * 100), _block(1, "x" * 2000), _block(2, "x" * 100)]
    out = packets(blocks, 500)
    assert [[b["id"] for b in p] for p in out] == [[0], [1], [2]]


def test_no_blocks_means_no_packets():
    assert packets([], 800000) == []


# --- extract_packet ---------------------------------------------------------

def _client(answer: str, calls: list):
    def create(**kw):
        calls.append(kw)
        msg = types.SimpleNamespace(content=answer)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_the_request_carries_the_prompt_the_date_and_the_blocks():
    calls = []
    packet = [_block(10, "Klausur am 14.03.2026")]
    extract_packet(_client('{"appointments": []}', calls), "m", packet, HEUTE)
    kw = calls[0]
    assert kw["messages"][0]["content"] == AIA_SCHEDULE_EXTRACT_PROMPT
    user = kw["messages"][1]["content"]
    assert "2026-09-14" in user and "Klausur am 14.03.2026" in user and '"id": 10' in user
    assert kw["response_format"] == {"type": "json_object"}
    # Measured: 600k chars of dense text are 245k tokens, more answer room tips a full packet over the window.
    assert 8000 <= kw["max_tokens"] <= 16000


def test_the_answer_items_come_back_as_a_list():
    items = extract_packet(_client(json.dumps({"appointments": [_item(10)]}), []), "m",
                           [_block(10, "Klausur am 14.03.2026")], HEUTE)
    assert [i["id"] for i in items] == [10]


@pytest.mark.parametrize("answer", ["{}", '{"appointments": null}', '```json\n{"appointments": []}\n```'])
def test_an_empty_or_fenced_answer_is_no_appointment(answer):
    assert extract_packet(_client(answer, []), "m", [_block(10, "x 1.1.2027")], HEUTE) == []


# --- items_to_pairs ---------------------------------------------------------

def test_every_source_of_the_blocks_gets_a_pair_even_without_items():
    blocks = [_block(10, "am 1.1.2027", source_id=1), _block(20, "am 2.2.2027", source_id=2)]
    out = items_to_pairs([], blocks, HEUTE)
    assert out == {1: ([], []), 2: ([], [])}


def test_a_full_date_becomes_a_kept_day_candidate():
    blocks = [_block(10, "Die Klausur am 14.03.2026 um 10 Uhr.", page=4)]
    out = items_to_pairs([_item(10, time="10:00", description="Raum A1")], blocks, HEUTE)
    cands, cls = out[7]
    assert len(cands) == 1
    c, v = cands[0], cls[0]
    assert (c["date_iso"], c["date_precision"], c["partial_date"], c["is_tbd"]) == ("2026-03-14", "day", None, False)
    assert (c["raw_quote"], c["page_number"], c["source_uuid"], c["source_filename"]) == ("Klausur am 14.03.2026", 4, "u7", "q7.pdf")
    assert "14.03.2026" in c["context"]
    assert v["keep"] is True and v["type"] == "termin" and v["title"] == "Klausur Wirtschaftsrecht"
    assert (v["due_time"], v["end_time"], v["description"]) == ("10:00", None, "Raum A1")
    assert (v["is_footer"], v["is_header"], v["is_historical"], v["is_range"], v["is_open_ended"], v["is_optional"]) == (False,) * 6


def test_a_month_only_date_sorts_on_the_first_with_month_precision():
    blocks = [_block(10, "Abgabe im März 2026.")]
    out = items_to_pairs([_item(10, date="2026-03", quote="Abgabe im März 2026")], blocks, HEUTE)
    c = out[7][0][0]
    assert (c["date_iso"], c["date_precision"]) == ("2026-03-01", "month")


def test_a_date_without_a_year_keeps_month_and_day_for_the_year_rule():
    blocks = [_block(10, "Klausur am 14. März.")]
    out = items_to_pairs([_item(10, date="03-14", quote="Klausur am 14. März")], blocks, HEUTE)
    c = out[7][0][0]
    assert (c["date_iso"], c["partial_date"], c["date_precision"]) == (None, (3, 14), "day")


def test_no_date_at_all_is_an_open_appointment():
    blocks = [_block(10, "Sprechstunde nach Vereinbarung.")]
    out = items_to_pairs([_item(10, date=None, quote="Sprechstunde nach Vereinbarung")], blocks, HEUTE)
    c = out[7][0][0]
    assert c["is_tbd"] is True and c["date_iso"] is None and c["partial_date"] is None


def test_an_end_date_makes_a_range():
    blocks = [_block(10, "Anmeldung 14.03.2026 bis 20.03.2026.")]
    out = items_to_pairs([_item(10, end_date="2026-03-20", quote="Anmeldung 14.03.2026 bis 20.03.2026")], blocks, HEUTE)
    c, v = out[7][0][0], out[7][1][0]
    assert (c["date_end_iso"], c["date_end_partial"], v["is_range"]) == ("2026-03-20", None, True)


def test_an_end_without_a_year_keeps_month_and_day():
    blocks = [_block(10, "vom 14. bis 20. März")]
    out = items_to_pairs([_item(10, date="03-14", end_date="03-20", quote="vom 14. bis 20. März")], blocks, HEUTE)
    c = out[7][0][0]
    assert (c["date_end_iso"], c["date_end_partial"]) == (None, (3, 20))


def test_open_ended_and_optional_flags_pass_through():
    blocks = [_block(10, "ab 14.03.2026 freigeschaltet, freiwillig")]
    out = items_to_pairs([_item(10, open_ended=True, optional=True, quote="ab 14.03.2026 freigeschaltet")], blocks, HEUTE)
    v = out[7][1][0]
    assert (v["is_open_ended"], v["is_optional"]) == (True, True)


def test_an_unknown_block_id_is_dropped():
    blocks = [_block(10, "Klausur am 14.03.2026")]
    out = items_to_pairs([_item(99)], blocks, HEUTE)
    assert out == {7: ([], [])}


def test_a_quote_that_is_not_in_the_block_is_dropped():
    blocks = [_block(10, "Klausur am 14.03.2026")]
    out = items_to_pairs([_item(10, quote="Klausur am 15.03.2026")], blocks, HEUTE)
    assert out == {7: ([], [])}


def test_a_quote_survives_line_breaks_in_the_block():
    blocks = [_block(10, "Die Klausur\nam 14.03.2026\nim Audimax.")]
    out = items_to_pairs([_item(10, quote="Klausur am 14.03.2026 im Audimax")], blocks, HEUTE)
    assert len(out[7][0]) == 1


def test_an_impossible_date_is_dropped():
    blocks = [_block(10, "am 30.02.2026")]
    out = items_to_pairs([_item(10, date="2026-02-30", quote="am 30.02.2026")], blocks, HEUTE)
    assert out == {7: ([], [])}


def test_an_unknown_type_becomes_termin():
    blocks = [_block(10, "Klausur am 14.03.2026")]
    out = items_to_pairs([_item(10, type="exam")], blocks, HEUTE)
    assert out[7][1][0]["type"] == "termin"


def test_the_timestamp_comes_from_the_spot_in_a_transcript_block():
    blocks = [_block(10, "bla bla Klausur am 14.03.2026", start=100.0)]
    out = items_to_pairs([_item(10)], blocks, HEUTE, time_at=lambda block, offset: 100.0 + offset)
    assert out[7][0][0]["start_time"] == 108.0


def test_without_a_timeline_the_block_start_is_the_timestamp():
    blocks = [_block(10, "Klausur am 14.03.2026", start=42.0)]
    out = items_to_pairs([_item(10)], blocks, HEUTE)
    assert out[7][0][0]["start_time"] == 42.0


def test_a_quote_that_differs_only_in_case_is_still_found():
    blocks = [_block(10, "Für Güterhändler besteht die Pflicht ab dem 1. Januar 2027.")]
    out = items_to_pairs([_item(10, date="2027-01-01",
                                quote="für Güterhändler besteht die Pflicht ab dem 1. Januar 2027")],
                         blocks, HEUTE)
    assert len(out[7][0]) == 1


def test_a_month_without_a_year_keeps_the_month_for_the_year_rule():
    blocks = [_block(10, "Ende Mai ist die freiwillige Abgabe.")]
    out = items_to_pairs([_item(10, date="05", quote="Ende Mai ist die freiwillige Abgabe")], blocks, HEUTE)
    c = out[7][0][0]
    assert (c["date_iso"], c["partial_date"], c["date_precision"]) == (None, (5, 1), "month")


def test_the_prompt_names_the_month_only_shape():
    assert "'MM' when only the month" in AIA_SCHEDULE_EXTRACT_PROMPT


def _client_that_rejects_big_packets(calls: list, limit_blocks: int):
    """Answers only packets up to the limit, bigger ones get the provider's 400."""
    def create(**kw):
        calls.append(kw)
        blocks = json.loads(kw["messages"][1]["content"].split("Blocks:\n", 1)[1])
        if len(blocks) > limit_blocks:
            raise RuntimeError("Error code: 400 - {'message': 'Failed to process request'}")
        items = [{"id": b["id"], "date": "2026-03-14", "type": "termin", "title": "T",
                  "quote": b["text"]} for b in blocks]
        msg = types.SimpleNamespace(content=json.dumps({"appointments": items}))
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_a_rejected_packet_is_split_in_half_and_both_halves_are_sent():
    calls = []
    packet = [_block(i, f"Termin am 14.03.2026 Nr. {i}") for i in range(4)]
    items = extract_packet(_client_that_rejects_big_packets(calls, 2), "m", packet, HEUTE)
    assert sorted(i["id"] for i in items) == [0, 1, 2, 3]
    assert len(calls) == 3


def test_a_rejected_single_block_gives_up():
    calls = []
    packet = [_block(0, "Termin am 14.03.2026")]
    with pytest.raises(RuntimeError):
        extract_packet(_client_that_rejects_big_packets(calls, 0), "m", packet, HEUTE)
    assert len(calls) == 1


def test_another_error_is_not_retried_by_splitting():
    calls = []

    def create(**kw):
        calls.append(kw)
        raise RuntimeError("Error code: 500 - server down")

    client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    with pytest.raises(RuntimeError):
        extract_packet(client, "m", [_block(0, "a 1.1.2027"), _block(1, "b 1.1.2027")], HEUTE)
    assert len(calls) == 1


def _client_that_truncates_big_packets(calls: list, limit_blocks: int):
    """Answers small packets fully, a bigger one comes back cut off at the cap."""
    def create(**kw):
        calls.append(kw)
        blocks = json.loads(kw["messages"][1]["content"].split("Blocks:\n", 1)[1])
        items = [{"id": b["id"], "date": "2026-03-14", "type": "termin", "title": "T",
                  "quote": b["text"]} for b in blocks]
        voll = json.dumps({"appointments": items})
        zu_lang = len(blocks) > limit_blocks
        msg = types.SimpleNamespace(content=voll[:len(voll) // 2] if zu_lang else voll)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=msg, finish_reason="length" if zu_lang else "stop")])
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


def test_a_truncated_answer_is_split_in_half_and_both_halves_are_sent():
    calls = []
    packet = [_block(i, f"Termin am 14.03.2026 Nr. {i}") for i in range(4)]
    items = extract_packet(_client_that_truncates_big_packets(calls, 2), "m", packet, HEUTE)
    assert sorted(i["id"] for i in items) == [0, 1, 2, 3]
    assert len(calls) == 3


def test_a_truncated_single_block_gives_up_instead_of_splitting_forever():
    calls = []
    packet = [_block(0, "Termin am 14.03.2026")]
    with pytest.raises(ValueError, match="abgeschnitten"):
        extract_packet(_client_that_truncates_big_packets(calls, 0), "m", packet, HEUTE)
    assert len(calls) == 1
