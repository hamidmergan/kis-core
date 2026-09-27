"""Ein Upload wartet kurz auf einen freien Platz, statt sofort abgewiesen zu werden."""

import pytest

from src.features.ai_assistant.routes.sources import _upload


@pytest.mark.asyncio
async def test_ein_frei_werdender_platz_wird_genommen(monkeypatch):
    """Lasttest 26.09.: Absagen kamen, obwohl nach Sekunden wieder Platz war."""
    antworten = iter([None, None, "ticket"])
    monkeypatch.setattr(_upload, "_claim_upload_slot", lambda limit: next(antworten))

    async def kein_schlaf(sek):
        return None

    monkeypatch.setattr(_upload.asyncio, "sleep", kein_schlaf)
    assert await _upload._wait_for_upload_slot(3, wait_seconds=30) == "ticket"


@pytest.mark.asyncio
async def test_nach_der_wartezeit_gibt_es_keinen_platz(monkeypatch):
    uhr = {"t": 0.0}
    monkeypatch.setattr(_upload, "_claim_upload_slot", lambda limit: None)
    monkeypatch.setattr(_upload.time, "monotonic", lambda: uhr["t"])

    async def schlaf(sek):
        uhr["t"] += sek

    monkeypatch.setattr(_upload.asyncio, "sleep", schlaf)
    assert await _upload._wait_for_upload_slot(3, wait_seconds=30) is None
    assert uhr["t"] >= 30
