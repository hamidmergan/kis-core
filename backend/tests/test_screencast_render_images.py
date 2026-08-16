"""PPTX nach PNG: LibreOffice-Aufruf und Bildanzahl.

Zwei Dinge sind hier schon schiefgegangen.

Erstens teilen sich alle LibreOffice-Aufrufe ohne eigenes Profil dieselbe
Konfiguration. Ein zweiter Aufruf während eines laufenden reicht den Auftrag
nur weiter und endet mit Rückgabewert 0, ohne PDF. Gemessen: drei gleichzeitige
Konvertierungen, eine ohne Ergebnis, keine Fehlermeldung im Log.

Zweitens exportiert LibreOffice ausgeblendete Folien nicht. Der Aufruf muss sie
deshalb schon beim Export ausschliessen, sonst bekommt jedes Bild nach der ersten
versteckten Folie das falsche Skript.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.services.screencast.pptx import (
    build_soffice_cmd,
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
