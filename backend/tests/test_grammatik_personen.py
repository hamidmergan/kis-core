"""The people in grammar sentences are concrete, never 'das Team' or 'die Person'."""

from src.features.ai_assistant.tasks.language_training._source_grammar import _build_prompt
from src.services.aia_grammar_topic import _PROMPT as DERIVE_PROMPT


def _prompt() -> str:
    gtype = {"id": 1, "label": "Passiv Präsens", "rule": "Aktiv wird Passiv.",
             "example": {"before": "Max schreibt den Bericht.", "after": "Der Bericht wird von Max geschrieben."},
             "examples": [{"before": "Max schreibt den Bericht.", "after": "Der Bericht wird von Max geschrieben."}]}
    return _build_prompt(gtype, "Passiv Präsens", gtype["examples"], ["transform", "choice"])


def test_uebung_verlangt_konkrete_personen():
    prompt = _prompt()
    assert "Never a vague subject such as 'das Team', 'die Person'" in prompt
    assert "Do NOT use personal names" not in prompt


def test_eigene_beispiele_der_uebung_nennen_kein_team():
    """The model copies the subject of the worked examples, so they show what is wanted."""
    assert "vom Team" not in _prompt()
    assert "Das Team" not in _prompt()


def test_neues_thema_bekommt_ein_konkretes_beispiel():
    assert "'das Team'" in DERIVE_PROMPT and "Never a vague subject" in DERIVE_PROMPT
    assert "Use no personal names" not in DERIVE_PROMPT
