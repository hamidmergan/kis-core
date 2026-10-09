"""Direct uploads: the server signs parts, checks the joined file and only then creates a source."""
import json

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.sources import _direct_upload as du

WS = {"id": 7, "uuid": "w1", "user_id": 42}
PART = du._PART_SIZE
WEBM_HEAD = bytes.fromhex("1a45dfa3") + b"\x9f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\x82\x84webm" + b"\x00" * 64


class _FakeRedis:
    def __init__(self, store):
        self._store = store

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)


class _Request:
    def __init__(self, origin="https://kis.example", host="kis.example"):
        self.headers = {"origin": origin, "x-forwarded-host": host}


@pytest.fixture
def bucket(monkeypatch):
    """Bucket, Redis and database stubbed, every call recorded."""
    state = {"redis": {}, "parts": [], "existing": [], "created": [], "deleted": [], "aborted": [],
             "completed": [], "cors": [], "recorded": [], "enqueued": [], "head": WEBM_HEAD}
    monkeypatch.setattr(du, "USE_S3", True)
    monkeypatch.setattr(du, "_redis", lambda: _FakeRedis(state["redis"]))
    monkeypatch.setattr(du, "_require_workspace_manage", lambda *a, **k: WS)
    monkeypatch.setattr(du, "check_upload_limit", lambda *a, **k: None)
    monkeypatch.setattr(du, "record_upload", lambda uid: state["recorded"].append(uid))
    monkeypatch.setattr(du, "_require_source_capacity", lambda *a, **k: None)
    monkeypatch.setattr(du.db, "get_aia_sources_by_workspace", lambda wid: state["existing"])
    monkeypatch.setattr(du.db, "create_aia_source", lambda **kw: state["created"].append(kw))
    monkeypatch.setattr(du, "_enqueue_index_source", lambda *a: state["enqueued"].append(a[0]))
    monkeypatch.setattr(du, "ensure_upload_cors", lambda origin: state["cors"].append(origin))
    monkeypatch.setattr(du, "multipart_start", lambda key, ct: "up-1")
    monkeypatch.setattr(du, "multipart_part_url", lambda key, uid, n, sec: f"https://bucket/{key}?part={n}")
    monkeypatch.setattr(du, "multipart_parts", lambda key, uid: state["parts"])
    monkeypatch.setattr(du, "multipart_complete", lambda key, uid, parts: state["completed"].append(parts))
    monkeypatch.setattr(du, "multipart_abort", lambda key, uid: state["aborted"].append(key))
    monkeypatch.setattr(du, "get_range", lambda key, start, length: state["head"])
    monkeypatch.setattr(du, "delete_file", lambda key: state["deleted"].append(key))
    monkeypatch.setattr("src.services.tool_limits.max_upload_bytes", lambda: 500 * 1024 * 1024)
    return state


def _start(name="vorlesung.webm", size=PART * 2 + 5, request=None):
    return du.start_direct_upload(
        workspace_uuid="w1", body=du.DirectStart(filename=name, size=size),
        request=request or _Request(), current_user={"user_id": 42}, locale="de",
    )


def test_dokumente_bleiben_beim_klassischen_weg(bucket):
    assert _start(name="skript.pdf") == {"direct": False}
    assert bucket["redis"] == {}


def test_ohne_bucket_klassischer_weg(bucket, monkeypatch):
    monkeypatch.setattr(du, "USE_S3", False)
    assert _start() == {"direct": False}


def test_start_legt_sitzung_beim_besitzer_an(bucket):
    antwort = _start()

    assert antwort["direct"] is True
    assert antwort["part_count"] == 3
    session = json.loads(bucket["redis"][du._SESSION_PREFIX + antwort["token"]])
    assert session["key"].startswith("users/42/aia/workspaces/w1/sources/")
    assert session["key"].endswith(".webm")
    assert bucket["cors"] == ["https://kis.example"]


def test_fremde_herkunft_setzt_keine_cors_regel(bucket):
    _start(request=_Request(origin="https://boese.example", host="kis.example"))
    assert bucket["cors"] == [""]


@pytest.mark.parametrize("size,status", [(0, 400), (501 * 1024 * 1024, 413)])
def test_groesse_wird_vorab_geprueft(bucket, size, status):
    with pytest.raises(HTTPException) as exc:
        _start(size=size)
    assert exc.value.status_code == status


def test_gleicher_name_wird_abgelehnt(bucket):
    bucket["existing"] = [{"filename": "Vorlesung.WEBM"}]
    with pytest.raises(HTTPException) as exc:
        _start()
    assert exc.value.status_code == 409


