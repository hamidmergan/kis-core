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
    '"label": "The exact name of the form you worked out, in {language}", '
    '"examples": [{"before": "A sentence in the original form", '
    '"after": "The same sentence transformed"}], '
    '"task_lines": {"transform": "...", "cloze": "...", "statement": "...", '
    '"choice": "..."}}\n\n'
    "Rules:\n"
    '- "is_grammar" asks ONE question: does the name say something about how a '
    "sentence is BUILT, rather than what it is about? Word order, case, tense, mood, "
    "voice, sentence type and style contrasts such as Nominalstil versus Verbalstil "
    "all qualify, and so does a teaching mnemonic for one of them, even an obscure "
    'one: German "tekamolo" is the order temporal, kausal, modal, lokal, so it is a '
    "grammar topic. A name you do not recognise is not automatically nonsense. It is "
    "false for subject matter (photosynthesis), for a person, and for a string that "
    "says nothing about sentence structure. Then return an empty rule and an empty "
    "list.\n"
    '- "rule" is read by another model and never by a learner. Name the input form '
    "and the output form precisely, the way a grammar reference would.\n"
    '- "label" names the ONE form that the rule and the example actually describe, '
    "not the broader area the teacher typed. Resolve an ambiguous name: German "
    '"Passiv" covers nine different forms, so write "Passiv Präsens" when your example '
    "is in the present tense. At most five words, the way a course topic is titled. "
    "No quotes and no sentence.\n"
    "- Give exactly ONE example. 'before' and 'after' are each ONE sentence and must "
    "differ from each other, otherwise there is nothing to practise.\n"
    "- Write the example in {language}, whatever language the topic name is written in.\n"
    "- Use no personal names. Write 'die Dozentin', 'das Team' or 'the lecturer' "
    "instead, matching the output language.\n"
    '- "task_lines" are the four instructions a learner reads above an exercise, one per '
    "exercise kind, in {language}. They MUST name this topic in a grammatically correct "
    "sentence. Inflect it, do not paste the topic name into a fixed frame: for a plural "
    "or feminine topic a frame like \"Setze den Satz ins ...\" produces nonsense.\n"
    "  transform: the learner rewrites the sentence into this form. A worked example "
    "sits above that exercise, so point at it where it reads naturally, INSIDE the "
    "sentence and never as a comma-separated tail. Leave it out rather than force it.\n"
    "  cloze: the learner fills one missing word in this form.\n"
    "  statement: the learner judges whether the sentence is correct in this form.\n"
    "  choice: the learner picks which of several sentences is correct in this form.\n"
    "  Each is ONE short sentence, addressed to the learner, ending in a full stop or a "
    "question mark. No quotes around the topic name.\n"
    "  Write the sentence a teacher would write. Rephrase whatever the teacher typed "
    "until it fits: a topic name may be plural, may be an area rather than a form, may "
    "name a word-order rule, or may bundle several topics at once. Copy these shapes:\n"
    '    "Relativsatz" -> transform: "Forme den Satz nach dem Beispiel in einen '
    'Relativsatz um."   NOT "Setze den Satz ins Relativsatz, nach dem Beispiel."\n'
    '    "Adjektivdeklination ohne Artikel" -> transform: "Forme den Satz in einen Satz '
    'mit Adjektivdeklination ohne Artikel um."\n'
    '    "tekamolo" -> transform: "Bilde den Satz nach der tekamolo-Regel."\n'
    '    "Finalsätze Nominalstil Verbalstil" -> transform: "Forme den Satz nach dem '
    'Beispiel vom Nominalstil in den Verbalstil um."\n'
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
    from src.features.ai_assistant.tasks._helpers import _clean_llm_json

    # ``language`` darf der englische Sprachname sein ("German") oder der Sprachcode
    # ("de"). Beides kommt vor, und ein durchgereichter Code landete sonst wortwoertlich
    # im Prompt: "Write the example in de." Ein Test hat genau das gefunden.
    from src.i18n import TRANSCRIPT_LANGUAGES
    eintrag = TRANSCRIPT_LANGUAGES.get((language or "").lower())
    # Nicht ``label``: so heisst seit dem Namensvorschlag das Feld, das das Modell
    # zurückgibt. Zwei verschiedene Dinge unter einem Namen in einer Funktion.
    sprach_label = eintrag["name"] if eintrag else (language or "German")
    messages = [
        {"role": "system", "content": _PROMPT.replace("{language}", sprach_label)},
        {"role": "user",
         "content": f"Topic: {name}\n\nWrite the example in {sprach_label}."},
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
    return {"rule": rule, "examples": examples[:MAX_EXAMPLES],
            "task_lines": usable_task_lines(data.get("task_lines")),
            # Welche Form das Modell aus dem getippten Namen gemacht hat. Das Formular
            # bietet sie als Namen an, damit die Kachel nicht "passi" heisst, während
            # die Aufgaben Passiv Präsens üben.
            "label": usable_label(data.get("label"))}


def derive_task_lines(client, model, name: str, language: str) -> dict:
    """Nur die vier Anweisungszeilen, fuer Ausarbeitungen von vor diesem Feld.

    Themen, die vor den ``task_lines`` ausgearbeitet wurden, tragen Regel und
    Musterpaar, aber keine Zeilen. Ohne diesen Nachschlag bekaemen sie nie welche,
    denn ausgearbeitet wird nur, was noch gar nicht ausgearbeitet ist, und sie
    haengen damit dauerhaft an der Schablone. Genau das wurde am 2026-08-12
    gemeldet.

    Regel und Musterpaar werden ausdruecklich NICHT mit zurueckgegeben. Der Dozent
    darf beide im Formular von Hand geaendert haben, und ein Nachschlag fuer eine
    Anweisungszeile darf ihm diese Arbeit nicht ueberschreiben.

    Klappt es nicht, kommt ein leeres dict zurueck und es bleibt bei der Schablone.
    Anders als beim ersten Ausarbeiten ist eine Stoerung des Anbieters hier kein
    Grund, den ganzen Satz scheitern zu lassen: die Aufgaben selbst sind ohne
    diesen Aufruf vollstaendig, nur die Anweisung ueber ihnen ist nuechterner.

    Ein Fehlschlag wird nicht festgehalten, der naechste Satz fragt also erneut.
    Das ist Absicht. Die Ablehnung ist nicht stabil: "tekamolo" wurde in vier
    Anlaeufen dreimal angenommen und einmal abgelehnt, und wer einmal Pech hat,
    haette sonst fuer immer die nuechterne Zeile. Der Aufruf faellt weg, sobald er
    einmal geklappt hat, und er kostet nur bei Themen von vor dem Feld etwas.
    """
    try:
        derived = derive_topic(client, model, name, language)
    except Exception as e:
        logger.warning("Anweisungszeilen fuer {!r} nicht nachgereicht: {}", name, e)
        return {}
    return (derived or {}).get("task_lines") or {}


# Die vier Aufgabenformate, fuer die es je eine Anweisung braucht.
TASK_KINDS = ("transform", "cloze", "statement", "choice")


def usable_task_lines(lines) -> dict:
    """Die Anweisungszeilen, sofern alle vier brauchbar sind, sonst ein leeres dict.

    Alles oder nichts: mit drei von vier Zeilen haette ein gemischtes Set eine Aufgabe
    mit Modell-Anweisung und drei mit Schablone, und die eine faellt aus dem Ton. Leer
    heisst, die alte Schablone greift, so wie vor diesem Feld.
    """
    if not isinstance(lines, dict):
        return {}
    fertig = {}
    for kind in TASK_KINDS:
        text = (lines.get(kind) or "").strip()
        # Eine leere oder ein-Wort-Anweisung ist keine. Der Themenname allein reicht
        # nicht, der steht ohnehin schon ueber dem Set.
        if not text or len(text.split()) < 3:
            return {}
        fertig[kind] = text
    return fertig


# Ein Themenname und kein Satz. Länger heisst, das Modell hat die Frage nicht
# verstanden, und ein Absatz auf einer Kachel wäre schlimmer als kein Vorschlag.
MAX_LABEL_CHARS = 60


def usable_label(value) -> str:
    """Der Namensvorschlag, oder leer.

    Leer ist kein Fehler und keine Absage. Der Vorschlag ist Komfort: er sagt dem
    Dozenten, welche Form das Modell aus seinem getippten Namen gemacht hat. Ein
    Thema ohne ihn wird angelegt wie vor diesem Feld.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or len(text) > MAX_LABEL_CHARS or len(text.splitlines()) > 1:
        return ""
    return text


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
