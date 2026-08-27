"""A model verdict on the sentence the learner is left with, passed when in doubt."""

import json
import types

from src.features.ai_assistant.tasks.language_training._grammar_verify import (
    solved_text,
    verdicts,
)


_FORM = "Passiv mit Modalverb Präsens"
_RULE = "Input: an active sentence with a modal verb. Output: the same in the passive."

# The reported case: the solution is right, the sentence with it is not.
_LUECKE_KAPUTT = {
    "kind": "cloze",
    "sentence": "Die Familienmitglieder ___ am Wochenende treffen.",
    "answer": "müssen getroffen werden",
    "options": ["müssen getroffen werden", "werden getroffen",
                "müssen treffen werden", "sollen getroffen sein"],
    "correct_idx": 0,
}

# The reported case: a theory question instead of an exercise.
_THEORIE = {
    "kind": "statement",
    "statement": "Das Verb steht im Relativsatz immer am Ende.",
    "answer": True,
}

_SAUBER = {
    "kind": "cloze",
    "sentence": "Die Messwerte ___ vom Server gespeichert.",
    "answer": "müssen werden",
    "options": ["müssen werden", "werden", "muss werden", "sollen sein"],
    "correct_idx": 0,
}


def _client(content):
    """Fake client with a fixed answer, collects the sent messages."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _urteil(*paare):
    """The checker's answer: (number, usable) per exercise."""
    return json.dumps({"verdicts": [{"i": i, "ok": ok} for i, ok in paare]})


def _aufgabenzeilen(calls) -> str:
    """The sent exercise lines, without the prompt."""
    return "\n".join(m["content"] for m in calls[0] if m["role"] == "user")


def test_solved_text_fuellt_die_luecke():
    """The checker has to see the sentence WITH the solution, otherwise the reported case slips through."""
    assert solved_text(_LUECKE_KAPUTT) == (
        "Die Familienmitglieder müssen getroffen werden am Wochenende treffen."
    )


def test_solved_text_nimmt_die_markierte_option():
    """In multiple choice the learner is left with the marked option."""
    ex = {"kind": "choice", "sentence": "Das Team schreibt den Bericht.",
          "options": ["Der Bericht wird vom Team geschrieben.",
                      "Der Bericht ist vom Team geschrieben."],
          "correct_idx": 0}
    assert solved_text(ex) == "Der Bericht wird vom Team geschrieben."


def test_absichtlich_falsche_aussage_wird_gekennzeichnet():
    """Without the marker the checker would report every deliberately wrong statement."""
    falsch = {"kind": "statement",
              "statement": "Der Bericht wird vom Team geschrieben werden müssen.",
              "answer": False}
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [falsch], _FORM, _RULE)
    assert "wrong on purpose" in _aufgabenzeilen(calls)


def test_richtige_aussage_wird_nicht_gekennzeichnet():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_THEORIE], _FORM, _RULE)
    assert "wrong on purpose" not in _aufgabenzeilen(calls)


def test_der_gefuellte_satz_steht_im_pruefauftrag():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_LUECKE_KAPUTT], _FORM, _RULE)
    gesendet = "\n".join(m["content"] for m in calls[0])
    assert "müssen getroffen werden am Wochenende treffen" in gesendet


def test_zielform_und_regel_stehen_im_pruefauftrag():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_LUECKE_KAPUTT], _FORM, _RULE)
    gesendet = "\n".join(m["content"] for m in calls[0])
    assert _FORM in gesendet
    assert _RULE in gesendet


def test_gemeldete_aufgabe_faellt_raus():
    client, _ = _client(_urteil((0, False), (1, True)))
    assert verdicts(client, "m", [_LUECKE_KAPUTT, _SAUBER], _FORM, _RULE) == [False, True]


def test_theoriesatz_faellt_raus():
    client, _ = _client(_urteil((0, True), (1, False)))
    assert verdicts(client, "m", [_SAUBER, _THEORIE], _FORM, _RULE) == [True, False]


def test_unlesbare_antwort_laesst_alles_durch():
    """A checker that discards on doubt turns a good set into a too short one."""
    client, _ = _client("kein JSON, nur Text")
    assert verdicts(client, "m", [_LUECKE_KAPUTT, _SAUBER], _FORM, _RULE) == [True, True]


def test_stoerung_laesst_alles_durch():
    """The exercises are complete without this call, only unchecked."""

    def create(model, messages, **kwargs):
        raise RuntimeError("429 Too Many Requests")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    assert verdicts(client, "m", [_LUECKE_KAPUTT], _FORM, _RULE) == [True]


def test_fehlendes_urteil_laesst_die_aufgabe_durch():
    """The model likes to skip a number, that is no reason to discard."""
    client, _ = _client(_urteil((1, False)))
    assert verdicts(client, "m", [_SAUBER, _THEORIE], _FORM, _RULE) == [True, False]


def test_urteil_ausserhalb_der_liste_wird_ignoriert():
    client, _ = _client(_urteil((0, False), (7, False)))
    assert verdicts(client, "m", [_SAUBER], _FORM, _RULE) == [False]


def test_ok_als_wort_zaehlt_auch_als_meldung():
    """Models like to write 'false' as text, a report stays a report."""
    client, _ = _client(json.dumps({"verdicts": [{"i": 0, "ok": "false"}]}))
    assert verdicts(client, "m", [_THEORIE], _FORM, _RULE) == [False]


def test_ohne_aufgaben_kein_aufruf():
    """Without exercises not a single model call happens."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [], _FORM, _RULE) == []
    assert calls == []


def test_ohne_beurteilbaren_satz_kein_aufruf():
    """A kind that does not exist yields no sentence and therefore nothing to check."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [{"kind": "quatsch"}], _FORM, _RULE) == [True]
    assert calls == []
