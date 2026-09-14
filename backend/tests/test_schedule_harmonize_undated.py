"""The title harmonisation takes the undated appointments along, but carefully."""

import json
import types
from datetime import date

from src.features.ai_assistant.tasks.studio.schedule import _harmonize as mod

HEUTE = date(2026, 8, 13)


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


def _cand(date_iso=None, tbd=False):
    return {"date_iso": date_iso, "partial_date": None, "is_tbd": tbd}


def _cls(title):
    return {"keep": True, "is_footer": False, "is_header": False,
            "is_historical": False, "title": title, "type": "termin",
            "description": None, "due_time": None, "is_optional": False}


def test_offene_termine_bekommen_einen_gemeinsamen_titel():
    cands = [_cand(tbd=True), _cand(tbd=True)]
    cls = [_cls("Präsentation: Hausarbeit"), _cls("Präsentationen: online")]
    client, _ = _make_client({"groups": [
        {"ids": ["c0", "c1"], "canonical_title": "Präsentationen (nach Vereinbarung)"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert cls[0]["title"] == "Präsentationen (nach Vereinbarung)"
    assert cls[1]["title"] == "Präsentationen (nach Vereinbarung)"


def test_die_anfrage_warnt_vor_dem_leeren_datum():
    """For the undated group the query has to undo the merging."""
    cands = [_cand(tbd=True), _cand(tbd=True)]
    cls = [_cls("Präsentation"), _cls("Sprechstunde")]
    client, calls = _make_client({"groups": []})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    frage = calls[0][1]["content"]
    assert "NO fixed date" in frage
    assert "does NOT apply" in frage
    assert "Date: " not in frage


def test_verschiedene_offene_termine_bleiben_getrennt():
    cands = [_cand(tbd=True), _cand(tbd=True)]
    cls = [_cls("Präsentation"), _cls("Sprechstunde")]
    client, _ = _make_client({"groups": [
        {"ids": ["c0"], "canonical_title": "Präsentation"},
        {"ids": ["c1"], "canonical_title": "Sprechstunde"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert cls[0]["title"] == "Präsentation"
    assert cls[1]["title"] == "Sprechstunde"


def test_vorhandener_eintrag_ohne_datum_gibt_den_titel_vor():
    cands = [_cand(tbd=True)]
    cls = [_cls("Präsentation: Hausarbeit")]
    vorhanden = [{"id": 7, "due_date": None, "title": "Präsentationen: online",
                  "description": None, "type": "termin"}]
    client, calls = _make_client({"groups": [
        {"ids": ["c0", "e7"], "canonical_title": "Präsentationen: online"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, vorhanden)

    assert cls[0]["title"] == "Präsentationen: online"
    assert '"e7"' in calls[0][1]["content"]


def test_eintraege_mit_datum_laufen_wie_vorher():
    cands = [_cand("2026-05-29"), _cand("2026-05-29")]
    cls = [_cls("Peer-Review"), _cls("Online-Präsenz: Peer-Review")]
    client, calls = _make_client({"groups": [
        {"ids": ["c0", "c1"], "canonical_title": "Online-Präsenz: Peer-Review"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert cls[0]["title"] == "Online-Präsenz: Peer-Review"
    assert "Date: 2026-05-29" in calls[0][1]["content"]


def test_datum_und_kein_datum_stehen_als_zwei_abschnitte_in_einer_anfrage():
    cands = [_cand("2026-05-29"), _cand(tbd=True), _cand(tbd=True)]
    cls = [_cls("Peer-Review"), _cls("Präsentation"), _cls("Präsentationen: online")]
    client, calls = _make_client({"groups": []})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [
        {"id": 1, "due_date": date(2026, 5, 29), "title": "Online-Präsenz: Peer-Review",
         "description": None, "type": "termin"},
    ])

    assert len(calls) == 1
    frage = calls[0][1]["content"]
    assert "Date: 2026-05-29" in frage
    assert "NO fixed date" in frage


def test_mehrere_tage_mit_ankern_kosten_eine_anfrage():
    cands = [_cand("2026-05-29"), _cand("2026-06-27"), _cand("2026-07-03")]
    cls = [_cls("Peer-Review"), _cls("Schreibwerkstatt"), _cls("Abgabe")]
    anker = [{"id": i, "due_date": d, "title": t, "description": None, "type": "termin"}
             for i, d, t in ((1, date(2026, 5, 29), "Online-Präsenz: Peer-Review"),
                             (2, date(2026, 6, 27), "Online-Präsenz: Schreibwerkstatt"),
                             (3, date(2026, 7, 3), "Abgabe: Hausarbeit"))]
    client, calls = _make_client({"groups": [
        {"ids": ["c0", "e1"], "canonical_title": "Online-Präsenz: Peer-Review"},
        {"ids": ["c1", "e2"], "canonical_title": "Online-Präsenz: Schreibwerkstatt"},
        {"ids": ["c2", "e3"], "canonical_title": "Abgabe: Hausarbeit"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, anker)

    assert len(calls) == 1
    frage = calls[0][1]["content"]
    assert frage.count("Date: ") == 3
    assert [c["title"] for c in cls] == ["Online-Präsenz: Peer-Review",
                                         "Online-Präsenz: Schreibwerkstatt", "Abgabe: Hausarbeit"]


def test_eine_gruppe_ueber_zwei_tage_wird_verworfen():
    cands = [_cand("2026-05-29"), _cand("2026-05-29"), _cand("2026-06-27"), _cand("2026-06-27")]
    cls = [_cls("Peer-Review"), _cls("Review"), _cls("Werkstatt"), _cls("Schreibwerkstatt")]
    client, _ = _make_client({"groups": [
        {"ids": ["c0", "c2"], "canonical_title": "Falsch zusammengelegt"},
        {"ids": ["c1"], "canonical_title": "Review"},
        {"ids": ["c3"], "canonical_title": "Schreibwerkstatt"},
    ]})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert cls[0]["title"] == "Peer-Review"
    assert cls[2]["title"] == "Werkstatt"


def test_ein_einzelner_offener_termin_kostet_keine_anfrage():
    cands = [_cand(tbd=True)]
    cls = [_cls("Präsentation")]
    client, calls = _make_client({"groups": []})

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert calls == []


def test_ein_fehler_beim_abgleich_laesst_die_titel_stehen():
    def create(model, messages, **kwargs):
        raise RuntimeError("Anbieter down")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    cands = [_cand(tbd=True), _cand(tbd=True)]
    cls = [_cls("Präsentation"), _cls("Präsentationen: online")]

    mod._harmonize_same_date_titles(client, "m", cands, cls, HEUTE, [])

    assert cls[0]["title"] == "Präsentation"
    assert cls[1]["title"] == "Präsentationen: online"
