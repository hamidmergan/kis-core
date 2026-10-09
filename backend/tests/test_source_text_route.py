"""A pasted text becomes a text source, its length is capped and editing reads it in again."""
import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.sources import _text
from src.limits import AIA_TEXT_SOURCE_MAX_CHARS

WS = {"id": 7, "uuid": "w1", "user_id": 42}


@pytest.fixture
def route(monkeypatch, tmp_path):
    """Everything around the routes stubbed, the calls recorded."""
    calls = {"existing": [], "bytes": {}}
    monkeypatch.setattr(_text, "_require_workspace_manage", lambda *a, **k: WS)
    monkeypatch.setattr(_text, "check_upload_limit", lambda *a, **k: None)
    monkeypatch.setattr(_text, "record_upload", lambda uid: calls.setdefault("recorded", []).append(uid))
    monkeypatch.setattr(_text.db, "get_aia_sources_by_workspace", lambda wid: calls["existing"])
    monkeypatch.setattr(_text, "_require_source_capacity", lambda *a, **k: None)

    async def _render(title, text, tmpdir, locale):
        calls["rendered"] = {"title": title, "text": text}
        pdf = tmp_path / "text.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return str(pdf)

    monkeypatch.setattr(_text, "_render_pdf", _render)
    monkeypatch.setattr(
        _text, "_save_source_file_path",
        lambda owner, ws, source_uuid, ext, path: f"users/{owner}/aia/workspaces/{ws}/sources/{source_uuid}{ext}",
    )
    monkeypatch.setattr(_text, "put_bytes", lambda key, data: calls["bytes"].__setitem__(key, data))
    monkeypatch.setattr(_text, "put_file", lambda key, path: calls.setdefault("replaced", []).append(key))
    monkeypatch.setattr(_text, "get_file", lambda key: calls["bytes"][key])

    def _create(**kwargs):
        calls["created"] = kwargs
        return 1

    monkeypatch.setattr(_text.db, "create_aia_source", _create)
    monkeypatch.setattr(_text.db, "delete_aia_chunks_by_source", lambda sid: calls.setdefault("chunks_cleared", []).append(sid))
    monkeypatch.setattr(_text.db, "reset_aia_source_for_retry", lambda u: calls.setdefault("reset", []).append(u))
    monkeypatch.setattr(
        _text, "_enqueue_index_source",
        lambda source_uuid, uid, locale: calls.setdefault("enqueued", []).append(source_uuid),
    )
    return calls


async def _neu(title="Merkblatt", text="Erster Absatz.\n\nZweiter Absatz."):
    return await _text.add_text_source(
        workspace_uuid="w1", body=_text.NewTextBody(title=title, text=text),
        current_user={"user_id": 42}, locale="de",
    )


@pytest.mark.asyncio
async def test_text_wird_eine_quelle_mit_eigenem_typ(route):
    antwort = await _neu()

    assert antwort["status"] == "pending"
    assert antwort["filename"] == "Merkblatt.pdf"
    assert antwort["file_type"] == "text"
    assert route["created"]["file_type"] == "text"
    file_path = route["created"]["file_path"]
    assert route["bytes"][f"{file_path[:-4]}_text.txt"] == "Erster Absatz.\n\nZweiter Absatz.".encode()
    assert route["enqueued"] == [antwort["uuid"]]
    assert route["recorded"] == [42]


@pytest.mark.asyncio
async def test_gleicher_titel_bekommt_eine_nummer(route):
    route["existing"] = [{"filename": "Merkblatt.pdf"}]
    antwort = await _neu()
    assert antwort["filename"] == "Merkblatt (2).pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize("title,text,key", [
    ("Merkblatt", "   \n ", "leer"),
    ("  ", "Inhalt", "Titel"),
    ("Merkblatt", "x" * (AIA_TEXT_SOURCE_MAX_CHARS + 1), "höchstens"),
])
async def test_abgelehnt_ohne_zeile(route, title, text, key):
    with pytest.raises(HTTPException) as e:
        await _neu(title=title, text=text)
    assert e.value.status_code == 400
    assert key in e.value.detail
    assert "created" not in route
    assert "recorded" not in route


@pytest.mark.asyncio
async def test_genau_an_der_grenze_geht_durch(route):
    antwort = await _neu(text="x" * AIA_TEXT_SOURCE_MAX_CHARS)
    assert antwort["status"] == "pending"


def _quelle(monkeypatch, **felder):
    quelle = {"id": 3, "uuid": "s1", "workspace_id": 7, "filename": "Merkblatt.pdf",
              "file_path": "users/42/aia/workspaces/w1/sources/s1.pdf", "file_type": "text",
              "status": "ready", "progress": None, **felder}
    monkeypatch.setattr(_text, "_load_workspace_source", lambda *a, **k: quelle)
    return quelle


