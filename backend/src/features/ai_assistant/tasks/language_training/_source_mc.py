"""Quiz aus Quelltext (mode='source').

Das Quiz stellt drei Aufgabenarten in einem Satz: Verständnisfragen und Lückensätze,
beide mit vier Auswahloptionen, und Aussagen mit Richtig oder Falsch.

Das eigenständige Lückentext-Werkzeug ist deshalb entfallen, es war dieselbe Aufgabe
unter einem eigenen Namen und stand zudem im Sprachbereich, obwohl die Lücke ein
Fachbegriff ist und kein Grammatikthema.

Richtig/Falsch kam am 2026-08-10 dazu. Es war bis dahin die einzige Form des Werkzeugs
Hörverstehen, das an diesem Tag abgeschafft wurde. Die Form zieht damit hierher um, statt
ersatzlos wegzufallen. Mitgekommen sind die Regeln aus der Testkonstruktion und die zwei
Musteraufgaben, beide am echten Lauf nachgemessen. Nicht mitgekommen sind die zwei
Verbote, die dort den Unterschied zum Quiz sicherten (keine Definitionen, keine
Wortbedeutungen): sie verbieten genau das, was das Quiz will.
"""

import json

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize
from src.tool_prompts import AIA_HINT_RULE

from src.features.ai_assistant.tasks.language_training._attribution import (
    attach_chips,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._hint import attach_hint
from src.features.ai_assistant.tasks.language_training._title import title_from_items
from src.services.llm_context_healing import create_with_shrink


_SOURCE_RULE = (
    "- For every question, include source_label and page_number, the source/page the content came from.\n"
)
_PERSONAL_RULE = (
    "IMPORTANT:\n- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Quelle' (German) or 'according to the source' (English), matching the output language.\n"
)
# The title ships with the generation response so no extra LLM call is needed for it
# (that call used to come back empty on reasoning models and left the raw filename behind).
_TITLE_RULE = (
    "- title: a short, concrete topic title in {language} (max 6 words), no quotation marks, "
    "never a filename.\n"
)

# Feste Beschriftung statt einer vom Modell erfundenen: es schrieb sonst mal "Wahr",
# mal "richtig", und die Ansicht zeigt die Optionen unverändert an.
_VERDICT_LABELS = {"de": ("Richtig", "Falsch"), "en": ("True", "False")}

# Zwei Musteraufgaben, eine wahre und eine falsche Aussage. Sie stehen HINTER dem
# Quellmaterial, siehe _build_user, und werden in _true_false_item gesperrt, damit sie
# nicht als Aufgabe 1 abgeschrieben werden.
_EXAMPLE_ITEMS = (
    ("Bei sinkender Temperatur arbeitet die Anlage weniger wirtschaftlich.", True),
    ("Die Leistungszahl steigt, wenn es draußen kälter wird.", False),
)

# Aus denselben Sätzen abgeleitet, damit Beispiel und Sperre nicht auseinanderlaufen
# können.
_EXAMPLE_MARKERS = frozenset(normalize(satz) for satz, _ in _EXAMPLE_ITEMS)


def _verdict_labels(locale: str) -> tuple[str, str]:
    return _VERDICT_LABELS["en" if (locale or "").lower().startswith("en") else "de"]


# Regeln aus der Testkonstruktion. Ohne sie ist die Aufgabe ohne die Quelle lösbar:
# Absolutwörter wie "immer" sind fast immer falsch, Weichmacher wie "in der Regel" fast
# immer richtig, wörtlich übernommene Sätze prüfen Wiedererkennung statt Verstehen, und
# ein Modell ohne Vorgabe schreibt fast nur wahre Sätze.
_TRUE_FALSE_RULES = (
    "\nRULES FOR THE TRUE/FALSE STATEMENTS (a statement that breaks one of these can be "
    "marked right without having read the source):\n"
    "- About half of the statements must be false. Do not follow a pattern.\n"
    "- One statement, one idea. Short and unambiguous.\n"
    "- Never use absolute words (always, never, all, none, nobody) and never use hedges "
    "(usually, mostly, as a rule). Both give the answer away.\n"
    "- No negation inside the statement.\n"
    "- Never copy the source verbatim, always say it in your own words.\n"
    "- Make a statement false by changing exactly one detail: a number, a person, a role, "
    "a time, a direction, or a cause. Never invent something the source does not mention "
    "at all, that is too easy to spot.\n"
    "- True and false statements must be about the same length.\n"
)

# Die Musteraufgaben, wie sie hinter dem Quellmaterial stehen.
_EXAMPLE_BLOCK = (
    "\nTwo examples of the SHAPE of a true/false item. They are about different material,\n"
    "never reuse their wording or their content:\n\n"
    + "\n".join(json.dumps({"statement": satz, "answer": urteil}, ensure_ascii=False)
                for satz, urteil in _EXAMPLE_ITEMS)
    + "\n"
)


def _split_counts(count: int) -> tuple[int, int, int]:
    """Wie viele Aufgaben je Art bestellt werden: Verständnis, Lücke, Richtig/Falsch.

    Gezählte Vorgabe und keine Absichtserklärung. Die alte Zeile "use BOTH kinds, roughly
    half and half" ist genau so eine Absichtserklärung, und beim Grammatik-Quiz war
    gemessen der Unterschied zwischen "vary the forms" und "mindestens drei verschiedene"
    der zwischen zehnmal derselben Form und zehn verschiedenen.

    Der Rest geht der Reihe nach an die Ankreuz-Arten. Ein sehr kleiner Satz hat damit
    keine Richtig/Falsch-Aufgabe, und das ist richtig so: das Quiz ist schwerpunktmässig
    eine Ankreuz-Übung.
    """
    base, rest = divmod(count, 3)
    return (base + (1 if rest > 0 else 0),
            base + (1 if rest > 1 else 0),
            base)


def generate_mc_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    # adaptive_suffix pitches questions/options at the learner's CEFR level; it
    # explicitly must not change the item count, the options or the correct answer.
    tool_prompt = _build_prompt(count, language) + adaptive_suffix + title_avoidance + coverage
    # No "already exists, avoid these" block: feeding the old questions back made the model
    # COPY them verbatim (it even reproduced a "laut Seite 7" question for a page no longer in
    # context). Variation comes instead from the context sweep in build_source_context,
    # with _dedup dropping anything that repeats an earlier set regardless.
    # The TITLE is the exception (title_avoidance): one short string, no few-shot pull.
    messages = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": _build_user(ctx, language)},
    ]
    # 0.6 (not 0.3): a little sampling diversity for wording. The real variation comes from the
    # context sweep in build_source_context (a different window per run). Still JSON-safe.
    response = create_with_shrink(client, model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)
    # Preferred shape is {"title": ..., "exercises": [...]} so the title comes free with the
    # generation call. A bare array (older/simpler models) still works, then the title is
    # derived afterwards from the items.
    if isinstance(data, dict):
        exercises = data.get("exercises") or []
        json_title = (data.get("title") or "").strip()
    else:
        exercises = data
        json_title = ""
    exercises = list(exercises)[:count]

    items, claims = _build_items(exercises, locale)

    # Post-hoc attribution (same pgvector gate as chat): each item cites where its
    # answer actually appears, nav-only, no highlight.
    _attach_by_kind(items, claims, ctx)

    title = json_title or title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _attach_by_kind(items: list[dict], claims: list[str], ctx: QuelleContext) -> None:
    """Zwei Zuordnungsläufe, einer je Aufgabenart.

    Die zwei Ankreuz-Arten wiederholen die Formulierung der Quelle, für sie ist die reine
    Suche richtig: sie findet den Satz, und ein Fehlschlag heisst ehrlich "steht so nicht
    in den Quellen". Eine Richtig/Falsch-Aussage ist dagegen per Regel immer umformuliert
    und findet sich oft nicht wieder. Für sie gilt dieselbe gestaffelte Zuordnung wie in
    der Grammatik-Übung: erst die Seite, die das Modell selbst genannt hat, dann die
    Suche, dann wenigstens die Datei.
    """
    tf_items, tf_claims, mc_items, mc_claims = [], [], [], []
    for item, claim in zip(items, claims):
        ziel_items, ziel_claims = ((tf_items, tf_claims) if item.pop("_tf", False)
                                   else (mc_items, mc_claims))
        ziel_items.append(item)
        ziel_claims.append(claim)
    if mc_items:
        # multi=False: eine Ankreuz-Antwort hat einen Ursprung und nicht "jede Seite, auf
        # der das Wort vorkommt". Die vom Modell genannte Datei und Seite werden hier
        # bewusst ignoriert, die Zuordnung entscheidet über die Seite.
        attach_chips(mc_items, mc_claims, ctx, multi=False)
    if tf_items:
        attach_chips_cited(tf_items, tf_claims, ctx)


