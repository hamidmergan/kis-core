from src.features.ai_assistant.routes._helpers import _sanitize_citations


def test_sanitize_repairs_page_and_time():
    assert _sanitize_citations("Foo [1] S. 3 bar") == "Foo [1, S. 3] bar"
    assert _sanitize_citations("Clip [2] 05:32 end") == "Clip [2, 05:32] end"
