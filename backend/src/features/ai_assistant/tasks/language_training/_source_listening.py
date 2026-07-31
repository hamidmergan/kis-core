"""Hörverstehen aus Ton- und Bildquellen (mode='source').

Das Werkzeug stellt drei Fragearten in einem Satz: Verständnisfragen, Lückensätze
und Richtig/Falsch-Aussagen, alle zum Ankreuzen. Es ist bewusst ein eigenes
Werkzeug und keine vierte Frageart im Quiz: das Quiz arbeitet auf allem, was
ausgewählt ist, hier zählen nur Transkripte von Audio und Video (die Auswahl wird
in der Route gefiltert).

Die Regeln für die Richtig/Falsch-Aussagen stammen aus der Testkonstruktion. Ohne
sie ist dieser Aufgabentyp ohne Zuhören lösbar: Absolutwörter wie "immer" sind fast
immer falsch, Weichmacher wie "in der Regel" fast immer richtig, wörtlich übernommene
Sätze prüfen Wiedererkennung statt Verstehen, und ein Modell ohne Vorgabe schreibt
fast nur wahre Sätze.
"""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items


# Feste Beschriftung statt einer vom Modell erfundenen: es schrieb sonst mal "Wahr",
# mal "richtig", und die Ansicht zeigt die Optionen unverändert an. Die Reihenfolge
# ist ebenfalls fest, deshalb mischt die Ansicht Zwei-Options-Items nicht.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

_SOURCE_RULE = (
    "- For every item, include source_label and page_number, the source/timestamp the "
    "content came from.\n"
)
_PERSONAL_RULE = (
    "IMPORTANT:\n- Do NOT use personal names in questions. Instead of 'laut Prof. X', write "
    "'laut Quelle' (German) or 'according to the source' (English), matching the output "
    "language.\n"
)
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation marks, "
    "never a filename.\n"
)
# Die Regeln gelten nur für die Aussagen, nicht für Fragen und Lücken: dort sind
# die Optionen sichtbar, hier entscheidet der Satz allein.
_TRUE_FALSE_RULES = (
    "\nRULES FOR THE statement ITEMS (an item that breaks one of these can be solved "
    "without having listened):\n"
    "- About half of the statements must be false. Do not follow a pattern.\n"
    "- One statement, one idea. Short and unambiguous.\n"
    "- Never use absolute words (always, never, all, none, nobody) and never use hedges "
    "(usually, mostly, as a rule). Both give the answer away.\n"
    "- No negation inside the statement.\n"
    "- Never copy the source verbatim, always paraphrase it.\n"
    "- Make a statement false by changing exactly one detail: a number, a person, a role, a "
    "time, a direction, or a cause. Never invent something the source does not mention at all, "
    "that is too easy to spot.\n"
    "- True and false statements must be about the same length.\n"
    "- Every statement must be decidable from the source alone, never from general knowledge.\n"
)


def generate_listening_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    language = _language_label(locale)
    tool_prompt = _build_prompt(count, language) + adaptive_suffix + title_avoidance + coverage
    messages = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\nSources:\n\n{ctx.context}"},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)
    if isinstance(data, dict):
        exercises = data.get("exercises") or []
        json_title = (data.get("title") or "").strip()
    else:
        exercises = data
        json_title = ""
    exercises = list(exercises)[:count]

    items, claims = _build_items(exercises, locale)

    # Post-hoc-Attribution wie im Quiz: nav-only, kein Highlight. Bei Medienquellen
    # landet der Chip auf dem Zeitstempel, eine falsche Aussage zeigt also auf die
    # Stelle, an der die richtige Fassung zu hören ist.
    attach_chips(items, claims, ctx, multi=False)

    title = json_title or title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _verdict_labels(locale: str) -> tuple[str, str]:
    return _VERDICT_LABELS["en" if (locale or "").lower().startswith("en") else "de"]


def _build_prompt(count: int, language: str) -> str:
    base = (
        f"You create listening-comprehension exercises. The sources are transcripts of audio "
        f"or video recordings, so ask about what is actually said in them. "
        f"Write ALL questions, statements, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} "
        f"if needed.\n\n"
    )
    title_rule = _TITLE_RULE.replace("{language}", language)
    return base + (
        "Use all three kinds of item, roughly one third each:\n"
        "- a comprehension question that tests understanding of the content;\n"
        "- a gap sentence: a statement from the recording with one key term replaced by ___;\n"
        "- a statement the learner marks as true or false.\n\n"
        "Respond ONLY with a JSON object. A comprehension item uses \"question\", a gap item "
        "uses \"sentence\" with ___ in it, both with their own options. A true/false item uses "
        "\"statement\" plus \"answer\" (JSON true or false) and brings no options:\n"
        '{"title": "Short topic title", "exercises": ['
        '{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, "source_label": "VL1.mp4", "page_number": "3:20"}, '
        '{"sentence": "Statement with ___ as a gap.", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 2, "source_label": "VL1.mp4", "page_number": "7:05"}, '
        '{"statement": "A claim about the recording.", "answer": false, '
        '"source_label": "VL1.mp4", "page_number": "9:40"}]}\n'
        + _TRUE_FALSE_RULES + _PERSONAL_RULE + _SOURCE_RULE + title_rule +
        f"Create exactly {count} exercises. Mix easy and hard ones."
    )


def _build_items(exercises: list[dict], locale: str) -> tuple[list[dict], list[str]]:
    """Item-Zeilen und der Claim-Text für die Quellenzuordnung.

    Alle drei Fragearten teilen sich eine Form: Aufgabentext in ``front``, richtige
    Option in ``back``, dazu ``options`` und ``correct_idx``. Die Ansicht unterscheidet
    sie an der Anzahl der Optionen und am Lückenzeichen, nicht an einem eigenen Feld.

    Der Claim einer Aussage ist die Aussage selbst. Bei den anderen Arten kommt die
    richtige Option dazu, hier wäre das nur das Wort "Richtig" und damit als Suchtext
    wertlos.
    """
    yes, no = _verdict_labels(locale)
    items, claims = [], []
    for ex in exercises:
        statement = (ex.get("statement") or "").strip()
        if statement:
            verdict = ex.get("answer")
            if not isinstance(verdict, bool):
                continue
            prompt_text, options = statement, [yes, no]
            idx = 0 if verdict else 1
            claim = statement
        else:
            prompt_text = (ex.get("question") or ex.get("sentence") or "").strip()
            options = ex.get("options") or []
            idx = ex.get("correct_idx")
            if not prompt_text or not options or idx is None or not (0 <= idx < len(options)):
                continue
            claim = f"{prompt_text} {options[idx]}".strip()
        items.append({
            "front": prompt_text,
            "back": options[idx],
            "options": options,
            "correct_idx": idx,
            # Welchen nummerierten Abschnitt das Modell benutzt hat. Wird nicht
            # gespeichert, finalize_exercise_set liest nur bekannte Schlüssel.
            "_section": ex.get("section"),
        })
        claims.append(claim)
    return items, claims
