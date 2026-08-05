"""Aus einem getippten Namen werden Regel und Musterbeispiel.

Die Grammatik-Übung ist das einzige Werkzeug, das nicht aus den Quellen
antwortet: das Thema kommt vom Dozenten, die Grammatik aus dem Modell, die
Quellen liefern nur den Wortschatz. Damit fällt die Quellen-Grenze als Netz gegen
einen Irrtum weg, und das Musterbeispiel wird zur einzigen Prüfstelle.

Deshalb wird hier lieber abgelehnt als geraten. Ein falsches Muster würde einem
ganzen Kurs die falsche Form beibringen, und niemand merkt es an der Aufgabe,
weil sie in sich stimmig aussieht.

Kein Netzzugriff, das Modell bekommt einen Fake-Client.
"""

import json
import types

from src.services.aia_grammar_topic import derive_topic


def _client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


_GOOD = json.dumps({
    "is_grammar": True,
    "rule": "Input: indicative present. Output: Konjunktiv II.",
    "examples": [{"before": "Er kommt morgen.", "after": "Er käme morgen."}],
})


def test_a_grammar_topic_yields_rule_and_example():
    client, _ = _client(_GOOD)
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out["rule"].startswith("Input:")
    assert out["examples"][0]["before"] == "Er kommt morgen."
    assert out["examples"][0]["after"] == "Er käme morgen."


def test_the_prompt_carries_the_typed_name_and_the_language():
    client, calls = _client(_GOOD)
    derive_topic(client, "m", "Konjunktiv II", "de")
    sent = " ".join(m["content"] for m in calls[0])
    assert "Konjunktiv II" in sent
    assert "German" in sent


def test_something_that_is_not_grammar_is_refused():
    # "Photosynthese" ist ein Fachthema, kein Grammatikthema. Daraus einen Eintrag
    # zu erfinden wäre schlimmer als eine Absage.
    client, _ = _client(json.dumps({"is_grammar": False, "rule": "", "examples": []}))
    assert derive_topic(client, "m", "Photosynthese", "de") is None


def test_an_example_that_changes_nothing_is_refused():
    """Vorher gleich nachher heisst, das Modell hat die Umformung nicht
    verstanden. Sprach-unabhängig geprüft, ohne Wortlisten."""
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r",
        "examples": [{"before": "Er kommt.", "after": "Er kommt!"}],
    }))
    assert derive_topic(client, "m", "Irgendwas", "de") is None


def test_an_answer_without_any_example_is_refused():
    client, _ = _client(json.dumps({"is_grammar": True, "rule": "r", "examples": []}))
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_an_answer_without_a_rule_is_refused():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "  ",
        "examples": [{"before": "a b c.", "after": "c b a."}],
    }))
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_unusable_json_is_refused_instead_of_crashing():
    client, _ = _client("kein json")
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_a_provider_error_is_refused_instead_of_crashing():
    def create(**kwargs):
        raise RuntimeError("Connection error.")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_a_fenced_answer_is_still_parsed():
    client, _ = _client(f"```json\n{_GOOD}\n```")
    assert derive_topic(client, "m", "Konjunktiv II", "de") is not None


def test_more_than_three_examples_are_cut_back():
    # Die Ansicht zeigt drei, mehr zu speichern hiesse sie stillschweigend zu verlieren.
    pairs = [{"before": f"Satz {i} hier.", "after": f"Umgeformt {i} hier."}
             for i in range(5)]
    client, _ = _client(json.dumps({"is_grammar": True, "rule": "r", "examples": pairs}))
    out = derive_topic(client, "m", "X", "de")
    assert len(out["examples"]) == 3


def test_a_broken_pair_is_dropped_but_the_good_ones_stay():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r",
        "examples": [
            {"before": "", "after": "x"},
            {"before": "Er kommt morgen.", "after": "Er käme morgen."},
        ],
    }))
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert len(out["examples"]) == 1
    assert out["examples"][0]["before"] == "Er kommt morgen."
