"""Reading an uploaded source does not stall the backend.

Load test 26.09.: 20 people started summary, podcast and presentation with PDFs; every file
was read on the thread that also serves pages, and everyone else's pages froze.
"""

import asyncio
import time

import pytest

from src.services import sources


class _Upload:
    filename = "a.pdf"


@pytest.mark.asyncio
async def test_andere_anfragen_laufen_waehrend_eine_datei_gelesen_wird(monkeypatch, tmp_path):
    async def strom(datei, ziel, grenze, locale):
        open(ziel, "wb").write(b"%PDF-1.4")
        return 8, b"%PDF-1.4"

    monkeypatch.setattr(sources, "stream_upload_to_path", strom)
    monkeypatch.setattr(sources, "validate_or_raise", lambda *a: None)
    monkeypatch.setattr(sources, "pages_or_raise", lambda *a: time.sleep(0.3))
    monkeypatch.setattr(sources, "read_file", lambda pfad, name: time.sleep(0.3) or "gelesen")

    takte = []

    async def herzschlag():
        for _ in range(10):
            start = time.monotonic()
            await asyncio.sleep(0.05)
            takte.append(time.monotonic() - start)

    schlag = asyncio.create_task(herzschlag())
    await asyncio.sleep(0.01)  # the heartbeat is already ticking when the reading starts
    ergebnis = await sources._read_upload(_Upload(), str(tmp_path), "de", "summary")
    await schlag

    assert ergebnis == "gelesen"
    # Blocked, a single beat would wait the full 0.3 s of reading.
    assert max(takte) < 0.2
