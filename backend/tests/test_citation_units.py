from src.features.ai_assistant.routes._helpers import SourceUnitLoader


def test_loader_caches_per_source(monkeypatch):
    calls = {"n": 0}

    def fake_chunks(sid):
        calls["n"] += 1
        return [{"page_number": 5, "content": "hello world", "start_time": None}]

    monkeypatch.setattr(
        "src.features.ai_assistant.repository.chunks.get_aia_chunks_by_source", fake_chunks
    )
    loader = SourceUnitLoader()
    src = {"id": 1, "filename": "x.pdf", "file_path": "x.pdf"}
    u1 = loader.units(src, is_media=False)
    u2 = loader.units(src, is_media=False)
    assert calls["n"] == 1            # cached
    assert u1[0].page == 5 and u1[0].raw_text == "hello world"
