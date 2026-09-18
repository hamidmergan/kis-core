"""The route takes several files, files them numbered and starts the staged task."""

import io

import pytest

from src.routes import summary as route


class _Upload:
    def __init__(self, data: bytes, name: str):
        self.filename = name
        self._buf = io.BytesIO(data)
        self.size = len(data)

    async def read(self, n=-1):
        return self._buf.read(n)


class _Request:
    headers = {}


@pytest.fixture
def stub(monkeypatch):
    gestartet = {}
    monkeypatch.setattr(route, "enforce_open_jobs", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_tool_burst", lambda *a, **k: None)
    monkeypatch.setattr(route, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(route, "save_job_file_from_path", lambda uid, job, name, pfad: f"s3/{name}")
    monkeypatch.setattr(route, "validate_or_raise", lambda *a, **k: None)

    import src.tasks.summary_tasks as st
    monkeypatch.setattr(st, "run_summary",
                        type("T", (), {"delay": staticmethod(lambda *a: gestartet.update(args=a))})())
    return gestartet


async def test_templates_nennen_vorlagen_und_grenzen():
    antwort = await route.list_templates(_user={})
    assert [v["slug"] for v in antwort["templates"]][0] == "fliesstext"
    assert antwort["maxSources"] == 10 and ".pdf" in antwort["extensions"]


async def test_zwei_dateien_werden_nummeriert_abgelegt(stub):
    antwort = await route.summarize(
        request=_Request(), files=[_Upload(b"eins " * 100, "a.txt"), _Upload(b"zwei " * 100, "b.md")],
        template="zeitstrahl", provider_id=None, current_user={"user_id": 1}, locale="de")
    assert antwort["status"] == "pending"
    job, quellen, slug, pid = stub["args"]
    assert [q["filename"] for q in quellen] == ["a.txt", "b.md"]
    assert [q["input_path"] for q in quellen] == ["s3/input_0.txt", "s3/input_1.md"]
    assert slug == "zeitstrahl"


async def test_ohne_vorlage_gilt_der_fliesstext(stub):
    await route.summarize(request=_Request(), files=[_Upload(b"x " * 100, "a.txt")],
                          template=None, provider_id=None, current_user={"user_id": 1}, locale="de")
    assert stub["args"][2] == "fliesstext"


async def test_eine_fremde_vorlage_wird_abgelehnt(stub):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as fehler:
        await route.summarize(request=_Request(), files=[_Upload(b"x " * 100, "a.txt")],
                              template="nix", provider_id=None, current_user={"user_id": 1}, locale="de")
    assert fehler.value.status_code == 400


async def test_zu_viele_dateien_werden_abgelehnt(stub):
    from fastapi import HTTPException
    dateien = [_Upload(b"x " * 10, f"{n}.txt") for n in range(11)]
    with pytest.raises(HTTPException) as fehler:
        await route.summarize(request=_Request(), files=dateien, template=None, provider_id=None,
                              current_user={"user_id": 1}, locale="de")
    assert fehler.value.status_code == 400


async def test_keine_datei_wird_abgelehnt(stub):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await route.summarize(request=_Request(), files=[], template=None, provider_id=None,
                              current_user={"user_id": 1}, locale="de")


async def test_ungueltige_zweite_datei_kostet_kein_kontingent(stub, monkeypatch):
    from fastapi import HTTPException
    aufrufe = []
    monkeypatch.setattr(route, "enforce_quota", lambda *a, **k: aufrufe.append(1))
    with pytest.raises(HTTPException):
        await route.summarize(
            request=_Request(), files=[_Upload(b"eins " * 100, "a.txt"), _Upload(b"zwei " * 100, "b.xyz")],
            template=None, provider_id=None, current_user={"user_id": 1}, locale="de")
    assert aufrufe == []


async def test_fehler_beim_ablegen_erzeugt_keinen_auftrag(stub, monkeypatch):
    aufrufe = {"n": 0}

    def kaputt(uid, job, name, pfad):
        aufrufe["n"] += 1
        if aufrufe["n"] == 2:
            raise RuntimeError("Speicher weg")
        return f"s3/{name}"

    monkeypatch.setattr(route, "save_job_file_from_path", kaputt)
    erzeugt = []
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: erzeugt.append(1))
    with pytest.raises(RuntimeError):
        await route.summarize(
            request=_Request(), files=[_Upload(b"eins " * 100, "a.txt"), _Upload(b"zwei " * 100, "b.md")],
            template=None, provider_id=None, current_user={"user_id": 1}, locale="de")
    assert erzeugt == []
