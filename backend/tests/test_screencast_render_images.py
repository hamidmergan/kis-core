"""PPTX nach PNG: LibreOffice-Aufruf und Bildanzahl.

Zwei Dinge sind hier schon schiefgegangen.

Erstens teilen sich alle LibreOffice-Aufrufe ohne eigenes Profil dieselbe
Konfiguration. Ein zweiter Aufruf während eines laufenden reicht den Auftrag
nur weiter und endet mit Rückgabewert 0, ohne PDF. Gemessen: drei gleichzeitige
Konvertierungen, eine ohne Ergebnis, keine Fehlermeldung im Log.

Zweitens exportiert LibreOffice ausgeblendete Folien nicht. Die Bildanzahl muss
deshalb zur Textanzahl aus ``extract_text_per_slide`` passen, sonst bekommt
jedes Bild nach der ersten versteckten Folie das falsche Skript.
"""

import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tests._pptx_fixtures import hidden_slide_pptx

from src.services.screencast.pptx import (
    build_soffice_cmd,
    extract_text_per_slide,
    pptx_to_images,
    soffice_profile_dir,
)


def test_soffice_cmd_uses_isolated_profile():
    cmd = build_soffice_cmd(Path("/tmp/x.pptx"), Path("/tmp/out"))
    profile_args = [a for a in cmd if a.startswith("-env:UserInstallation=")]
    assert profile_args, "ohne eigenes Profil verwerfen parallele Aufrufe still ihr Ergebnis"
    assert str(soffice_profile_dir()) in profile_args[0]


def test_soffice_cmd_excludes_hidden_slides():
    cmd = build_soffice_cmd(Path("/tmp/x.pptx"), Path("/tmp/out"))
    convert_arg = cmd[cmd.index("--convert-to") + 1]
    assert convert_arg.startswith("pdf:")
    assert '"ExportHiddenSlides"' in convert_arg
    assert '"value":"false"' in convert_arg


def test_profile_dir_differs_between_concurrent_threads():
    """Zwei gleichzeitig laufende Konvertierungen dürfen sich kein Profil teilen."""
    barrier = threading.Barrier(2)

    def _profile(_: int) -> Path:
        barrier.wait(timeout=5)  # beide Threads laufen sicher gleichzeitig
        return soffice_profile_dir()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(_profile, range(2)))
    assert a != b


@pytest.mark.e2e
def test_image_count_matches_text_count_with_hidden_slide(tmp_path):
    """Braucht LibreOffice, läuft daher nur im E2E-Lauf."""
    pptx = tmp_path / "hidden.pptx"
    pptx.write_bytes(hidden_slide_pptx())
    out = tmp_path / "images"
    out.mkdir()

    images = pptx_to_images(pptx, out, dpi=50)
    texts = extract_text_per_slide(pptx.read_bytes())

    assert len(images) == len(texts) == 2
    assert not list(out.glob("*.pdf")), "Zwischen-PDF muss aufgeräumt sein"
    assert not list(tmp_path.glob("_render_*.pptx")), "AutoFit-Kopie muss aufgeräumt sein"
    shutil.rmtree(out, ignore_errors=True)


@pytest.mark.e2e
def test_parallel_conversions_all_produce_images(tmp_path):
    """Drei gleichzeitige Konvertierungen, alle müssen Bilder liefern."""
    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(hidden_slide_pptx())

    def _convert(i: int) -> int:
        out = tmp_path / f"out{i}"
        out.mkdir()
        return len(pptx_to_images(pptx, out, dpi=50))

    with ThreadPoolExecutor(max_workers=3) as pool:
        counts = list(pool.map(_convert, range(3)))

    assert counts == [2, 2, 2]
