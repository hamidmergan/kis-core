"""Deleting a source has to take transcript and subtitles along."""

from src import storage
from src.features.ai_assistant.routes import _helpers
from src.features.ai_assistant.routes.sources import _upload

# Names as in operation so no source is a prefix of another.
EINS = "0a1b2c3d4e5f60718293a4b5c6d7e8f9"
ZWEI = "0a1b2c3d4e5f60718293a4b5c6d7ffff"


def _quelle_anlegen(wurzel, user_id: int, ws_uuid: str, source_uuid: str):
    """Creates video, transcript and two subtitle files and returns the folder."""
    ordner = wurzel / f"users/{user_id}/aia/workspaces/{ws_uuid}/sources"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{source_uuid}.mp4").write_bytes(b"video")
    (ordner / f"{source_uuid}_transcript.txt").write_bytes(b"volltext")
    (ordner / f"{source_uuid}_transcript.de.vtt").write_bytes(b"de")
    (ordner / f"{source_uuid}_transcript.en.vtt").write_bytes(b"en")
    return ordner


def _route_loeschen(monkeypatch, ordner, source_uuid: str) -> None:
    """Calls the delete route with the access check and the database stubbed out."""
    workspace = {"id": 7, "uuid": "w1", "user_id": 42}
    source = {"uuid": source_uuid, "workspace_id": 7, "file_path": str(ordner / f"{source_uuid}.mp4")}
    monkeypatch.setattr(_upload, "_require_workspace_manage", lambda *a, **k: workspace)
    monkeypatch.setattr(_upload, "_load_workspace_source", lambda *a, **k: source)
    monkeypatch.setattr(_upload.db, "delete_aia_source", lambda uuid: None)

    _upload.delete_source(
        workspace_uuid="w1",
        source_uuid=source_uuid,
        current_user={"user_id": 42},
        locale="de",
    )


def test_quelle_loeschen_nimmt_transkript_und_untertitel_mit(lokal, monkeypatch):
    ordner = _quelle_anlegen(lokal, 42, "w1", EINS)

    _route_loeschen(monkeypatch, ordner, EINS)

    assert list(ordner.iterdir()) == []


def test_quelle_loeschen_laesst_die_anderen_quellen_in_ruhe(lokal, monkeypatch):
    ordner = _quelle_anlegen(lokal, 42, "w1", EINS)
    _quelle_anlegen(lokal, 42, "w1", ZWEI)

    _route_loeschen(monkeypatch, ordner, EINS)

    assert sorted(p.name for p in ordner.iterdir()) == [
        f"{ZWEI}.mp4", f"{ZWEI}_transcript.de.vtt",
        f"{ZWEI}_transcript.en.vtt", f"{ZWEI}_transcript.txt",
    ]


def test_workspace_loeschen_raeumt_den_ganzen_workspace_ordner(lokal):
    _quelle_anlegen(lokal, 42, "w1", EINS)
    _quelle_anlegen(lokal, 42, "w1", ZWEI)

    _helpers._delete_workspace_files({"id": 7, "uuid": "w1", "user_id": 42})

    assert not (lokal / "users/42/aia/workspaces/w1").exists()


def test_workspace_loeschen_laesst_fremde_workspaces_stehen(lokal):
    _quelle_anlegen(lokal, 42, "w1", EINS)
    _quelle_anlegen(lokal, 42, "w2", ZWEI)

    _helpers._delete_workspace_files({"id": 7, "uuid": "w1", "user_id": 42})

    assert not (lokal / "users/42/aia/workspaces/w1").exists()
    assert (lokal / f"users/42/aia/workspaces/w2/sources/{ZWEI}.mp4").exists()


def test_speicher_meldet_wie_viele_dateien_weg_sind(lokal):
    """The return value ends up in the log, traceability hangs off it."""
    ordner = _quelle_anlegen(lokal, 42, "w1", EINS)

    assert storage.delete_aia_source_files(str(ordner / f"{EINS}.mp4")) == 4
    assert storage.delete_aia_workspace_folder(42, "w1") == 0
