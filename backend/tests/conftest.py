# backend/tests/conftest.py
import sys
from pathlib import Path

# Make 'src' package importable when running pytest from repo root or backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest  # noqa: E402  (after the sys.path shim above)


@pytest.fixture(autouse=True)
def _global_consent_given(monkeypatch):
    """New accounts confirm this once; every other test assumes it already happened.
    A test for the gate itself overrides it back, see test_global_consent.py."""
    import src.dependencies_rbac as rbac
    monkeypatch.setattr(rbac, "has_global_consent", lambda user_id: True)


@pytest.fixture(autouse=True)
def _keine_alten_erreichbarkeiten(monkeypatch):
    """Each test probes its own fake providers, a result from an earlier test must not answer for them."""
    from src.services import feature_provider_choices
    monkeypatch.setattr(feature_provider_choices, "_probed", {})
    monkeypatch.setattr(feature_provider_choices, "_probing", {})


@pytest.fixture
def lokal(monkeypatch, tmp_path):
    """Storage without S3, the keys end up as files in the test directory."""
    from src import storage
    wurzel = tmp_path / "storage"
    wurzel.mkdir()
    monkeypatch.setattr(storage, "USE_S3", False)
    monkeypatch.setattr(storage, "STORAGE_ROOT", wurzel)
    return wurzel
