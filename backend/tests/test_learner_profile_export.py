from src.features.ai_assistant.routes.learner_profile import build_profile_markdown


def test_markdown_has_level_and_weaknesses():
    md = build_profile_markdown(
        level="A2",
        weaknesses=[
            {"label": "Konjunktiv", "category": "term", "effective_weight": 6.0, "hit_count": 3},
            {"label": "Mindmap", "category": "tool", "effective_weight": 1.0, "hit_count": 2},
        ],
    )
    assert "A2" in md
    assert "Konjunktiv" in md
    assert "Mindmap" in md


def test_markdown_without_level_says_none():
    md = build_profile_markdown(level=None, weaknesses=[])
    assert "kein" in md.lower() or "none" in md.lower()
