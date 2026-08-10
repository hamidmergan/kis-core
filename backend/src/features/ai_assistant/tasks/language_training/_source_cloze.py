"""Wortschatz-Lückentext aus Quelltext (tool='wortschatz').

Ein Set ist genau EINE Aufgabe: ein zusammenhängender Text mit Platzhaltern, die
Lösungen und Grundformen hängen in ``extras.gaps`` daran. Der Text entsteht aus
dem Inhalt der Quellen und nicht aus der Luft, damit das Geübte zu dem passt, was
im Kurs gelesen wird.

Die Wörter kommen entweder aus den Quellen oder aus einem Lernkarten-Set. Im
zweiten Fall steht die Kartenliste im Auftrag, und ``clean_gaps`` wirft alles
weg, was nicht darauf steht.

Es gibt so viele Chips wie Lücken. Ablenker wurden ausdrücklich verworfen: wer
aus einem Lernkarten-Set übt, will genau diese Karten üben.
"""

import json
import re

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize

from src.features.ai_assistant.tasks.language_training._attribution import (
    PAGE_RULE,
    attach_chips_cited,
)
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

# Unter diesem Anteil brauchbarer Lücken gilt der Durchlauf als misslungen. Lieber
# ein fehlgeschlagenes Set als ein Text, in dem die Hälfte der Lücken schon
# ausgefüllt dasteht. Derselbe Massstab wie in _source_grammar.py.
_MIN_USABLE_RATIO = 0.5

_SHAPE = (
    'Respond ONLY with a JSON object:\n'
    '{"title": "Short topic title", '
    '"instruction": "What the learner has to do, one or two sentences", '
    '"example": {"gapped": "A short sentence with ___ and the base form in brackets", '
    '"solved": "the word that belongs in that gap"}, '
    '"text": "A coherent passage where the target words are replaced by {{1}}, {{2}}, ...", '
    '"page": 12, '
    '"gaps": [{"base": "the dictionary form of the word", '
    '"solution": "the form that belongs in that gap"}]}\n'
)

_RULES = (
    "RULES:\n"
    "- The passage is ONE coherent text about the source content, not a list of "
    "unrelated sentences. It must read as if it came from the material.\n"
    "- Number the placeholders {{1}}, {{2}} and so on, without gaps, in the order "
    "they appear. The gaps array is in the same order.\n"
    "- Mix the forms: some gaps take the dictionary form unchanged, others need it "
    "inflected. The learner has to decide, that is the exercise.\n"
    "- Never use the same base word twice.\n"
    "- Never write a solution somewhere else in the passage, that gives it away.\n"
    "- 'base' is always the plain dictionary form, that is what the learner sees.\n"
    "- The instruction must say that some words keep their form and others do not.\n"
    "- The example must be about different material than the passage.\n"
)


def placeholders(text: str) -> list[int]:
    """Die Platzhalter-Nummern in der Reihenfolge, in der sie im Text stehen."""
    return [int(m.group(1)) for m in _PLACEHOLDER_RE.finditer(text or "")]


def _is_usable(gap, words: list[str] | None, gesehen: set[str]) -> bool:
    """Ob diese Lücke stehen bleiben darf.

    Eine Lücke ohne Lösung ist unlösbar, eine doppelte Grundform stünde zweimal
    als Chip unter dem Text, und bei Lernkarten gehört alles weg, was nicht auf
    einer Karte steht. Kein Dict ist ebenfalls unbrauchbar, nicht abstürzend: das
    Modell schreibt ``"gaps"`` gelegentlich als Liste blosser Strings statt als
    Liste von Objekten, und das ist ein misslungener Durchlauf, kein Programmfehler.
    """
    if not isinstance(gap, dict):
        return False
    base = (gap.get("base") or "").strip()
    solution = (gap.get("solution") or "").strip()
    if not base or not solution:
        return False
    schluessel = normalize(base)
    if not schluessel or schluessel in gesehen:
        return False
    if words is not None and schluessel not in {normalize(w) for w in words}:
        return False
    return True


def clean_gaps(text: str, gaps: list[dict], words: list[str] | None):
    """Unbrauchbare Lücken füllen, die brauchbaren neu durchnummerieren.

    Eine verworfene Lücke wird im Text durch ihre Lösung ersetzt statt gelöscht.
    Sonst risse ein Satz auseinander, und der Lernende bekäme einen Text, der
    mitten im Wort aufhört. Fehlt auch die Lösung, bleibt an der Stelle nichts.

    Eine Lücke zählt nur mit, wenn ihr Platzhalter auch WIRKLICH im Text steht. Sonst
    schreibt das Modell drei brauchbare Lücken, setzt aber nur zwei Platzhalter, und
    der dritte Chip haette keine Stelle im Text, an der er geuebt wird -- ein Ablenker,
    und Ablenker sind zweimal ausdruecklich verworfen worden.

    Gibt (Text, Lücken) zurück. Die Nummern laufen danach wieder lückenlos von 1, und
    es gibt nie mehr Lücken als Platzhalter im zurückgegebenen Text (und umgekehrt).
    """
    text = text or ""
    im_text = set(placeholders(text))
    gesehen: set[str] = set()
    behalten: list[dict] = []
    ersatz: dict[int, str] = {}
    for i, gap in enumerate(gaps or [], start=1):
        if i not in im_text:
            # Keine Stelle im Text, an der diese Nummer steht -- weder ein Chip noch
            # eine Ersetzung ist hier noetig, es gibt schlicht nichts zu tun.
            continue
        if _is_usable(gap, words, gesehen):
            gesehen.add(normalize(gap["base"]))
            behalten.append({"base": gap["base"].strip(),
                             "solution": gap["solution"].strip()})
            ersatz[i] = "{{%d}}" % len(behalten)
        else:
            loesung = gap.get("solution") if isinstance(gap, dict) else None
            ersatz[i] = (loesung or "").strip()
    neu = _PLACEHOLDER_RE.sub(lambda m: ersatz.get(int(m.group(1)), ""), text)
    return neu, behalten


