# backend/tests/conftest.py
import sys
from pathlib import Path

# Make 'src' package importable when running pytest from repo root or backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402  (after the sys.path shim above)


@pytest.fixture
def lokal(monkeypatch, tmp_path):
    """Speicher ohne S3: STORAGE_ROOT zeigt in ein Testverzeichnis.

    Liefert die Wurzel, unter der die Schluessel als echte Dateien landen.
    """
    from src import storage
    wurzel = tmp_path / "storage"
    wurzel.mkdir()
    monkeypatch.setattr(storage, "USE_S3", False)
    monkeypatch.setattr(storage, "STORAGE_ROOT", wurzel)
    return wurzel
