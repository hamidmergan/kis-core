"""One packet per source, an interrupted run keeps the sources it already finished."""

import threading
import time
import types

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from src.features.ai_assistant.tasks.studio import schedule as job

BLOCK = "Klausur am 14.03.2026"


def _chunk(cid: int, text: str = BLOCK) -> dict:
    return {"id": cid, "content": text, "page_number": 1, "start_time": None}


def _item(cid: int) -> dict:
    return {"id": cid, "date": "2026-03-14", "end_date": None, "time": None, "end_time": None,
            "type": "termin", "title": "Klausur", "description": None, "quote": BLOCK,
            "open_ended": False, "optional": False}


@pytest.fixture
def welt(monkeypatch):
    state = {"gespeichert": [], "inhalt": {}, "erledigt": [], "job": {}, "pakete": []}
    quellen = {f"u{i}": {"id": i, "uuid": f"u{i}", "filename": f"q{i}.pdf", "workspace_id": 7}
               for i in (1, 2, 3)}
    lock = threading.Lock()

    def db(name, fn):
        monkeypatch.setattr(job.db, name, fn)

    def speichern(sid, c, cl):
        state["gespeichert"].append(sid)
        state["inhalt"][sid] = (c, cl)

    db("update_schedule_job", lambda jid, status, **kw: state["job"].update(status=status, **kw))
    db("get_aia_source", lambda u: quellen.get(u))
    db("get_processed_source_ids", lambda w, u: [])
    db("get_source_extraction", lambda sid: None)
    db("upsert_source_extraction", speichern)
    db("mark_source_processed", lambda w, u, sid: state["erledigt"].append(sid))
    db("get_schedule_entries", lambda w, u: [])
    db("get_schedule_entries_for_workspace", lambda w: [])
    db("hybrid_search_chunks", lambda *a, **k: [])
    db("create_schedule_entry", lambda *a, **k: {"id": 1, **k})

    monkeypatch.setattr("src.services.aia_embeddings.get_embedding_provider_with_fallback",
                        lambda **kw: types.SimpleNamespace(embed_one=lambda t: [0.0]))
    monkeypatch.setattr(job, "_get_llm_client", lambda: (object(), "m", None))
    # Two dated blocks per source, one packet per source, one at a time for a fixed order.
    monkeypatch.setattr(job, "_load_source_chunks",
                        lambda sid: [_chunk(sid * 10 + 1), _chunk(sid * 10 + 2)])
    monkeypatch.setattr(job, "_transcript_index", lambda src, chunks: None)
    monkeypatch.setattr(job, "tool_context_budget", lambda: 3 * len(BLOCK) + 2)
    monkeypatch.setattr(job, "_harmonize_same_date_titles", lambda *a, **k: None)
    monkeypatch.setattr(job, "parallel_packets", lambda pakete: 1)

    def extract(client, model, paket, today):
        with lock:
            state["pakete"].append([b["id"] for b in paket])
        return []

    monkeypatch.setattr(job, "extract_packet", extract)
    return state


def _lauf():
    job.run_generate_schedule.run(1, 7, 5, ["u1", "u2", "u3"])


def _bricht_ab_wenn_block_dabei(state, block_id, fehler):
    """The packet holding this block fails, the others answer empty."""
    def extract(client, model, paket, today):
        ids = [b["id"] for b in paket]
        state["pakete"].append(ids)
        if block_id in ids:
            raise fehler
        return []
    return extract


def test_a_clean_run_saves_every_source(welt):
    _lauf()
    assert sorted(welt["pakete"]) == [[11, 12], [21, 22], [31, 32]]
    assert sorted(welt["gespeichert"]) == [1, 2, 3]
    assert welt["erledigt"] == [1, 2, 3]
    assert welt["job"]["status"] == "success"


