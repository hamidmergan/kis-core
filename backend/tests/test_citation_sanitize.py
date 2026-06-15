"""Stray-bracket cleanup in the chat answer pipeline.

Despite the prompt forbidding the model from citing sources (tool_prompts), some
models (Qwen-family especially) still leak a bare 【source】 / 【Quelle】 placeholder
with no page/timestamp inside. That is never a real citation — the chip parser needs
"S. X" or "MM:SS" inside the bracket — so it would render as dead text and survive the
copy-strip. _sanitize_citations drops it while keeping real citations untouched.
"""

from src.features.ai_assistant.routes._helpers import _sanitize_citations


def test_strips_stray_lenticular_placeholder_keeps_real_citation():
    out = _sanitize_citations("Die Abgabe ist am 03.07.2026【source】 [1, S. 6]")
    assert "source" not in out
    assert "【" not in out
    assert "[1, S. 6]" in out  # real nav citation kept


def test_strips_bare_quelle_placeholder():
    out = _sanitize_citations("Ergebnis【Quelle】 weiter")
    assert out == "Ergebnis weiter"


def test_keeps_valid_lenticular_citation():
    # A 【…】 that carries a page IS a real citation (the frontend parser accepts 【】).
    out = _sanitize_citations("Text 【1, S. 6】 mehr")
    assert "【1, S. 6】" in out


def test_keeps_valid_lenticular_timestamp_citation():
    out = _sanitize_citations("Audio 【1, 08:58】 hier")
    assert "【1, 08:58】" in out
