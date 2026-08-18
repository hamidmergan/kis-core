from src.features.ai_assistant.prompts.rag_prompts import aia_system_rag


def test_prompt_has_no_citation_injection():
    p = aia_system_rag()
    assert "[N, #C" not in p          # no chunk-id chip instruction
    assert "CITATION FORMAT" not in p
    assert "keyword" not in p.lower() # no verbatim-keyword rule


def test_prompt_still_demands_grounded_answer():
    p = aia_system_rag()
    assert "ONLY" in p                # answer only from <documents>
    assert "NEVER invent" in p
