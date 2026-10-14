"""The worker turns an uploaded docx or pptx into a PDF and renames the source."""
from contextlib import contextmanager

from src.features.ai_assistant.tasks import ingestion


def _patch(monkeypatch, others):
    calls = {"put": [], "deleted": [], "updated": []}

    @contextmanager
    def fake_open(path, suffix=""):
        yield "/tmp/in" + suffix

    monkeypatch.setattr(ingestion, "open_input_file", fake_open)
    monkeypatch.setattr(
        "src.features.ai_assistant.routes._media_files._convert_office_to_pdf_path",
        lambda local, ext, tmpdir, locale: "/tmp/out.pdf",
    )
    monkeypatch.setattr(ingestion, "put_file", lambda key, path: calls["put"].append((key, path)))
    monkeypatch.setattr(ingestion, "delete_file", lambda key: calls["deleted"].append(key))
    monkeypatch.setattr(ingestion.db, "get_aia_source", lambda u: {"workspace_id": 7})
    monkeypatch.setattr(
        ingestion.db, "get_aia_sources_by_workspace",
        lambda ws: [{"uuid": "x", "filename": n} for n in others] + [{"uuid": "me", "filename": "skript.docx"}],
    )
    monkeypatch.setattr(ingestion.db, "update_aia_source_file", lambda *a: calls["updated"].append(a))
    return calls


def test_docx_wird_zu_pdf_und_original_geloescht(monkeypatch):
    calls = _patch(monkeypatch, [])
    path, ftype, name = ingestion._convert_office_source("me", "u/ws/me.docx", "docx", "skript.docx", "de")
    assert (path, ftype, name) == ("u/ws/me.pdf", "pdf", "skript.pdf")
    assert calls["put"] == [("u/ws/me.pdf", "/tmp/out.pdf")]
    assert calls["deleted"] == ["u/ws/me.docx"]
    assert calls["updated"] == [("me", "skript.pdf", "u/ws/me.pdf", "pdf")]


def test_namenskollision_bekommt_nummer(monkeypatch):
    _patch(monkeypatch, ["Skript.pdf"])
    _, _, name = ingestion._convert_office_source("me", "u/ws/me.docx", "docx", "skript.docx", "de")
    assert name == "skript (2).pdf"
