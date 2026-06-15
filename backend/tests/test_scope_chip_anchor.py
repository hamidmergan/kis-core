"""Single-page scope summary keeps ONE click-to-page anchor chip.

A single-page PDF scope ("fasse Seite 5 zusammen") must not chip every line with the
page the user named (pure noise in nav-only mode). The route skips per-line
attribution for it and appends exactly one ``[N, S. X]`` anchor at the bottom via
``_append_scope_anchor`` — a single jump-to-page link. The frontend renders that as a
chip.
"""
from src.features.ai_assistant.routes._helpers import _append_scope_anchor


def test_appends_single_anchor_at_bottom():
    body = "- 3.5.6 2D-Filterung\n- 4 Video"
    out = _append_scope_anchor(body, 1, 5)
    assert out.rstrip().endswith("[1, S. 5]")
    assert out.count("[1, S. 5]") == 1          # exactly one anchor, no per-line wall


def test_anchor_separated_from_body():
    out = _append_scope_anchor("Inhalt der Seite.", 2, 30)
    assert "Inhalt der Seite." in out
    assert "\n\n[2, S. 30]" in out               # blank line before the chip
