"""A source row carries the link it came from, an upload leaves it empty."""
import pytest
from fastapi import HTTPException

from src.features.ai_assistant.repository import sources as repo
from src.features.ai_assistant.routes.sources import _shared


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return (99,)


class _FakeConn:
    def __init__(self, calls):
        self._cur = _FakeCursor(calls)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, *a, **k):
        return self._cur

    def commit(self):
        self.committed = True


def _verbindung(monkeypatch):
    calls = []
    conn = _FakeConn(calls)

    class _Ctx:
        def __enter__(self):
            return conn

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(repo, "get_connection", lambda: _Ctx())
    return calls, conn


def test_anlegen_schreibt_den_link_mit(monkeypatch):
    calls, conn = _verbindung(monkeypatch)

    neu = repo.create_aia_source(
        workspace_id=7, uuid="abc", filename="Seite.pdf", file_path="u/7/x.pdf",
        file_type="pdf", source_url="https://example.org/a",
    )

    assert neu == 99
    sql, params = calls[0]
    assert "source_url" in sql
    assert params == (7, "abc", "Seite.pdf", "u/7/x.pdf", "pdf", "https://example.org/a")
    assert conn.committed


def test_anlegen_ohne_link_schreibt_null(monkeypatch):
    calls, _ = _verbindung(monkeypatch)

    repo.create_aia_source(workspace_id=7, uuid="abc", filename="a.pdf", file_path="p", file_type="pdf")

    assert calls[0][1][-1] is None


WS = {"id": 7, "uuid": "w1", "user_id": 42}


@pytest.fixture
def schwanz(monkeypatch, tmp_path):
    """Storage, table and queue stubbed, every call recorded."""
    calls = {}
    monkeypatch.setattr(_shared.db, "get_setting", lambda key, default=None: default)
    monkeypatch.setattr(_shared, "_save_source_file_path",
                        lambda uid, ws, su, ext, path: calls.setdefault("saved", (uid, ws, ext)) and f"users/{uid}/{su}{ext}")
    monkeypatch.setattr(_shared.db, "create_aia_source", lambda **kw: calls.setdefault("row", kw) and 1)
    monkeypatch.setattr("src.features.ai_assistant.scheduling.service.scheduler_enabled", lambda: True)
    monkeypatch.setattr("src.features.ai_assistant.scheduling.service.enqueue_task",
                        lambda name, uid, args=None: calls.setdefault("job", (name, uid, args)))
    datei = tmp_path / "x.pdf"
    datei.write_bytes(b"%PDF-1.4")
    return calls, str(datei)


@pytest.mark.asyncio
async def test_schwanz_speichert_legt_an_und_reiht_ein(schwanz, monkeypatch):
    calls, pfad = schwanz
    monkeypatch.setattr(_shared, "_count_pages_path", lambda ext, path: 3)

    antwort = await _shared._register_source_file(
        WS, "w1", pfad, ".pdf", "Seite.pdf", 42, "de", source_url="https://example.org/a",
    )

    assert calls["saved"] == (42, "w1", ".pdf")
    assert calls["row"]["filename"] == "Seite.pdf"
    assert calls["row"]["file_type"] == "pdf"
    assert calls["row"]["source_url"] == "https://example.org/a"
    assert calls["job"][0] == "aia.index_source"
    assert calls["job"][2] == [antwort["uuid"], "de"]
    assert antwort["status"] == "pending"
    assert antwort["source_url"] == "https://example.org/a"


@pytest.mark.asyncio
async def test_schwanz_lehnt_zu_viele_seiten_ab(schwanz, monkeypatch):
    calls, pfad = schwanz
    monkeypatch.setattr(_shared, "_count_pages_path", lambda ext, path: 999)

    with pytest.raises(HTTPException) as exc:
        await _shared._register_source_file(WS, "w1", pfad, ".pdf", "Seite.pdf", 42, "de")

    assert exc.value.status_code == 413
    assert "row" not in calls


def test_quellen_deckel(monkeypatch):
    monkeypatch.setattr(_shared.db, "get_setting", lambda key, default=None: "2")
    _shared._require_source_capacity([{"id": 1}], "de")
    with pytest.raises(HTTPException) as exc:
        _shared._require_source_capacity([{"id": 1}, {"id": 2}], "de")
    assert exc.value.status_code == 409