def _solved(text: str, gaps: list[dict]) -> str:
    """Die Musterlösung: derselbe Text mit eingesetzten Lösungen."""
    return _PLACEHOLDER_RE.sub(
        lambda m: gaps[int(m.group(1)) - 1]["solution"] if 0 < int(m.group(1)) <= len(gaps) else "",
        text,
    )


def _build_prompt(count: int, language: str, words: list[str] | None) -> str:
    kopf = (
        f"You write a vocabulary gap-fill exercise from the given source text. "
        f"Write the passage, the instruction and the example in {language}, "
        f"regardless of the source-text language.\n\n"
    )
    auftrag = f"Create a passage with exactly {count} gaps.\n\n"
    if words:
        liste = ", ".join(words)
        auftrag += (
            "Use ONLY these words as the gaps, nothing else. Every gap's 'base' must "
            f"be one of them, spelled exactly as given:\n{liste}\n\n"
        )
    else:
        auftrag += (
            "Pick the words yourself: the technical terms of the source material, the "
            "ones a learner of the subject has to know.\n\n"
        )
    return kopf + auftrag + _SHAPE + _RULES + PAGE_RULE


def generate_cloze_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    words: list[str] | None = None,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
):
    """Ein Aufruf, ein Text, eine Aufgabe.

    Gibt ``(items, title)`` zurück oder ``None``, wenn nichts Brauchbares herauskam.
    ``items`` hat genau einen Eintrag.

    Es gibt kein ``coverage`` und keinen Abschnitts-Anteil wie bei den anderen
    Werkzeugen. Die Aufteilung auf alle Abschnitte zerschnitte den Text, und einer,
    der aus jedem Kapitel einen Satz nimmt, ist kein zusammenhängender Text mehr.
    """
    prompt = _build_prompt(count, language, words) + adaptive_suffix + title_avoidance
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the output in {language}.\n\n"
                                    f"Sources:\n\n{ctx.context}"},
    ]
    try:
        response = client.chat.completions.create(model=model, messages=messages,
                                                  temperature=0.6)
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except Exception as e:  # noqa: BLE001
        logger.warning("KI Tutor: Lückentext nicht lesbar: {}", e)
        return None
    if not isinstance(data, dict):
        return None
    # Falsche Form ist ein misslungener Durchlauf und kein Absturz: 'text' fehlt oder
    # ist keine Zeichenkette, oder 'gaps' ist gar keine Liste (z.B. ein einzelnes
    # Objekt statt einer Aufzaehlung). Ohne diese Pruefung wuerde re.sub weiter unten
    # bei einem Nicht-String-Text mit TypeError abstuerzen, statt None zu liefern wie
    # jeder andere schlechte Antwortpfad hier auch.
    if not isinstance(data.get("text"), str) or not isinstance(data.get("gaps"), list):
        logger.warning("KI Tutor: Lückentext-Antwort hatte die falsche Form")
        return None

    text, gaps = clean_gaps(data.get("text"), data.get("gaps"), words)
    bestellt = max(1, count)
    if not gaps or len(gaps) < bestellt * _MIN_USABLE_RATIO:
        logger.warning("KI Tutor: Lückentext hatte nur {} von {} brauchbaren Lücken",
                       len(gaps), bestellt)
        return None

    beispiel = data.get("example") or {}
    item = {
        "front": text,
        "back": _solved(text, gaps),
        # Anweisung und Beispiel stehen HIER und nicht in den Set-Spalten
        # instruction/pattern_*, die die Grammatik-Übung benutzt. Der Vorrat trägt
        # Aufgaben und keine Set-Spalten: ein Text aus dem Vorrat käme sonst ohne
        # Anweisung an, und der Lernende sähe Lücken ohne zu wissen, was zu tun ist.
        "extras": {
            "gaps": gaps,
            "instruction": (data.get("instruction") or "").strip(),
            "example": {"gapped": (beispiel.get("gapped") or "").strip(),
                        "solved": (beispiel.get("solved") or "").strip()},
        },
        # Mit Unterstrich, weil _attribution.py genau dieses Feld liest (_cited_chip
        # prüft item.get("_page")). Ohne ihn griffe die erste Stufe der Zuordnung nie,
        # jeder Lauf zahlte die Suche, obwohl das Modell die Seite schon genannt hat.
        "_page": data.get("page"),
    }
    # Ein Text, ein Satz Quellen-Chips. Der Lückentext ist aus dem Material NEU
    # geschrieben und findet sich deshalb oft nicht wörtlich wieder, darum die
    # gestaffelte Zuordnung: erst die Seite, die das Modell selbst genannt hat (kostenlos,
    # kein Suchaufruf), dann die Suche, dann wenigstens die Datei. attach_chips_cited
    # entfernt _page nach dem Lesen selbst, hier bleibt nichts mehr aufzuräumen.
    attach_chips_cited([item], [item["back"]], ctx)

    title = (data.get("title") or "").strip() or ctx.multi_label
    return [item], title