def _build_prompt(count: int, language: str) -> str:
    n_frage, n_luecke, n_tf = _split_counts(count)
    base = (
        f"You create exercises based on the given source text. "
        f"Write ALL questions, sentences, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    )
    title_rule = _TITLE_RULE.replace("{language}", language)
    return base + (
        "Create exercises for the given text. There are THREE kinds:\n"
        "- a comprehension question that tests understanding of the content, with four "
        "options;\n"
        "- a gap sentence: a statement from the text with one key term replaced by ___, "
        "with four options;\n"
        "- a true/false statement about the content, with no options at all.\n\n"
        "Respond ONLY with a JSON object. A comprehension item uses \"question\", a gap "
        "item uses \"sentence\", both with \"options\" and \"correct_idx\". A true/false "
        "item uses \"statement\" plus \"answer\", which is JSON true or false and nothing "
        "else, and it never carries options. EVERY item carries a \"tip\":\n"
        '{"title": "Short topic title", "exercises": ['
        '{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, "tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 5}, '
        '{"sentence": "Statement with ___ as a gap.", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 2, "tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 7}, '
        '{"statement": "A claim about the content.", "answer": false, '
        '"tip": "A nudge that does not give it away.", '
        '"source_label": "Filename.pdf", "page_number": 9}]}\n'
        + _TRUE_FALSE_RULES
        + _PERSONAL_RULE + _SOURCE_RULE + title_rule
        + AIA_HINT_RULE.replace("{language}", language) +
        f"Create exactly {n_frage} comprehension questions, {n_luecke} gap sentences and "
        f"{n_tf} true/false statements, {count} exercises in total. Mix easy and hard ones."
    )


def _build_user(ctx: QuelleContext, language: str) -> str:
    """Quellmaterial zuerst, Musterbeispiele dahinter.

    Die Reihenfolge ist nicht Geschmack: ein Beispiel im System-Prompt wurde auf
    Fachquellen als Aufgabe 1 abgeschrieben, hinter dem Material wirkt es als Form.
    """
    return (f"Write the output in {language}.\n\nSources:\n\n{ctx.context}\n\n"
            f"{_EXAMPLE_BLOCK}")


def _build_items(exercises: list[dict], locale: str) -> tuple[list[dict], list[str]]:
    """Item-Zeilen + der Suchtext, über den die Quellen-Chips gesucht werden.

    Drei Arten, eine Zeilenform. Eine Lückenaufgabe trägt "sentence", eine
    Verständnisfrage "question", eine Richtig/Falsch-Aufgabe "statement". Der
    Aufgabentext landet immer in ``front``, die richtige Antwort in ``back``. Die Ansicht
    unterscheidet sie an der Anzahl der Optionen und am Lückenzeichen im Text, nicht an
    einem eigenen Feld.
    """
    items, claims = [], []
    for ex in exercises:
        if ex.get("statement") is not None or "answer" in ex:
            gebaut = _true_false_item(ex, locale)
        else:
            gebaut = _choice_item(ex)
        if gebaut is None:
            continue
        item, claim = gebaut
        # Eine Stelle für alle drei Arten: der Tipp haengt an der Aufgabe und nicht an
        # ihrer Form. Er kommt aus derselben Antwort und nicht aus einem zweiten Aufruf.
        attach_hint(item, ex)
        items.append(item)
        claims.append(claim)
    return items, claims


def _choice_item(ex: dict) -> tuple[dict, str] | None:
    """Verständnisfrage oder Lückensatz, beide mit vier Optionen."""
    prompt_text = (ex.get("question") or ex.get("sentence") or "").strip()
    options = ex.get("options") or []
    idx = ex.get("correct_idx")
    if not prompt_text or not options or idx is None or not (0 <= idx < len(options)):
        return None
    answer = options[idx]
    return {
        "front": prompt_text,
        "back": answer,
        "options": options,
        "correct_idx": idx,
        # Welchen nummerierten Kontextabschnitt das Modell benutzt haben will. Wird nicht
        # gespeichert (finalize_exercise_set liest nur bekannte Felder), der Aufrufer
        # prüft damit, ob jeder Abschnitt drankam.
        "_section": ex.get("section"),
    }, f"{prompt_text} {answer}".strip()


def _true_false_item(ex: dict, locale: str) -> tuple[dict, str] | None:
    """Eine Aussage über die Quelle, zwei Optionen. Was durchfällt, gibt None.

    Eine Aufgabe mit vier Optionen fällt hier durch, auch wenn der Prompt sie nie
    bestellt hat: das Modell liefert sie gelegentlich trotzdem, und dann stünde eine
    Ankreuzaufgabe ohne Frage im Satz.
    """
    statement = (ex.get("statement") or "").strip()
    verdict = ex.get("answer")
    options = ex.get("options") or []
    if not statement or not isinstance(verdict, bool) or (options and len(options) != 2):
        return None
    if normalize(statement) in _EXAMPLE_MARKERS:
        return None

    yes, no = _verdict_labels(locale)
    return {
        "front": statement,
        "back": yes if verdict else no,
        "options": [yes, no],
        "correct_idx": 0 if verdict else 1,
        "_section": ex.get("section"),
        # Markiert die Aufgabenart für die Zuordnung. Wird dort entfernt.
        "_tf": True,
        # Woher das Modell die Aufgabe genommen haben will. Beides wird gegen den
        # Kontext geprüft und danach entfernt.
        "_source_label": (ex.get("source_label") or "").strip(),
        "_page": ex.get("page_number"),
    # Gesucht wird über die Aussage allein und nie plus "Richtig": die feste
    # Beschriftung steht in keiner Quelle und würde die Suche verwässern.
    }, statement
