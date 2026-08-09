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

import pytest

from src.services.aia_grammar_topic import derive_topic, usable_label


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


def test_a_provider_failure_is_not_confused_with_a_bad_topic():
    """Am laufenden System aufgefallen: der Anbieter meldete "Model Not Loaded", und
    der Dozent las "daraus lässt sich kein Grammatikthema machen". Er hätte seinen
    völlig richtigen Themennamen umgeschrieben, obwohl nur der Dienst weg war.

    Eine Störung muss also durchschlagen, damit der Aufrufer sie als solche melden
    kann. Ein Modell, das antwortet und dabei Unsinn liefert, bleibt None.
    """
    def create(**kwargs):
        raise RuntimeError("Model Not Loaded.")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    with pytest.raises(RuntimeError):
        derive_topic(client, "m", "Konjunktiv II", "de")


def test_a_fenced_answer_is_still_parsed():
    client, _ = _client(f"```json\n{_GOOD}\n```")
    assert derive_topic(client, "m", "Konjunktiv II", "de") is not None


def test_only_the_first_example_is_kept():
    # Der Generator liest nur das erste Paar, weitere zu speichern hiesse sie in der
    # Tabelle abzulegen und nie wieder anzusehen.
    pairs = [{"before": f"Satz {i} hier.", "after": f"Umgeformt {i} hier."}
             for i in range(5)]
    client, _ = _client(json.dumps({"is_grammar": True, "rule": "r", "examples": pairs}))
    out = derive_topic(client, "m", "X", "de")
    assert out["examples"] == [{"before": "Satz 0 hier.", "after": "Umgeformt 0 hier."}]


# ─── Der Namensvorschlag ─────────────────────────────────────────────────────

def test_a_clean_name_comes_through():
    assert usable_label("Passiv Präsens") == "Passiv Präsens"


def test_surrounding_space_is_trimmed():
    assert usable_label("  Perfekt  ") == "Perfekt"


@pytest.mark.parametrize("value", [None, "", "   ", 42, ["Passiv"], {"a": 1}])
def test_nothing_usable_is_no_suggestion(value):
    """Leer ist kein Fehler. Der Vorschlag ist Komfort und keine Prüfstelle."""
    assert usable_label(value) == ""


def test_a_whole_paragraph_is_no_suggestion():
    # Ein Modell, das statt eines Namens einen Absatz liefert, hat die Frage nicht
    # verstanden. Ein Absatz auf einer Kachel wäre schlimmer als kein Vorschlag.
    assert usable_label("x" * 61) == ""
    assert usable_label("x" * 60) == "x" * 60


def test_more_than_one_line_is_no_suggestion():
    assert usable_label("Passiv Präsens\nund noch etwas") == ""
    assert usable_label("Passiv Präsens\rund noch etwas") == ""


def test_the_suggested_name_comes_back():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r", "label": "Passiv Präsens",
        "examples": [{"before": "Das Team schreibt den Bericht.",
                      "after": "Der Bericht wird vom Team geschrieben."}],
    }))
    assert derive_topic(client, "m", "passi", "de")["label"] == "Passiv Präsens"


def test_a_topic_without_a_suggested_name_is_still_created():
    """Ein Modell, das die neue Zeile im Prompt überliest, darf kein Thema kosten.
    Der Vorschlag ist Komfort und keine Prüfstelle."""
    client, _ = _client(_GOOD)
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out is not None
    assert out["label"] == ""


def test_an_unusable_suggested_name_does_not_cost_the_topic():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r", "label": "x" * 200,
        "examples": [{"before": "Er kommt morgen.", "after": "Er käme morgen."}],
    }))
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out is not None
    assert out["label"] == ""


def test_the_prompt_asks_for_the_suggested_name():
    client, calls = _client(_GOOD)
    derive_topic(client, "m", "Konjunktiv II", "de")
    sent = " ".join(m["content"] for m in calls[0])
    assert "label" in sent


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