def test_a_source_split_over_two_packets_is_saved_only_when_both_are_through(welt, monkeypatch):
    monkeypatch.setattr(job, "tool_context_budget", lambda: len(BLOCK))
    monkeypatch.setattr(job, "extract_packet",
                        _bricht_ab_wenn_block_dabei(welt, 22, SoftTimeLimitExceeded()))
    _lauf()
    assert welt["gespeichert"] == [1]


def test_an_unfinished_source_is_not_marked_done(welt, monkeypatch):
    monkeypatch.setattr(job, "extract_packet",
                        _bricht_ab_wenn_block_dabei(welt, 22, SoftTimeLimitExceeded()))
    _lauf()
    assert welt["erledigt"] == [1]
    assert welt["job"]["status"] == "success"


def test_a_failing_packet_keeps_the_sources_of_the_other_packets(welt, monkeypatch):
    monkeypatch.setattr(job, "extract_packet",
                        _bricht_ab_wenn_block_dabei(welt, 22, RuntimeError("kaputt")))
    _lauf()
    assert welt["gespeichert"] == [1, 3]
    assert welt["job"]["status"] == "success"


def test_when_every_packet_fails_the_job_fails(welt, monkeypatch):
    def extract(client, model, paket, today):
        raise RuntimeError("kaputt")
    monkeypatch.setattr(job, "extract_packet", extract)
    _lauf()
    assert welt["gespeichert"] == []
    assert welt["job"]["status"] == "failed"
    assert "kaputt" in welt["job"]["error"]


def test_a_source_without_a_dated_block_is_saved_empty_without_a_call(welt, monkeypatch):
    monkeypatch.setattr(job, "_load_source_chunks",
                        lambda sid: [_chunk(sid * 10 + 1, "kein Datum")] if sid == 2
                        else [_chunk(sid * 10 + 1), _chunk(sid * 10 + 2)])
    _lauf()
    assert sorted(welt["pakete"]) == [[11, 12], [31, 32]]
    assert welt["gespeichert"][0] == 2
    assert welt["inhalt"][2] == ([], [])
    assert welt["erledigt"] == [1, 2, 3]


def test_a_cached_source_sends_no_blocks(welt, monkeypatch):
    monkeypatch.setattr(job.db, "get_source_extraction",
                        lambda sid: {"candidates": [], "classifications": []} if sid == 2 else None)
    _lauf()
    assert sorted(welt["pakete"]) == [[11, 12], [31, 32]]
    assert sorted(welt["gespeichert"]) == [1, 3]
    assert welt["erledigt"] == [1, 2, 3]


def test_found_appointments_are_saved_with_their_source_in_packet_order(welt, monkeypatch):
    def extract(client, model, paket, today):
        return [_item(b["id"]) for b in paket if b["id"] in (21, 22)]
    monkeypatch.setattr(job, "extract_packet", extract)
    _lauf()
    cands, cls = welt["inhalt"][2]
    assert [c["date_iso"] for c in cands] == ["2026-03-14", "2026-03-14"]
    assert cls[0]["keep"] is True and cls[0]["title"] == "Klausur"
    assert welt["inhalt"][1] == ([], [])
    assert welt["job"]["added_count"] == 1


def test_small_packets_run_side_by_side(welt, monkeypatch):
    from src.features.ai_assistant.tasks.studio.schedule import _extract
    monkeypatch.setattr(job, "parallel_packets", _extract.parallel_packets)
    monkeypatch.setattr(job, "tool_context_budget", lambda: len(BLOCK))
    zaehler = {"jetzt": 0, "hoechst": 0}
    lock = threading.Lock()

    def extract(client, model, paket, today):
        with lock:
            zaehler["jetzt"] += 1
            zaehler["hoechst"] = max(zaehler["hoechst"], zaehler["jetzt"])
        time.sleep(0.02)
        with lock:
            zaehler["jetzt"] -= 1
        return []

    monkeypatch.setattr(job, "extract_packet", extract)
    _lauf()
    assert zaehler["hoechst"] == 6
    assert sorted(welt["gespeichert"]) == [1, 2, 3]