def usable_flashcard_set(ex_set: dict | None, workspace_id: int, user_id: int) -> bool:
    """Ob dieses Lernkarten-Set die Wörter für einen Lückentext liefern darf.

    Es muss existieren, diesem Kursraum und dieser Person gehören, wirklich ein
    Lernkarten-Set sein und fertig. Ein fremdes Set wäre ein Blick in die Ablage
    einer anderen Person, ein unfertiges hätte keine Karten herzugeben.

    Prüft absichtlich NICHT, ob das Set auch wirklich Karten enthält: dafür bräuchte
    es die Karten selbst und nicht nur die Satz-Zeile, und diese Funktion bleibt eine
    reine Prüfung ohne Datenbankzugriff. Ein Set ohne Karten fängt die Route separat
    ab, mit denselben ``items``, die sie ohnehin schon geladen hat.
    """
    return bool(
        ex_set
        and ex_set.get("workspace_id") == workspace_id
        and ex_set.get("user_id") == user_id
        and ex_set.get("tool") == "flashcards"
        and ex_set.get("status") == "ready"
    )


def run_cloze_set(set_id, ex_set, user_id, count, client, model,
                  locale, language, adaptive_suffix, uuids) -> None:
    """Einen Lückentext-Satz fertigstellen: Vorrat, sonst erzeugen, dann speichern.

    Steht hier und nicht im Verteiler, damit der Verteiler nicht um einen zweiten
    Ablauf wächst. Er behält eine Verzweigung, den Rest trägt dieses Modul.
    """
    from src import database as db
    from src.features.ai_assistant.tasks.language_training._context import build_source_context
    from src.features.ai_assistant.tasks.language_training._pool import (
        pool_level, store as store_in_pool, take as take_from_pool, uses_pool,
    )

    mode = ex_set.get("mode") or "source"
    if not uuids:
        db.fail_exercise_set(set_id)
        return

    # Aus Lernkarten: die Vorderseiten sind die Wortliste. Hat das Set weniger
    # Karten als bestellt, gibt es eben weniger Lücken.
    words = None
    if mode == "cards":
        karten = db.get_exercise_set_with_items(ex_set.get("flashcard_set_id"))
        if not karten or not karten.get("items"):
            db.fail_exercise_set(set_id)
            return
        words = [i["front"] for i in karten["items"] if (i.get("front") or "").strip()]
        count = min(count, len(words))
        if not words:
            # Karten mit ausschliesslich leeren Vorderseiten: syntaktisch ein Set mit
            # Eintraegen, inhaltlich keiner. Sonst liefe ``words=[]`` weiter in den
            # Erzeuger, wo eine leere Liste etwas anderes bedeutet als kein Auftrag
            # (siehe Modulkopf) und die Prüfung dort alles verwerfen wuerde.
            db.fail_exercise_set(set_id)
            return

    level = pool_level(adaptive_suffix, user_id)
    # Eine Vorratszeile ist ein GANZER Text, deshalb genau einer und nicht `count`.
    if uses_pool(tool="wortschatz", mode=mode):
        aus_vorrat = take_from_pool(uuids, "wortschatz", level, user_id, 1)
        if aus_vorrat:
            logger.info("KI Tutor: Satz {} nimmt seinen Text aus dem Vorrat", set_id)
            db.finalize_exercise_set(set_id, ex_set.get("title") or "Lückentext",
                                     aus_vorrat)
            return

    ctx = build_source_context(uuids, "wortschatz", count=count)
    if ctx is None:
        db.fail_exercise_set(set_id)
        return
    result = generate_cloze_from_source(
        client, model, ctx, count, words=words, locale=locale, language=language,
        adaptive_suffix=adaptive_suffix,
    )
    if result is None:
        db.fail_exercise_set(set_id)
        return
    items, title = result
    if uses_pool(tool="wortschatz", mode=mode):
        store_in_pool(items, ctx, "wortschatz", level)
    # Kein header=: Anweisung und Beispiel hängen in extras an der Aufgabe, damit
    # sie den Vorrat überleben.
    db.finalize_exercise_set(set_id, title, items)


__all__ = ["clean_gaps", "generate_cloze_from_source", "placeholders",
           "run_cloze_set", "usable_flashcard_set"]
