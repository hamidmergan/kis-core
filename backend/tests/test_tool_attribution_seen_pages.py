"""The tools also look for their citations only on seen pages."""
import pytest

# Load the package fully first, then the service, otherwise you catch it half built.
import src.features.ai_assistant.routes  # noqa: F401
from src import database as db
from src.services import aia_attribution


@pytest.fixture
def gesuchte_kwargs(monkeypatch):
    """Calls attribute_claims with the GIVEN search_fn and captures the database calls."""
    calls: list[dict] = []

    def _fake_search(workspace_id, text, vec, **kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(db, "hybrid_search_chunks", _fake_search)

    def _lauf(**kwargs):
        calls.clear()
        aia_attribution.attribute_claims(
            ["Die Anmeldung laeuft ueber das Portal."],
            {7: "Skript.pdf"},
            workspace_id=1,
            source_ids=[7],
            embed_fn=lambda texte: [[0.1] * 8 for _ in texte],
            **kwargs,
        )
        return calls

    return _lauf


def test_gesehene_seiten_erreichen_die_abfrage(gesuchte_kwargs):
    calls = gesuchte_kwargs(seen_pages_by_source={7: {3, 4}})
    assert calls, "die vorgegebene search_fn muss die Datenbank fragen"
    for kw in calls:
        assert kw.get("seen_pages") == {7: {3, 4}}


def test_ohne_angabe_bleibt_die_suche_breit(gesuchte_kwargs):
    # A tool without a page value must not suddenly find nothing.
    for kw in gesuchte_kwargs():
        assert kw.get("seen_pages") is None
