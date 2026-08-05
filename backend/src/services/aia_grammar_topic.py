"""Aus einem getippten Themennamen Regel und Musterbeispiel machen.

Der Dozent tippt zwei Wörter, etwa "Konjunktiv II". Daraus entsteht in einem
Aufruf genau das, was bisher von Hand im Code stand: eine Regel für das Modell
und ein ausgearbeitetes Musterpaar in der Kurssprache.

Warum hier strenger geprüft wird als anderswo: Die Grammatik-Übung ist das
einzige Werkzeug, das nicht aus den Quellen antwortet. Das Thema kommt vom
Dozenten, die Grammatik aus dem Modell, die Quellen liefern nur den Wortschatz.
Damit fällt die Quellen-Grenze als Netz gegen einen Irrtum weg. Ein falsches
Musterpaar würde einem ganzen Kurs die falsche Form beibringen, und niemand
merkt es an der Aufgabe, weil sie in sich stimmig aussieht.

Deshalb wird lieber abgelehnt als geraten, und was durchkommt, bekommt der
Dozent vor dem Speichern zu sehen.
"""

import json

from loguru import logger

from src.features.ai_assistant.repository.grammar_topics import MAX_EXAMPLES
from src.services.aia_grammar_check import normalize


_PROMPT = (
    "A teacher wants their students to practise a grammar topic. You turn the topic "
    "name into a machine-readable description.\n\n"
    "Respond ONLY with a JSON object:\n"
    '{"is_grammar": true, '
    '"rule": "One paragraph in English naming the input form and the expected output '
    'form of the transformation", '
    '"examples": [{"before": "A sentence in the original form", '
    '"after": "The same sentence transformed"}]}\n\n'
    "Rules:\n"
    '- "is_grammar" is false when the name does not describe a grammatical form at '
    "all, for example a subject such as photosynthesis, a person, or plain nonsense. "
    "Then return an empty rule and an empty list.\n"
    '- "rule" is read by another model and never by a learner. Name the input form '
    "and the output form precisely, the way a grammar reference would.\n"
    "- Give exactly ONE example. 'before' and 'after' are each ONE sentence and must "
    "differ from each other, otherwise there is nothing to practise.\n"
    "- Write the example in {language}, whatever language the topic name is written in.\n"
    "- Use no personal names. Write 'die Dozentin', 'das Team' or 'the lecturer' "
    "instead, matching the output language.\n"
)


def derive_topic(client, model, name: str, language: str) -> dict | None:
    """Regel und Musterbeispiel zu einem Themennamen, oder ``None``.

    ``None`` heisst: daraus lässt sich kein Grammatikthema machen. Der Aufrufer
    zeigt eine Absage, statt einen erfundenen Eintrag zu speichern.

    Eine **Störung** des Anbieters schlägt dagegen durch. Am laufenden System
    aufgefallen: der Dienst meldete "Model Not Loaded", und der Dozent las
    "daraus lässt sich kein Grammatikthema machen". Er hätte seinen völlig
    richtigen Themennamen umgeschrieben, obwohl nur der Dienst weg war. Zwei
    verschiedene Ursachen brauchen zwei verschiedene Meldungen.
    """
    # Erst hier geholt, nicht oben: das Aufgaben-Paket importiert seinerseits
    # derive_topic, ein Import auf Modulebene ergäbe also einen Ringschluss. Die
    # beiden sind allgemeine Helfer für Modell-Ausgaben und liegen nur historisch
    # unter tasks/.
    from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

    label = _language_label(language)
    messages = [
        {"role": "system", "content": _PROMPT.replace("{language}", label)},
        {"role": "user", "content": f"Topic: {name}\n\nWrite the example in {label}."},
    ]
    # Niedrige Temperatur: hier ist keine Vielfalt gefragt, sondern die gängigste
    # und damit sicherste Lesart des Themennamens. Ein Fehler beim Aufruf selbst
    # geht bewusst nach oben durch, siehe Docstring.
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0.2)
    try:
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:
        # Das Modell hat geantwortet, aber unbrauchbar. Das ist eine Absage und
        # keine Störung: ein zweiter Versuch mit demselben Namen hilft nicht.
        logger.warning("Grammatik-Thema {!r} nicht lesbar beantwortet: {}", name, e)
        return None

    if not isinstance(data, dict) or not data.get("is_grammar"):
        logger.info("Grammatik-Thema {!r} abgelehnt, kein Grammatikthema", name)
        return None

    rule = (data.get("rule") or "").strip()
    examples = [pair for pair in (data.get("examples") or []) if is_usable_pair(pair)]
    if not rule or not examples:
        logger.info("Grammatik-Thema {!r} abgelehnt, Regel oder Beispiel fehlt", name)
        return None
    return {"rule": rule, "examples": examples[:MAX_EXAMPLES]}


def is_usable_pair(pair) -> bool:
    """Ob sich zwischen Vorher und Nachher wirklich etwas ändert.

    Gleich heisst, das Modell hat die Umformung nicht verstanden. Geprüft wird
    normalisiert, damit ein zusätzliches Ausrufezeichen nicht als Umformung
    durchgeht. Sprach-unabhängig, keine Wortlisten.
    """
    if not isinstance(pair, dict):
        return False
    before = (pair.get("before") or "").strip()
    after = (pair.get("after") or "").strip()
    if not before or not after:
        return False
    return normalize(before) != normalize(after)