@pytest.mark.asyncio
async def test_bearbeiten_ersetzt_text_und_liest_neu_ein(route, monkeypatch):
    quelle = _quelle(monkeypatch)
    antwort = await _text.edit_text_source(
        workspace_uuid="w1", source_uuid="s1", body=_text.EditTextBody(text="Neuer Inhalt"),
        current_user={"user_id": 42}, locale="de",
    )
    assert antwort == {"uuid": "s1", "status": "pending"}
    assert route["rendered"] == {"title": "Merkblatt", "text": "Neuer Inhalt"}
    assert route["replaced"] == [quelle["file_path"]]
    assert route["bytes"]["users/42/aia/workspaces/w1/sources/s1_text.txt"] == b"Neuer Inhalt"
    assert route["chunks_cleared"] == [3]
    assert route["reset"] == ["s1"]
    assert route["enqueued"] == ["s1"]

    gelesen = _text.get_text_source(workspace_uuid="w1", source_uuid="s1",
                                    current_user={"user_id": 42}, locale="de")
    assert gelesen == {"text": "Neuer Inhalt"}


@pytest.mark.asyncio
async def test_bearbeiten_waehrend_einlesen_abgelehnt(route, monkeypatch):
    _quelle(monkeypatch, status="indexing")
    with pytest.raises(HTTPException) as e:
        await _text.edit_text_source(
            workspace_uuid="w1", source_uuid="s1", body=_text.EditTextBody(text="Neu"),
            current_user={"user_id": 42}, locale="de",
        )
    assert e.value.status_code == 409
    assert "enqueued" not in route


@pytest.mark.asyncio
async def test_andere_quelle_ist_nicht_bearbeitbar(route, monkeypatch):
    _quelle(monkeypatch, file_type="pdf")
    with pytest.raises(HTTPException) as e:
        await _text.edit_text_source(
            workspace_uuid="w1", source_uuid="s1", body=_text.EditTextBody(text="Neu"),
            current_user={"user_id": 42}, locale="de",
        )
    assert e.value.status_code == 400


def test_html_behaelt_absaetze_und_maskiert():
    html = _text._document_html("A <b>", "Zeile eins\nZeile zwei\n\n<script>")
    assert "<h1>A &lt;b&gt;</h1>" in html
    assert "<p>Zeile eins<br>Zeile zwei</p>" in html
    assert "<p>&lt;script&gt;</p>" in html


class _IngestDb:
    """Just the db calls run_index_source makes for one text source."""

    def __init__(self, source, calls):
        self.source, self.calls = source, calls

    def get_aia_source(self, uuid):
        return self.source

    def update_aia_source_status(self, uuid, status, **kw):
        self.calls["status"].append(status)

    def update_aia_source_summary(self, uuid, summary):
        self.calls["summary"] = summary

    def create_aia_chunk(self, **kw):
        self.calls["chunks"].append(kw)
        return len(self.calls["chunks"])

    def get_aia_sources_by_workspace(self, wid):
        return [dict(self.source, status="ready")]

    def get_aia_workspace_by_id(self, wid):
        return {"uuid": "w"}

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_einlesen_liest_das_pdf_und_nimmt_den_text_als_zusammenfassung(lokal, monkeypatch):
    from contextlib import nullcontext

    from src import storage
    from src.features.ai_assistant.tasks import _helpers, ingestion
    from src.services import aia_chunker, aia_embeddings

    file_path = "users/1/aia/workspaces/w/sources/s1.pdf"
    storage.put_bytes(storage.aia_text_key(file_path), "Abgabe am 14. November.".encode())
    source = {"id": 3, "uuid": "s1", "workspace_id": 7, "file_path": file_path,
              "file_type": "text", "filename": "Merkblatt.pdf", "status": "pending"}
    calls = {"status": [], "chunks": []}
    monkeypatch.setattr(ingestion, "db", _IngestDb(source, calls))
    monkeypatch.setattr(ingestion, "open_input_file", lambda *a, **k: nullcontext("/tmp/s1.pdf"))
    gelesen = []
    monkeypatch.setattr(aia_chunker, "extract_chunks", lambda path, ft, **k: gelesen.append(ft) or
                        [{"page_number": 1, "content": "Merkblatt\nAbgabe am 14. November."}])
    monkeypatch.setattr(aia_embeddings, "get_embedding_provider_with_fallback",
                        lambda: type("E", (), {"model_name": "emb", "embed": lambda self, t: [[0.1] for _ in t]})())
    monkeypatch.setattr(aia_embeddings, "fingerprint_from_dim", lambda provider, dim: "fp")
    monkeypatch.setattr(_helpers, "_get_llm_client", lambda: pytest.fail("a text source needs no LLM call"))

    ingestion.run_index_source("s1", "de")

    assert gelesen == ["pdf"]
    assert calls["summary"] == "Abgabe am 14. November."
    assert calls["status"][-1] == "ready"
