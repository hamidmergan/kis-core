"""A model verdict on the sentence the learner is left with, passed when in doubt."""

import json
import types

from src.features.ai_assistant.tasks.language_training._grammar_verify import verdicts


_FORM = "Konjunktiv II mit Modalverben"
_RULE = "Input: a fact stated as real. Output: the same as a hypothetical with a modal verb in Konjunktiv II."

# The reported case: the target form itself is right, the sentence around it is not.
_SATZ_KAPUTT = ("Wenn die Altstadt kein Weltkulturerbe wäre, dürfte man dort "
                "vielleicht mehr Gebäude modern bauen.")

_SATZ_SAUBER = "Wenn der Server ausfiele, müssten die Messwerte manuell erfasst werden."

# The reported case: a theory question instead of an exercise.
_THEORIESATZ = "Das Verb steht im Relativsatz immer am Ende."


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
    """The checker's answer: (number, usable) per sentence."""
    return json.dumps({"verdicts": [{"i": i, "ok": ok} for i, ok in paare]})


def _aufgabenzeilen(calls) -> str:
    """The sent sentence lines, without the prompt."""
    return "\n".join(m["content"] for m in calls[0] if m["role"] == "user")


def test_absichtlich_falsche_aussage_wird_gekennzeichnet():
    """Without the marker the checker would report every deliberately wrong statement."""
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_THEORIESATZ], _FORM, _RULE, wrong_on_purpose=[True])
    assert "wrong on purpose" in _aufgabenzeilen(calls)


def test_luecke_geht_mit_der_sicht_der_lernenden_mit():
    """Reported: the gap swallowed the noun, only the gap sentence shows it."""
    satz = "Das Geschäft bleibt wegen eines kurzen Umbaus geschlossen."
    luecke = "Das Geschäft bleibt wegen eines ___ (kurz) geschlossen."
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [satz], _FORM, _RULE, gaps=[(luecke, "kurzen Umbaus")])
    zeilen = _aufgabenzeilen(calls)
    assert luecke in zeilen
    assert '"kurzen Umbaus"' in zeilen


def test_satz_ohne_luecke_bleibt_ohne_luecken_angabe():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_SATZ_SAUBER], _FORM, _RULE, gaps=[None])
    assert "gap shown" not in _aufgabenzeilen(calls)


def test_richtige_aussage_wird_nicht_gekennzeichnet():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_THEORIESATZ], _FORM, _RULE)
    assert "wrong on purpose" not in _aufgabenzeilen(calls)


def test_der_satz_steht_im_pruefauftrag():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_SATZ_KAPUTT], _FORM, _RULE)
    gesendet = "\n".join(m["content"] for m in calls[0])
    assert _SATZ_KAPUTT in gesendet


def test_zielform_und_regel_stehen_im_pruefauftrag():
    client, calls = _client(_urteil((0, True)))
    verdicts(client, "m", [_SATZ_KAPUTT], _FORM, _RULE)
    gesendet = "\n".join(m["content"] for m in calls[0])
    assert _FORM in gesendet
    assert _RULE in gesendet


def test_gemeldeter_satz_faellt_raus():
    client, _ = _client(_urteil((0, False), (1, True)))
    assert verdicts(client, "m", [_SATZ_KAPUTT, _SATZ_SAUBER], _FORM, _RULE) == [False, True]


def test_theoriesatz_faellt_raus():
    client, _ = _client(_urteil((0, True), (1, False)))
    assert verdicts(client, "m", [_SATZ_SAUBER, _THEORIESATZ], _FORM, _RULE) == [True, False]


def test_unlesbare_antwort_laesst_alles_durch():
    """A checker that discards on doubt turns a good set into a too short one."""
    client, _ = _client("kein JSON, nur Text")
    assert verdicts(client, "m", [_SATZ_KAPUTT, _SATZ_SAUBER], _FORM, _RULE) == [True, True]


def test_stoerung_laesst_alles_durch():
    """The exercises are complete without this call, only unchecked."""

    def create(model, messages, **kwargs):
        raise RuntimeError("429 Too Many Requests")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    assert verdicts(client, "m", [_SATZ_KAPUTT], _FORM, _RULE) == [True]


def test_fehlendes_urteil_laesst_den_satz_durch():
    """The model likes to skip a number, that is no reason to discard."""
    client, _ = _client(_urteil((1, False)))
    assert verdicts(client, "m", [_SATZ_SAUBER, _THEORIESATZ], _FORM, _RULE) == [True, False]


def test_urteil_ausserhalb_der_liste_wird_ignoriert():
    client, _ = _client(_urteil((0, False), (7, False)))
    assert verdicts(client, "m", [_SATZ_SAUBER], _FORM, _RULE) == [False]


def test_ok_als_wort_zaehlt_auch_als_meldung():
    """Models like to write 'false' as text, a report stays a report."""
    client, _ = _client(json.dumps({"verdicts": [{"i": 0, "ok": "false"}]}))
    assert verdicts(client, "m", [_THEORIESATZ], _FORM, _RULE) == [False]


def test_ohne_saetze_kein_aufruf():
    """Without sentences not a single model call happens."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [], _FORM, _RULE) == []
    assert calls == []


def test_ohne_beurteilbaren_satz_kein_aufruf():
    """An empty sentence yields nothing to check."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [""], _FORM, _RULE) == [True]
    assert calls == []
