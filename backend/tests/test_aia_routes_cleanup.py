"""Checks the shared helpers the workspace routes were tidied onto."""
import types
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _chat_setup, _workspace_access
from src.features.ai_assistant.routes import workspaces as ws_routes
from src.features.ai_assistant.routes._text import _json_object_text
from src.features.ai_assistant.routes.sources import _pdf, _shared
from src.features.ai_assistant.routes.studio import schedule as schedule_route


# ── access links and expiry ──────────────────────────────────────────────────

def test_iso_z_never_carries_an_offset_before_the_z():
    aware = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)
    assert ws_routes._iso_z(aware) == "2026-12-01T10:00:00Z"
    assert ws_routes._iso_z(datetime(2026, 12, 1, 10, 0)) == "2026-12-01T10:00:00Z"
    assert ws_routes._iso_z(None) is None


def test_legacy_fields_prefer_the_first_link():
    links = [{"code": "abc", "expires_at": None}]
    assert ws_routes._legacy_enroll_fields(links, {"enroll_code": "old"}) == {
        "enroll_code": "abc", "enroll_code_expires": None}
    assert ws_routes._legacy_enroll_fields([], {"enroll_code": "old"}) == {
        "enroll_code": "old", "enroll_code_expires": None}


def test_a_bad_expiry_creates_no_workspace(monkeypatch):
    created = []
    monkeypatch.setattr(ws_routes.db, "create_aia_workspace", lambda *a: created.append(a) or "w-1")
    with pytest.raises(HTTPException) as err:
        ws_routes.create_workspace("Titel", None, "not-a-date", {"user_id": 1}, "de")
    assert err.value.status_code == 400
    assert created == []


def test_create_returns_a_readable_expiry(monkeypatch):
    monkeypatch.setattr(ws_routes.db, "create_aia_workspace", lambda *a: "w-1")
    monkeypatch.setattr(ws_routes.db, "get_aia_workspace", lambda uuid: {"id": 7, "uuid": uuid})
    monkeypatch.setattr(ws_routes.db, "create_access_link",
                        lambda wid, code, expires: {"id": 3, "code": code,
                                                    "expires_at": datetime(2026, 12, 1, 10, 0)})
    monkeypatch.setattr(ws_routes.db, "set_aia_workspace_enroll_code", lambda *a: None)
    out = ws_routes.create_workspace("Titel", None, "2026-12-01T10:00:00", {"user_id": 1}, "de")
    assert out["enroll_code_expires"] == "2026-12-01T10:00:00Z"
    assert out["access_links"][0]["expires_at"] == "2026-12-01T10:00:00Z"


# ── renaming a studio row ────────────────────────────────────────────────────

def _rename(monkeypatch, title, renamed=True):
    monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: {"id": 7, "user_id": 1})
    monkeypatch.setattr(_workspace_access.db, "update_artifact_title", lambda *a: renamed)
    return _workspace_access._rename_artifact("mindmap", "w-1", 5, title, 1, "de", "mindmap.notFound")


def test_rename_cleans_the_title(monkeypatch):
    assert _rename(monkeypatch, "  Neuer   Name ") == {"ok": True, "title": "Neuer Name"}


def test_rename_rejects_an_empty_title(monkeypatch):
    with pytest.raises(HTTPException) as err:
        _rename(monkeypatch, "   ")
    assert err.value.status_code == 400


def test_rename_hides_someone_elses_row(monkeypatch):
    with pytest.raises(HTTPException) as err:
        _rename(monkeypatch, "Name", renamed=False)
    assert err.value.status_code == 404


# ── transcript language code ─────────────────────────────────────────────────

def test_clean_lang_lowercases_and_trims():
    assert _shared._clean_lang(" DE ", "de") == "de"


@pytest.mark.parametrize("bad", ["", None, "d", "de-DE", "../x", "abcdef"])
def test_clean_lang_rejects_anything_else(bad):
    with pytest.raises(HTTPException) as err:
        _shared._clean_lang(bad, "de")
    assert err.value.status_code == 400


# ── chat setup ───────────────────────────────────────────────────────────────

def test_only_sources_of_this_workspace_are_resolved(monkeypatch):
    rows = {"a": {"id": 1, "workspace_id": 7}, "b": {"id": 2, "workspace_id": 8}}
    monkeypatch.setattr(_chat_setup.db, "get_aia_source", lambda uuid: rows.get(uuid))
    ids, by_id = _chat_setup.resolve_active_sources(["a", "b", "missing"], 7)
    assert ids == [1]
    assert by_id == {1: rows["a"]}