def test_fremde_sitzung_ist_unsichtbar(bucket):
    token = _start()["token"]
    with pytest.raises(HTTPException) as exc:
        du.direct_upload_urls(workspace_uuid="w1", token=token, body=du.PartNumbers(parts=[1]),
                              current_user={"user_id": 99}, locale="de")
    assert exc.value.status_code == 404


def test_urls_nur_fuer_vorhandene_teile(bucket):
    token = _start()["token"]
    urls = du.direct_upload_urls(workspace_uuid="w1", token=token, body=du.PartNumbers(parts=[1, 3]),
                                 current_user={"user_id": 42}, locale="de")["urls"]
    assert set(urls) == {"1", "3"}
    with pytest.raises(HTTPException):
        du.direct_upload_urls(workspace_uuid="w1", token=token, body=du.PartNumbers(parts=[4]),
                              current_user={"user_id": 42}, locale="de")


def test_status_zaehlt_nur_vollstaendige_teile(bucket):
    token = _start()["token"]
    bucket["parts"] = [
        {"PartNumber": 1, "ETag": "a", "Size": PART},
        {"PartNumber": 2, "ETag": "b", "Size": PART - 10},
    ]
    status = du.direct_upload_status(workspace_uuid="w1", token=token, current_user={"user_id": 42}, locale="de")
    assert status["uploaded"] == [1]


def _alle_teile():
    return [
        {"PartNumber": 2, "ETag": "b", "Size": PART},
        {"PartNumber": 1, "ETag": "a", "Size": PART},
        {"PartNumber": 3, "ETag": "c", "Size": 5},
    ]


def _complete(token):
    return du.complete_direct_upload(workspace_uuid="w1", token=token, current_user={"user_id": 42}, locale="de")


def test_abschluss_legt_quelle_an(bucket):
    token = _start()["token"]
    bucket["parts"] = _alle_teile()

    antwort = _complete(token)

    assert [p["PartNumber"] for p in bucket["completed"][0]] == [1, 2, 3]
    assert bucket["created"][0]["file_type"] == "webm"
    assert bucket["created"][0]["uuid"] == antwort["uuid"]
    assert bucket["enqueued"] == [antwort["uuid"]]
    assert bucket["recorded"] == [42]
    assert bucket["redis"] == {}


def test_unvollstaendig_wird_nicht_zusammengefuegt(bucket):
    token = _start()["token"]
    bucket["parts"] = _alle_teile()[:2]
    with pytest.raises(HTTPException) as exc:
        _complete(token)
    assert exc.value.status_code == 409
    assert bucket["completed"] == []
    # The session stays, the missing part can still be sent.
    assert bucket["redis"]


def test_falscher_inhalt_wird_geloescht(bucket):
    token = _start()["token"]
    bucket["parts"] = _alle_teile()
    bucket["head"] = b"%PDF-1.4" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc:
        _complete(token)
    assert exc.value.status_code == 400
    assert len(bucket["deleted"]) == 1
    assert bucket["created"] == []
    assert bucket["recorded"] == []


def test_abbruch_verwirft_teile(bucket):
    token = _start()["token"]
    du.abort_direct_upload(workspace_uuid="w1", token=token, current_user={"user_id": 42}, locale="de")
    assert len(bucket["aborted"]) == 1
    assert bucket["redis"] == {}


def test_mit_weiterleitung_keine_cors_regel(bucket, monkeypatch):
    monkeypatch.setattr(du, "S3_UPLOAD_PROXY", "/bucket-upload")
    _start()
    assert bucket["cors"] == []


def test_signierte_adresse_geht_ueber_die_weiterleitung(monkeypatch):
    from src import storage

    class _Signer:
        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://s3.example/kis/{Params['Key']}?partNumber={Params['PartNumber']}&X-Amz-Signature=abc"

    monkeypatch.setattr(storage, "_s3_public", lambda: _Signer())
    monkeypatch.setattr(storage, "_S3_PUBLIC_ENDPOINT", "https://s3.example")
    monkeypatch.setattr(storage, "S3_UPLOAD_PROXY", "/bucket-upload")
    assert storage.multipart_part_url("users/1/a.webm", "u", 2, 60) == (
        "/bucket-upload/kis/users/1/a.webm?partNumber=2&X-Amz-Signature=abc"
    )
    monkeypatch.setattr(storage, "S3_UPLOAD_PROXY", "")
    assert storage.multipart_part_url("users/1/a.webm", "u", 2, 60).startswith("https://s3.example/kis/")
