"""Auch die Werkzeuge suchen ihre Belege nur auf gesehenen Seiten.

Der Chat wurde umgestellt (siehe test_seen_pages_filter): die Einschraenkung auf die
Seiten, die das Modell wirklich gelesen hat, steht in der ABFRAGE statt als Filter
dahinter. Die Werkzeuge im Studio und im Sprachtrainer belegen ueber denselben Dienst,
``attribute_claims``, und ihre Aufrufer reichen ``seen_pages_by_source`` auch schon
herein. Nur die vorgegebene ``search_fn`` gab es nicht weiter, also rankte die Datenbank
je Aussage weiter den ganzen Workspace und ``chips_for_claim`` zerriss die Liste danach.

Dieser Test haelt fest, dass die Einschraenkung wirklich bis zur Abfrage durchreicht.
Die Pruefung in ``chips_for_claim`` bleibt daneben stehen: sie deckt auch Aufrufer ab,
die eine eigene ``search_fn`` mitbringen.
"""
import pytest

# Reihenfolge ist Absicht. aia_attribution holt sich oben die Chip-Auswahl aus
# ai_assistant.routes, und dieses Paket zieht ueber die Werkzeuge wieder
# aia_attribution herein. Wer das Dienst-Modul zuerst anfasst, trifft es halbfertig.
# Erst das Paket vollstaendig laden, dann den Dienst.
import src.features.ai_assistant.routes  # noqa: F401
from src import database as db
from src.services import aia_attribution


@pytest.fixture
def gesuchte_kwargs(monkeypatch):
    """Ruft attribute_claims mit der VORGEGEBENEN search_fn und faengt die DB-Aufrufe."""
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
    # Ein Werkzeug ohne Kontextprotokoll (z.B. eine eigene search_fn oder ein Aufruf
    # ohne die Angabe) darf nicht ploetzlich gar nichts mehr finden.
    for kw in gesuchte_kwargs():
        assert kw.get("seen_pages") is None
