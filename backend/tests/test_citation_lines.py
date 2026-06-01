from src.features.ai_assistant.routes._helpers import is_citable_line


def test_classifier():
    assert is_citable_line("- Das Paper hat 6-7 Seiten.", in_summary=False)
    assert is_citable_line("| Themenfindung | bis April |", in_summary=False)  # table row
    assert not is_citable_line("## Prüfungsleistung", in_summary=False)        # heading
    assert not is_citable_line("Die Prüfungsleistung besteht aus:", in_summary=False)  # intro
    assert not is_citable_line("- Recap point.", in_summary=True)              # summary block
    assert not is_citable_line("", in_summary=False)                          # blank
    assert not is_citable_line("|---|---|", in_summary=False)                 # table separator
