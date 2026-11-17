"""The AI assistant uses the shared direct upload: its rule checks the room, from-upload makes the source."""
import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.sources import _from_upload as fu
from src.services import direct_upload as du

WS = {"id": 7, "uuid": "w1", "user_id": 42}
SESSION = {"tool": "aia", "user_id": 42, "context": {"workspace_uuid": "w1"}, "key": "tmp/uploads/42/tok.webm",
           "upload_id": "up", "filename": "Vorlesung.webm", "ext": ".webm", "size": 100, "done": True}


@pytest.fixture
def room(monkeypatch):
    """Database, storage and queue stubbed, every call recorded."""
    state = {"existing": [], "created": [], "copied": [], "released": [], "enqueued": [], "recorded": [],
             "session": dict(SESSION), "manage": []}

    def manage(workspace_uuid, user_id, locale="de"):
        state["manage"].append((workspace_uuid, user_id))
        if workspace_uuid != "w1":
            raise HTTPException(status_code=404, detail="not found")
        return WS

    monkeypatch.setattr(fu, "_require_workspace_manage", manage)
    monkeypatch.setattr(fu, "_require_source_capacity", lambda *a, **k: None)
    monkeypatch.setattr(fu.db, "get_aia_sources_by_workspace", lambda wid: state["existing"])
    monkeypatch.setattr(fu.db, "create_aia_source", lambda **kw: state["created"].append(kw))
    monkeypatch.setattr(fu, "copy_key", lambda src, dst: state["copied"].append((src, dst)))
    monkeypatch.setattr(fu, "_enqueue_index_source", lambda *a: state["enqueued"].append(a[0]))
    monkeypatch.setattr(fu.direct_upload, "take", lambda token, tool, uid, loc: state["session"])
    monkeypatch.setattr(fu.direct_upload, "release", lambda token, session: state["released"].append(token))
    return state


def _from_upload(workspace_uuid="w1"):
    return fu.source_from_upload(workspace_uuid=workspace_uuid, body=fu.FromUpload(upload_token="tok"),
                                 current_user={"user_id": 42}, locale="de")


def test_der_lernassistent_ist_beim_kern_angemeldet():
    rule = du.RULES["aia"]
    assert ".webm" in rule.extensions and ".pdf" in rule.extensions


def test_anmeldung_prueft_rechte_am_raum(room):
    fu._precheck({"user_id": 42}, {"workspace_uuid": "w1"}, "neu.pdf", 10, "de")
    assert room["manage"] == [("w1", 42)]
    with pytest.raises(HTTPException) as err:
        fu._precheck({"user_id": 42}, {"workspace_uuid": "fremd"}, "neu.pdf", 10, "de")
    assert err.value.status_code == 404


def test_anmeldung_lehnt_gleichen_namen_ab(room):
    room["existing"] = [{"filename": "NEU.pdf"}]
    with pytest.raises(HTTPException) as err:
        fu._precheck({"user_id": 42}, {"workspace_uuid": "w1"}, "neu.pdf", 10, "de")
    assert err.value.status_code == 409


def test_fertiger_upload_wird_zur_quelle(room):
    answer = _from_upload()
    assert answer["filename"] == "Vorlesung.webm" and answer["status"] == "pending"
    src, dst = room["copied"][0]
    assert src == "tmp/uploads/42/tok.webm"
    assert dst.startswith("users/42/aia/workspaces/w1/sources/") and dst.endswith(".webm")
    assert room["released"] == ["tok"]
    assert room["created"][0]["file_path"] == dst and room["created"][0]["file_type"] == "webm"
    assert room["enqueued"] == [answer["uuid"]]


def test_upload_fuer_einen_anderen_raum_wird_nicht_angenommen(room):
    room["session"] = {**SESSION, "context": {"workspace_uuid": "anderer"}}
    with pytest.raises(HTTPException) as err:
        _from_upload()
    assert err.value.status_code == 404
    assert room["created"] == [] and room["copied"] == []


def test_inzwischen_gleicher_name_legt_nichts_an(room):
    room["existing"] = [{"filename": "vorlesung.WEBM"}]
    with pytest.raises(HTTPException) as err:
        _from_upload()
    assert err.value.status_code == 409
    assert room["created"] == [] and room["released"] == []
