"""One link and a pasted transcript become one YouTube source, every rejection comes back before a row exists."""
import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.sources import _youtube
from src.services.web_page_fetch import LinkError

WS = {"id": 7, "uuid": "w1", "user_id": 42}
LINK = "https://youtu.be/dQw4w9WgXcQ"
KANONISCH = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TRANSKRIPT = "0:00\nHallo und willkommen\n0:04\nHeute geht es um Photosynthese\n"


@pytest.fixture
def route(monkeypatch):
    """Everything around the route stubbed, the calls recorded."""
    calls = {"existing": []}
    monkeypatch.setattr(_youtube, "_require_workspace_manage", lambda *a, **k: WS)
    monkeypatch.setattr(_youtube, "check_upload_limit", lambda *a, **k: None)
    monkeypatch.setattr(_youtube, "record_upload", lambda uid: calls.setdefault("recorded", []).append(uid))
    monkeypatch.setattr(_youtube.db, "get_aia_sources_by_workspace", lambda wid: calls["existing"])
    monkeypatch.setattr(_youtube, "_require_source_capacity", lambda *a, **k: None)
    monkeypatch.setattr(_youtube, "_workspace_label", lambda locale: "Modul")
    monkeypatch.setattr(_youtube, "fetch_title", lambda video_id: "Photosynthese einfach erklärt")

    def _save(user_id, workspace_uuid, source_uuid, vtt):
        calls["saved"] = {"owner": user_id, "workspace": workspace_uuid, "vtt": vtt}
        return f"users/{user_id}/aia/workspaces/{workspace_uuid}/sources/{source_uuid}.youtube"

    monkeypatch.setattr(_youtube, "save_aia_provided_transcript", _save)

    def _create(**kwargs):
        calls["created"] = kwargs
        return 1

    monkeypatch.setattr(_youtube.db, "create_aia_source", _create)
    monkeypatch.setattr(
        _youtube, "_enqueue_index_source",
        lambda source_uuid, uid, locale: calls.setdefault("enqueued", []).append(source_uuid),
    )
    return calls


async def _aufruf(url=LINK, transcript=TRANSKRIPT):
    return await _youtube.add_youtube_source(
        workspace_uuid="w1", body=_youtube.YoutubeBody(url=url, transcript=transcript),
        current_user={"user_id": 42}, locale="de",
    )


@pytest.mark.asyncio
async def test_link_und_transkript_werden_eine_quelle(route):
    antwort = await _aufruf()

    assert antwort["status"] == "pending"
    assert antwort["filename"] == "Photosynthese einfach erklärt.youtube"
    assert antwort["source_url"] == KANONISCH
    assert route["created"]["file_type"] == "youtube"
    assert route["created"]["source_url"] == KANONISCH
    assert route["created"]["filename"] == antwort["filename"]
    assert route["created"]["file_path"].endswith(f"/sources/{antwort['uuid']}.youtube")
    assert route["saved"]["owner"] == 42
    assert route["saved"]["vtt"].startswith("WEBVTT")
    assert "00:00:04.000 --> 00:00:09.000" in route["saved"]["vtt"]
    assert route["enqueued"] == [antwort["uuid"]]
    assert route["recorded"] == [42]


@pytest.mark.asyncio
async def test_ungueltiger_link_gibt_400_und_zaehlt_nicht(route):
    with pytest.raises(HTTPException) as exc:
        await _aufruf(url="https://vimeo.com/12345")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Das ist kein Link auf ein YouTube-Video."
    assert "created" not in route and "recorded" not in route


@pytest.mark.asyncio
async def test_transkript_ohne_zeitstempel_gibt_400(route):
    with pytest.raises(HTTPException) as exc:
        await _aufruf(transcript="Hallo und willkommen\nHeute geht es um Photosynthese")

    assert exc.value.status_code == 400
    assert exc.value.detail.startswith("Im Transkript fehlen die Zeitstempel.")
    assert "created" not in route


@pytest.mark.asyncio
async def test_dasselbe_video_gibt_409(route, monkeypatch):
    route["existing"] = [{"filename": "x.youtube", "source_url": KANONISCH}]
    monkeypatch.setattr(_youtube, "fetch_title", lambda video_id: pytest.fail("darf nicht holen"))

    with pytest.raises(HTTPException) as exc:
        await _aufruf(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Dieses Video ist schon im Modul."
    assert "created" not in route


@pytest.mark.asyncio
async def test_nicht_einbettbar_gibt_400(route, monkeypatch):
    def _sperre(video_id):
        raise LinkError("ai.youtube.notEmbeddable", 400)

    monkeypatch.setattr(_youtube, "fetch_title", _sperre)

    with pytest.raises(HTTPException) as exc:
        await _aufruf()

    assert exc.value.status_code == 400
    assert "nicht einbetten" in exc.value.detail
    assert "created" not in route


@pytest.mark.asyncio
async def test_namenskollision_haengt_eine_zahl_an(route):
    route["existing"] = [{"filename": "Photosynthese einfach erklärt.youtube", "source_url": None}]

    antwort = await _aufruf()

    assert antwort["filename"] == "Photosynthese einfach erklärt (2).youtube"
