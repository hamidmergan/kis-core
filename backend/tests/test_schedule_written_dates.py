"""The model reads spelled-out dates, numbers stay with the pattern."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.studio.schedule import _candidates as cand_mod
from src.features.ai_assistant.tasks.studio.schedule import _discover as mod


def _make_client(payload):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _src():
    return {"id": 1, "uuid": "u-1", "filename": "plan.pdf"}


def _chunks(*texts):
    return [
        {"id": i, "content": t, "page_number": i + 1, "start_time": None}
        for i, t in enumerate(texts)
    ]


# --- the numeric form the model delivers along --------------------------------

def test_ganzes_datum():
    assert mod._parse_model_date("2026-07-03") == {
        "date_iso": "2026-07-03", "partial_date": None, "date_precision": "day"}


def test_monat_mit_jahr_behaelt_seine_ungenauigkeit():
    """The first of the month is only the sort key, the precision stays 'month'."""
    assert mod._parse_model_date("2026-07") == {
        "date_iso": "2026-07-01", "partial_date": None, "date_precision": "month"}


def test_tag_und_monat_ohne_jahr():
    assert mod._parse_model_date("07-03") == {
        "date_iso": None, "partial_date": [7, 3], "date_precision": "day"}


@pytest.mark.parametrize("wert", [
    "", "irgendwas", "2026", "3. Juli 2026", "2026-13-01", "2026-02-30",
    "26-07-03", "2026-07-3", "07-32", "13-01",
])
def test_unbrauchbare_ziffernformen_fallen_raus(wert):
    assert mod._parse_model_date(wert) is None


# --- what becomes of the model answer -----------------------------------------

def test_daten_kommen_je_block_zurueck():
    client, _ = _make_client({"results": [], "dates": [
        {"id": 0, "phrase": "3 Temmuz 2026", "date": "2026-07-03"},
    ]})

    found = mod._discover_in_blocks(client, "m", [(0, "Teslim tarihi 3 Temmuz 2026 saat 10:00")])

    assert found[0]["dates"] == [
        {"phrase": "3 Temmuz 2026", "date_iso": "2026-07-03",
         "partial_date": None, "date_precision": "day"},
    ]


def test_ein_block_kann_beides_liefern():
    client, _ = _make_client({
        "results": [{"id": 0, "phrase": "tarih daha sonra duyurulacak"}],
        "dates": [{"id": 0, "phrase": "3 Temmuz 2026", "date": "2026-07-03"}],
    })

    found = mod._discover_in_blocks(client, "m", [
        (0, "Sinav 3 Temmuz 2026. Sunum tarih daha sonra duyurulacak."),
    ])

    assert found[0]["tbd"] == "tarih daha sonra duyurulacak"
    assert len(found[0]["dates"]) == 1


def test_kaputte_ziffernform_verwirft_nur_diesen_fund():
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "3 Temmuz 2026", "date": "irgendwann"},
        {"id": 0, "phrase": "5 Temmuz 2026", "date": "2026-07-05"},
    ]})

    found = mod._discover_in_blocks(client, "m", [(0, "3 Temmuz 2026 und 5 Temmuz 2026")])

    assert [d["date_iso"] for d in found[0]["dates"]] == ["2026-07-05"]


def test_zu_viele_daten_je_block_werden_gedeckelt():
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": f"{i} Temmuz 2026", "date": f"2026-07-{i:02d}"}
        for i in range(1, 12)
    ]})

    found = mod._discover_in_blocks(client, "m", [(0, "x" * 200)])

    assert len(found[0]["dates"]) == mod._MAX_DATES_PER_BLOCK


# --- what becomes of it in the schedule ---------------------------------------

def test_tuerkisches_datum_wird_zum_kandidaten(monkeypatch):
    chunks = _chunks("Ders programi\nTeslim tarihi 3 Temmuz 2026 saat 10:00")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "3 Temmuz 2026", "date": "2026-07-03"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len(out) == 1
    assert out[0]["date_iso"] == "2026-07-03"
    assert out[0]["date_raw"] == "3 Temmuz 2026"
    assert out[0]["date_precision"] == "day"
    assert out[0]["page_number"] == 1


def test_monat_ohne_tag_behaelt_seine_genauigkeit(monkeypatch):
    chunks = _chunks("Die Abgabe der Hausarbeit erfolgt im Juli 2026.")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "im Juli 2026", "date": "2026-07"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert out[0]["date_iso"] == "2026-07-01"
    assert out[0]["date_precision"] == "month"


def test_erfundenes_datum_wird_verworfen(monkeypatch):
    """The spot has to appear verbatim in the text, otherwise the entry points at nothing."""
    chunks = _chunks("Die Vorlesung findet woechentlich statt.")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "3 Temmuz 2026", "date": "2026-07-03"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert out == []


def test_was_der_regex_schon_hat_kommt_nicht_doppelt(monkeypatch):
    """The model reports the same spot again, that is one appointment, not two."""
    chunks = _chunks("Abgabe am 03.07.2026 um 18:00 Uhr")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "03.07.2026", "date": "2026-07-03"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len(out) == 1
    assert out[0]["date_raw"] == "03.07.2026"


def test_deutsches_datum_und_fremdes_datum_nebeneinander(monkeypatch):
    chunks = _chunks("Klausur am 03.07.2026, Nachholtermin 5 Temmuz 2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"dates": [
        {"id": 0, "phrase": "5 Temmuz 2026", "date": "2026-07-05"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert sorted(c["date_iso"] for c in out) == ["2026-07-03", "2026-07-05"]


def test_ohne_modell_bleibt_es_beim_suchmuster(monkeypatch):
    chunks = _chunks("Klausur am 03.07.2026, Nachholtermin 5 Temmuz 2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert [c["date_iso"] for c in out] == ["2026-07-03"]


def test_jeder_kandidat_traegt_eine_genauigkeit(monkeypatch):
    """Otherwise every spot further down has to guess what is missing."""
    chunks = _chunks("Abgabe 03.07.2026 und Sprechstunde nach Vereinbarung, 15. April")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert out and all(c["date_precision"] in ("day", "month") for c in out)
