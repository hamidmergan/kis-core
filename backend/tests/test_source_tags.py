"""Short stand-ins for file names in tool prompts and the way back."""

from src.features.ai_assistant.tasks._source_tags import SourceTags

_A = "02_WissenschaftlichesArbeiten.pdf"
_B = "VL1_25-03-2026.webm"


def test_the_model_reads_tags_instead_of_file_names():
    tags = SourceTags([_A, _B])
    out = tags.encode([{"role": "system", "content": "Mind map rules."},
                       {"role": "user", "content": f"--- {_A} ---\n[{_A}, S. 3] Text\n[{_B}, 1:20] Ton"}])
    user = out[-1]["content"]
    assert user == "--- Q1 ---\n[Q1, S. 3] Text\n[Q2, 1:20] Ton"
    # Not even a legend, the model copied names from it and made one up.
    assert _A not in user and _B not in user


def test_the_answer_gets_the_file_names_back_at_every_depth():
    tags = SourceTags([_A, _B])
    antwort = {"topic": "Wurzel", "children": [
        {"topic": "Ast", "source_label": "Q1", "children": [
            {"topic": "Blatt", "source_label": " Q2 ", "page_number": 4}]}]}
    zurueck = tags.decode(antwort)
    assert zurueck["children"][0]["source_label"] == _A
    assert zurueck["children"][0]["children"][0]["source_label"] == _B
    assert zurueck["children"][0]["children"][0]["page_number"] == 4


def test_an_unknown_label_stays_as_the_model_wrote_it():
    tags = SourceTags([_A])
    assert tags.decode({"source_label": _A})["source_label"] == _A
    assert tags.decode({"source_label": "Q7"})["source_label"] == "Q7"


def test_a_name_inside_a_longer_name_is_not_cut_apart():
    tags = SourceTags(["a.pdf", "data.pdf"])
    assert tags.encode_text("[data.pdf, S. 1] [a.pdf, S. 2]") == "[Q2, S. 1] [Q1, S. 2]"
