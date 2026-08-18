"""Der Prüf-Call für Grammatik-Aufgaben.

Er urteilt über den Satz, mit dem der Lernende am Ende dasteht: die Lücke gefüllt,
die markierte Option eingesetzt. Genau dort sassen die Meldungen vom 2026-08-12, die
kein Filter im Code fangen kann:

* "Die Familienmitglieder ___ am Wochenende treffen." mit der Lösung "müssen getroffen
  werden" ergibt einen unlesbaren Satz, aber "treffen" und "getroffen" sind zwei
  verschiedene Wörter. Ein Wortvergleich sieht die Dopplung nicht.
* "Das Verb steht im Relativsatz immer am Ende." ist eine Aussage ÜBER die Grammatik
  und keine Übung IN ihr. Ohne Wortlisten ist das im Code nicht zu erkennen.

Deshalb ein Modell-Urteil, und deshalb nur EIN Aufruf für alle Aufgaben zusammen.

Verworfen wird nur, was das Modell ausdrücklich meldet. Alles andere kommt durch,
auch eine unlesbare Antwort und auch eine Störung des Anbieters. Ein Prüfer, der bei
Zweifel wegwirft, macht aus einem guten Set ein zu kurzes.

Kein DB- und kein Netzzugriff.
"""

import json
import types

from src.features.ai_assistant.tasks.language_training._grammar_verify import (
    solved_text,
    verdicts,
)


_FORM = "Passiv mit Modalverb Präsens"
_RULE = "Input: an active sentence with a modal verb. Output: the same in the passive."

# Die Meldung 5 vom 2026-08-12: die Lösung ist richtig, der Satz mit ihr nicht.
_LUECKE_KAPUTT = {
    "kind": "cloze",
    "sentence": "Die Familienmitglieder ___ am Wochenende treffen.",
    "answer": "müssen getroffen werden",
    "options": ["müssen getroffen werden", "werden getroffen",
                "müssen treffen werden", "sollen getroffen sein"],
    "correct_idx": 0,
}

# Die Meldung 4: eine Theoriefrage statt einer Übung.
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
    """Fake-Client mit fester Antwort. Sammelt die gesendeten Nachrichten."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _urteil(*paare):
    """Antwort des Prüfers: (Nummer, ob brauchbar) je Aufgabe."""
    return json.dumps({"verdicts": [{"i": i, "ok": ok} for i, ok in paare]})


def _aufgabenzeilen(calls) -> str:
    """Die gesendeten Aufgabenzeilen, ohne den Prompt.

    Getrennt betrachtet, weil der Prompt die Kennzeichnung erklärt und damit selbst
    enthält. Ein Test auf die ganze Unterhaltung wäre immer erfüllt.
    """
    return "\n".join(m["content"] for m in calls[0] if m["role"] == "user")


def test_solved_text_fuellt_die_luecke():
    """Der Prüfer muss den Satz MIT der Lösung sehen, sonst fällt Meldung 5 nicht auf."""
    assert solved_text(_LUECKE_KAPUTT) == (
        "Die Familienmitglieder müssen getroffen werden am Wochenende treffen."
    )


def test_solved_text_nimmt_die_markierte_option():
    """Beim Ankreuzen steht der Lernende mit der markierten Option da."""
    ex = {"kind": "choice", "sentence": "Das Team schreibt den Bericht.",
          "options": ["Der Bericht wird vom Team geschrieben.",
                      "Der Bericht ist vom Team geschrieben."],
          "correct_idx": 0}
    assert solved_text(ex) == "Der Bericht wird vom Team geschrieben."


def test_absichtlich_falsche_aussage_wird_gekennzeichnet():
    """Die Hälfte aller Richtig/Falsch-Aussagen ist mit Absicht fehlerhaft.

    Ohne diese Kennzeichnung würde der Prüfer sie alle melden, denn er sucht ja nach
    Sätzen, die nicht stimmen. Übrig blieben nur die richtigen, und der Lernende
    bekäme ein Format, in dem "Falsch" nie die Antwort ist.
    """
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
    """Ein Prüfer, der bei Zweifel wegwirft, macht aus einem guten Set ein zu kurzes."""
    client, _ = _client("kein JSON, nur Text")
    assert verdicts(client, "m", [_LUECKE_KAPUTT, _SAUBER], _FORM, _RULE) == [True, True]


def test_stoerung_laesst_alles_durch():
    """Die Aufgaben sind ohne diesen Aufruf vollständig, nur ungeprüft."""

    def create(model, messages, **kwargs):
        raise RuntimeError("429 Too Many Requests")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    assert verdicts(client, "m", [_LUECKE_KAPUTT], _FORM, _RULE) == [True]


def test_fehlendes_urteil_laesst_die_aufgabe_durch():
    """Das Modell überspringt gern eine Nummer. Das ist kein Grund zu verwerfen."""
    client, _ = _client(_urteil((1, False)))
    assert verdicts(client, "m", [_SAUBER, _THEORIE], _FORM, _RULE) == [True, False]


def test_urteil_ausserhalb_der_liste_wird_ignoriert():
    client, _ = _client(_urteil((0, False), (7, False)))
    assert verdicts(client, "m", [_SAUBER], _FORM, _RULE) == [False]


def test_ok_als_wort_zaehlt_auch_als_meldung():
    """Modelle schreiben "false" gern als Text. Eine Meldung bleibt eine Meldung."""
    client, _ = _client(json.dumps({"verdicts": [{"i": 0, "ok": "false"}]}))
    assert verdicts(client, "m", [_THEORIE], _FORM, _RULE) == [False]


def test_ohne_aufgaben_kein_aufruf():
    """Ohne Aufgaben faellt kein einziger Modell-Aufruf an."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [], _FORM, _RULE) == []
    assert calls == []


def test_ohne_beurteilbaren_satz_kein_aufruf():
    """Eine Art, die es nicht gibt, ergibt keinen Satz und damit nichts zu prüfen."""
    client, calls = _client(_urteil())
    assert verdicts(client, "m", [{"kind": "quatsch"}], _FORM, _RULE) == [True]
    assert calls == []
