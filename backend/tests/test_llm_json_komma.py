"""Ein überzähliges Komma des LLM vor ] oder } kostet keine Übung mehr.

Lauf 15, 27.09.: zweimal scheiterte ein Quiz an "Expecting value: line 11 column 7", gemma4-31b
hatte nach der letzten Antwortmöglichkeit ein Komma stehen lassen.
"""
import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json


def test_das_komma_nach_der_letzten_moeglichkeit_faellt_weg():
    roh = """```json
{
  "items": [
    {
      "question": "Wann wird der Raum gebucht?",
      "options": [
        "Am Tag der Veranstaltung",
        "Spätestens eine Woche vorher",
        "Zwei Wochen im Voraus",
        "Nur nach Abschluss der Vorbereitung",
      ],
      "correct_idx": 1,
    },
  ]
}
```"""
    daten = json.loads(_clean_llm_json(roh))
    assert daten["items"][0]["options"][-1] == "Nur nach Abschluss der Vorbereitung"
    assert daten["items"][0]["correct_idx"] == 1


def test_kommas_in_texten_bleiben_stehen():
    roh = '{"satz": "Liste: a, ], b, }", "zitat": "Er sagte \\", ]\\" und ging", "n": [1, 2]}'
    daten = json.loads(_clean_llm_json(roh))
    assert daten["satz"] == "Liste: a, ], b, }"
    assert daten["zitat"] == 'Er sagte ", ]" und ging'


def test_notiz_nach_dem_codeblock_faellt_weg():
    # Lokal 08.10.: gemma4:31b hängte an den Lückentext einen "Korrekturhinweis (intern)" an.
    roh = '```json\n{\n  "text": "Ein `Paper` schreiben",\n  "gaps": []\n}\n```\n\n**Korrekturhinweis:**\n1. `Paper`'
    assert json.loads(_clean_llm_json(roh)) == {"text": "Ein `Paper` schreiben", "gaps": []}


def test_gueltiges_json_bleibt_wie_es_ist():
    roh = '{"a": [1, 2, 3], "b": {"c": "d, e"}}'
    assert _clean_llm_json(roh) == roh