def test_no_usable_selection_is_none(monkeypatch):
    monkeypatch.setattr(_chat_setup.db, "get_aia_source", lambda uuid: None)
    assert _chat_setup.resolve_active_sources(None, 7) == (None, {})
    assert _chat_setup.resolve_active_sources(["x"], 7) == (None, {})


def _body(**kw):
    base = dict(source_text="markiert", source_uuid="s-1", source_page=4,
                source_filename="a.pdf", action_key=None)
    return types.SimpleNamespace(**{**base, **kw})


def test_a_selection_becomes_a_note():
    entry = _chat_setup.popup_selection_entry(_body())
    assert entry == {"source_uuid": "s-1", "filename": "a.pdf", "page_number": 4,
                     "source_text": "markiert", "is_popup_selection": True}


def test_a_known_action_adds_its_icon():
    from src.features.ai_assistant.prompts.popup_prompts import AIA_POPUP_ACTIONS
    action = AIA_POPUP_ACTIONS[0]
    entry = _chat_setup.popup_selection_entry(_body(action_key=action["key"]))
    assert entry["action_key"] == action["key"]
    assert entry["action_icon"] == action["icon"]
    assert "action_key" not in _chat_setup.popup_selection_entry(_body(action_key="unknown"))


def test_without_a_page_it_is_no_selection():
    assert _chat_setup.popup_selection_entry(_body(source_page=None)) is None


def test_a_workspace_without_a_ready_source_refuses(monkeypatch):
    monkeypatch.setattr(_chat_setup.db, "get_aia_sources_by_workspace",
                        lambda wid: [{"status": "indexing"}])
    with pytest.raises(HTTPException) as err:
        _chat_setup.heal_workspace_status({"id": 7, "uuid": "w-1", "status": "pending"}, "de")
    assert err.value.status_code == 409


def test_a_stale_pending_is_healed_only_when_all_are_ready(monkeypatch):
    healed = []
    monkeypatch.setattr(_chat_setup.db, "update_aia_workspace_status",
                        lambda uuid, status: healed.append((uuid, status)))
    monkeypatch.setattr(_chat_setup.db, "get_aia_sources_by_workspace",
                        lambda wid: [{"status": "ready"}, {"status": "indexing"}])
    _chat_setup.heal_workspace_status({"id": 7, "uuid": "w-1", "status": "pending"}, "de")
    assert healed == []
    monkeypatch.setattr(_chat_setup.db, "get_aia_sources_by_workspace",
                        lambda wid: [{"status": "ready"}])
    _chat_setup.heal_workspace_status({"id": 7, "uuid": "w-1", "status": "pending"}, "de")
    assert healed == [("w-1", "ready")]


# ── JSON object in a model answer ────────────────────────────────────────────

def test_json_object_survives_thinking_and_fences():
    raw, blob = _json_object_text('<think>x {a}</think>```json\n{"intent": "GENERIC"}\n```')
    assert blob == '{"intent": "GENERIC"}'
    assert "<think>" not in raw and "```" not in raw


def test_no_json_object_is_none():
    assert _json_object_text("GENERIC")[1] is None
    assert _json_object_text(None) == ("", None)


# ── PDF search boxes ─────────────────────────────────────────────────────────

class _Textpage:
    def __init__(self, boxes):
        self._boxes = boxes

    def get_charbox(self, i, loose=True):
        return self._boxes[i]


def test_a_match_over_two_lines_gets_two_boxes():
    page = _Textpage([(0, 100, 5, 110), (5, 100, 10, 110),
                      (10, 100, 12, 100),            # a space without height is skipped
                      (0, 80, 6, 90)])
    assert _pdf._line_rects(page, 0, 4) == [(0, 100, 10, 110), (0, 80, 6, 90)]


# ── schedule entry ───────────────────────────────────────────────────────────

def test_both_schedule_lists_share_the_date_fields():
    row = {"id": 1, "type": "termin", "title": "T", "due_date": datetime(2026, 1, 2).date(),
           "is_optional": False, "is_checked": False, "origin": "manual",
           "workspace_uuid": "w", "module_title": "M", "module_relation": "owned"}
    entry = schedule_route._serialize_entry(row)
    glob = schedule_route._serialize_global_entry(row)
    assert entry["due_date"] == glob["due_date"] == "2026-01-02"
    assert entry["date_precision"] == glob["date_precision"] == "day"
    assert list(entry)[:4] == ["id", "type", "title", "description"]
