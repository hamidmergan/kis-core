"""For a single page exactly one anchor chip stays at the end."""
from src.features.ai_assistant.routes._chips import _append_scope_anchor


def test_appends_single_anchor_at_bottom():
    body = "- 3.5.6 2D-Filterung\n- 4 Video"
    out = _append_scope_anchor(body, 1, 5)
    assert out.rstrip().endswith("[1, S. 5]")
    assert out.count("[1, S. 5]") == 1          # exactly one anchor, no per-line wall


def test_anchor_separated_from_body():
    out = _append_scope_anchor("Inhalt der Seite.", 2, 30)
    assert "Inhalt der Seite." in out
    assert "\n\n[2, S. 30]" in out               # blank line before the chip
