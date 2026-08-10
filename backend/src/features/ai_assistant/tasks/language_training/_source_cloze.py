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
    '"example": {"gapped": "One short DEMO sentence with ___ where a word is missing, '
    'about DIFFERENT material than the passage below", '
    '"solved": "the same demo sentence with the gap correctly filled in"}, '
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
    # Gemessen an Satz 7043 (BewG85.pdf): das Modell schrieb die Grundform in Klammern
    # direkt hinter jeden Platzhalter, bei 10 von 10 Luecken, und loeste die Aufgabe damit
    # selbst. Die Beispiel-Konvention ("gapped"/"solved") war ins Passagen-Feld gewandert,
    # obwohl die alte Regel schon "never write a solution somewhere else" verlangte -- aus
    # Modellsicht ist eine Klammer ein Hinweis, keine zweite Nennung. Diese Regel benennt
    # die Klammer ausdruecklich, und _strip_answer_hints raeumt weiter unten auf, was
    # trotzdem durchrutscht.
    "- At each gap, the passage contains ONLY the placeholder, nothing beside it: no "
    "parenthesis, no bracket, no hint, no base form, no translation, no synonym next to "
    "its own gap. The chips shown below the text are the ONLY place a base form appears.\n"
    "- Never use the same base word twice.\n"
    "- Never write a solution somewhere else in the passage, that gives it away.\n"
    "- 'base' is always the plain dictionary form, that is what the learner sees.\n"
    "- The instruction must say that some words keep their form and others do not.\n"
    "- The example must be about different material than the passage.\n"
)


def _min_inflected(count: int) -> int:
    """Wie viele der bestellten Lücken mindestens eine geänderte Form brauchen.

    Rund ein Drittel, mindestens eine, nie alle. Die Zahl allein STEUERT das Modell
    nicht zuverlässig, sie sagt nur, wie viele Lücken es TREFFEN soll -- gemessen an
    Satz 7044 (BRAO91.pdf): 0 von 10 Lücken änderten die Form, obwohl der Prompt schon
    "At least 3 of the 10 gaps" verlangte (vorher, nur mit der Absicht "mix the forms"
    und ohne Zahl, war es bei Satz 7043 1 von 10 -- die Zahl allein machte es also nicht
    besser). Der Grund: ob sich eine Form überhaupt ändert, entscheiden WORTART und
    SATZSTELLE, die das Modell selbst wählt, nicht diese Zahl. Acht von zehn Lücken in
    Satz 7044 waren Nomen im Nominativ/Akkusativ von Femininum/Neutrum (dort ändert
    sich im Deutschen sichtbar nichts), die beiden Verben standen direkt nach einem
    Modalverb (dort ist der Infinitiv schon die Grundform) -- das Modell konnte die
    Zahl nur durch Zufall erfüllen, weil es beim Bau des Satzes zufällig Stellen traf,
    die gar keine Änderung verlangen. Die Zahl bleibt (dieser Wert), wirkt aber erst
    zusammen mit :func:`_mix_rule`, die dem Modell jetzt sagt, WELCHE Wortart und
    WELCHE Satzstelle eine Änderung überhaupt erzwingt.
    """
    bestellt = max(1, count)
    if bestellt == 1:
        return 1
    ziel = max(1, round(bestellt / 3))
    return min(ziel, bestellt - 1)  # nie alle, sonst bleibt keine unveraenderte Luecke


def _mix_rule(count: int) -> str:
    """Prompt-Zeilen für die Formen-Mischung: die Zahl UND die Satzstelle, die sie
    überhaupt erst erzwingt.

    Die Zahl allein reicht nicht (siehe :func:`_min_inflected`): ein Nomen im
    Nominativ/Akkusativ von Femininum/Neutrum oder ein Verb direkt nach einem
    Modalverb erfüllt die Zahl nie, egal wie oft man sie verlangt, weil sich an
    solchen Stellen im Deutschen nichts sichtbar ändert. Die Regeln unten nennen
    deshalb WELCHE Wortart und WELCHE Position eine Änderung erzwingt, in
    grammatischen Kategorien statt an deutschen Beispielen, damit der Prompt auch
    für die anderen Ausgabesprachen trägt. Ausserdem: 8 von 10 Lücken in Satz 7044
    waren Nomen, eine einzige Wortart lässt sich zu leicht auf eine Stelle ohne
    sichtbaren Unterschied schieben, deshalb die Mischungs-Regel am Ende.
    """
    bestellt = max(1, count)
    n = _min_inflected(bestellt)
    zeile = (
        f"- At least {n} of the {bestellt} gaps must need a form DIFFERENT from the "
        "dictionary form (a different ending, tense, case, or number) to be correct. "
        "A gap whose dictionary form already fits the sentence unchanged does NOT "
        "count towards this number, whichever word it is. Build the SENTENCE around a "
        "slot that FORCES the change, never pick a term first and hope the sentence "
        "happens to need a different form.\n"
        "- Slots that force a change: a verb the sentence needs to agree with its "
        "subject (never right after a modal verb, never a bare infinitive); an "
        "adjective placed directly in front of the noun it describes (it takes an "
        "ending there); a noun the sentence needs in the plural while its dictionary "
        "form is singular; a noun in a grammatical case that visibly changes its "
        "written form.\n"
    )
    # Bei genau einer Luecke widerspricht "nicht alle dieselbe Wortart" der Zeile
    # darueber ("At least 1 of the 1 gaps"): mit einer einzigen Luecke gibt es keine
    # Mischung, die Vorgabe waere unerfuellbar. Erreichbar, wenn ein Lernkarten-Set
    # nur ein einziges brauchbares Wort beisteuert (siehe run_cloze_set).
    if bestellt > 1:
        zeile += (
            "- The gaps must not all be the same part of speech. Mix nouns, verbs, and "
            "adjectives across the gaps.\n"
            "- At least one gap must keep the dictionary form completely unchanged. "
            "Copying the same word into every gap fails this exercise just as much as "
            "changing it in every gap.\n"
        )
    return zeile


def placeholders(text: str) -> list[int]:
    """Die Platzhalter-Nummern in der Reihenfolge, in der sie im Text stehen."""
    return [int(m.group(1)) for m in _PLACEHOLDER_RE.finditer(text or "")]


# Eine Klammer direkt hinter einem Platzhalter, mit wenig Inhalt. Die Längengrenze
# haelt die Suche schnell und verhindert, dass eine ganz andere Klammer weiter hinten
# im Satz aus Versehen mitgenommen wird.
_GAP_HINT_RE = re.compile(r"(\{\{(\d+)\}\})[ \t]*\(([^)]{1,80})\)")


def _strip_answer_hints(text: str, gaps: list) -> str:
    """Entfernt eine Klammer direkt nach einem Platzhalter, wenn ihr Inhalt die
    Grundform oder die Lösung genau dieser Lücke ist.

    Gemessen an Satz 7043 (BewG85.pdf, 10 von 10 Lücken betroffen): das Modell übernahm
    die Klammer-Konvention aus dem Beispielfeld in den FLIESSTEXT, "{{1}} (gemeiner
    Wert)" verriet die Lösung direkt neben ihrer eigenen Lücke, die Chips darunter
    wurden überflüssig. Die Prompt-Regel allein reicht nicht zuverlässig, deshalb räumt
    der Code auf, was das Modell trotzdem schreibt.

    Läuft VOR der Platzhalter-Buchführung in :func:`clean_gaps`, damit die Nummerierung
    den bereinigten Text sieht und nicht die Klammer mitzählt. Eine Klammer, deren
    Inhalt zu keiner der beiden Fassungen passt, ist gewöhnliche Prosa und bleibt stehen,
    zum Beispiel ein Verweis wie "(siehe Anlage 3)".
    """
    if not text or not gaps:
        return text

    def ersetze(m: re.Match) -> str:
        platzhalter, nummer_text, inhalt = m.group(1), m.group(2), m.group(3)
        nummer = int(nummer_text)
        if not (1 <= nummer <= len(gaps)):
            return m.group(0)
        gap = gaps[nummer - 1]
        if not isinstance(gap, dict):
            return m.group(0)
        verraten = {normalize(gap.get("base") or ""), normalize(gap.get("solution") or "")}
        verraten.discard("")
        if verraten and normalize(inhalt) in verraten:
            return platzhalter
        return m.group(0)

    return _GAP_HINT_RE.sub(ersetze, text)


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
    return kopf + auftrag + _SHAPE + _RULES + _mix_rule(count) + PAGE_RULE


def generate_cloze_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    words: list[str] | None = None,
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

    # Erst die verratenen Klammern raus, DANN die Platzhalter-Buchführung -- sonst
    # zaehlte clean_gaps eine Klammer mit, die gleich wieder verschwindet.
    roh_text = _strip_answer_hints(data.get("text"), data.get("gaps"))
    text, gaps = clean_gaps(roh_text, data.get("gaps"), words)
    bestellt = max(1, count)
    if not gaps or len(gaps) < bestellt * _MIN_USABLE_RATIO:
        logger.warning("KI Tutor: Lückentext hatte nur {} von {} brauchbaren Lücken",
                       len(gaps), bestellt)
        return None

    # Der Titel wird VOR dem Item bestimmt, weil er selbst mit in extras wandert.
    # Ohne das traegt eine Vorratszeile keinen Titel: ein Satz aus dem Vorrat wird
    # nie ueber generate_cloze_from_source finalisiert (siehe run_cloze_set), sein
    # Titel kaeme sonst nur aus der noch nicht fertigen Satz-Zeile, und die traegt an
    # dieser Stelle immer den Platzhalter "Wird generiert...".
    title = (data.get("title") or "").strip() or ctx.multi_label

    beispiel = data.get("example") or {}
    item = {
        "front": text,
        "back": _solved(text, gaps),
        # Anweisung, Beispiel und Titel stehen HIER und nicht in den Set-Spalten
        # instruction/pattern_*/title, die die Grammatik-Übung bzw. die Satz-Zeile
        # benutzen. Der Vorrat trägt Aufgaben und keine Set-Spalten: ein Text aus dem
        # Vorrat käme sonst ohne Anweisung und ohne eigenen Titel an.
        "extras": {
            "gaps": gaps,
            "instruction": (data.get("instruction") or "").strip(),
            "example": {"gapped": (beispiel.get("gapped") or "").strip(),
                        "solved": (beispiel.get("solved") or "").strip()},
            "title": title,
        },
        # Mit Unterstrich, weil _attribution.py genau dieses Feld liest (_cited_chip
        # prüft item.get("_page")). Ohne ihn griffe die erste Stufe der Zuordnung nie,
        # jeder Lauf zahlte die Suche, obwohl das Modell die Seite schon genannt hat.
        "_page": data.get("page"),
        # Bei diesem Werkzeug ist die Luecken-Zahl eine Eigenschaft der ZEILE und nicht
        # die Zahl der geholten Zeilen (die bleibt bei einem Text immer 1). _kind traegt
        # sie in den Vorrat (siehe exercise_pool.py), damit eine spaetere Anfrage gezielt
        # nach einem Text mit GENAU der bestellten Luecken-Zahl fragen kann (run_cloze_set
        # unten), statt irgendeinen gespeicherten Text zu bekommen, egal wie viele
        # Luecken er traegt. Wird vor dem Speichern des Satzes wieder entfernt.
        "_kind": str(len(gaps)),
    }
    # Ein Text, ein Satz Quellen-Chips. Der Lückentext ist aus dem Material NEU
    # geschrieben und findet sich deshalb oft nicht wörtlich wieder, darum die
    # gestaffelte Zuordnung: erst die Seite, die das Modell selbst genannt hat (kostenlos,
    # kein Suchaufruf), dann die Suche, dann wenigstens die Datei. attach_chips_cited
    # entfernt _page nach dem Lesen selbst, hier bleibt nichts mehr aufzuräumen.
    attach_chips_cited([item], [item["back"]], ctx)

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
                  language, adaptive_suffix, uuids) -> None:
    """Einen Lückentext-Satz fertigstellen: Vorrat, sonst erzeugen, dann speichern.

    Steht hier und nicht im Verteiler, damit der Verteiler nicht um einen zweiten
    Ablauf wächst. Er behält eine Verzweigung, den Rest trägt dieses Modul.

    Kein ``locale``-Parameter: die anderen Erzeuger brauchen es fuer feste
    de/en-Beschriftungen (Richtig/Falsch, Aufgaben-Zeilen), dieser Lückentext hat
    keine -- Anweisung, Beispiel und Titel schreibt das Modell selbst in `language`,
    Python haelt dafuer kein eigenes Woerterbuch. Ein ungenutzter Parameter waere
    hier nur eine zweite Kopie desselben Fehlers, den diese Aenderung gerade behebt.
    """
    from src import database as db
    from src.features.ai_assistant.tasks.language_training._context import build_source_context
    from src.features.ai_assistant.tasks.language_training._pool import (
        pool_level, store as store_in_pool, take as take_from_pool, uses_pool,
    )
    from src.features.ai_assistant.tasks.language_training._variation import (
        build_title_avoidance_block,
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
        # Die bestellte Anzahl ist bei diesem Werkzeug eine Eigenschaft der ZEILE und
        # nicht die Zahl der geholten Zeilen (die bleibt immer 1). Ohne "kinds" gaebe
        # der Vorrat irgendeinen gespeicherten Text zurueck, egal wie viele Luecken er
        # traegt -- ein Lernender, der 5 Luecken bestellt, bekaeme still einen
        # gespeicherten 15-Luecken-Text. kinds filtert auf die Luecken-Zahl, die
        # generate_cloze_from_source unter _kind einlagert.
        aus_vorrat = take_from_pool(uuids, "wortschatz", level, user_id, 1,
                                    kinds=[str(count)])
        if aus_vorrat:
            logger.info("KI Tutor: Satz {} nimmt seinen Text aus dem Vorrat", set_id)
            # Der Titel steht in extras.title (siehe generate_cloze_from_source), denn
            # ex_set traegt an dieser Stelle immer noch den Platzhalter "Wird
            # generiert...": diese Zeile wird erst hier zum ersten Mal fertiggestellt.
            # Eine Vorratszeile von vor dieser Aenderung hat noch keinen Titel in
            # extras, deshalb der Rueckfall.
            titel = (aus_vorrat[0].get("extras") or {}).get("title") or "Lückentext"
            db.finalize_exercise_set(set_id, titel, aus_vorrat)
            return

    # Kein count= hier: build_source_context traegt die Zahl nur in die
    # Abschnitts-Kopfzeile als Quote je Abschnitt (siehe per_section_quota in
    # _context.py). Bei zwei oder mehr Quellen wuerde diese Quote verlangen, "mindestens
    # Q Eintraege" aus jedem Abschnitt zu nehmen -- ein Begriff, den der Lückentext-Prompt
    # gar nicht kennt (er kennt Lücken, keine "Eintraege"), und der dem einen
    # zusammenhaengenden Text widerspricht, den generate_cloze_from_source bauen soll:
    # verteilt ueber mehrere Abschnitte zerlegte er den Text in ein Patchwork.
    # generate_cloze_from_source bekommt die bestellte Zahl ohnehin direkt als eigenes
    # Argument, dafuer braucht es die Kopfzeile nicht.
    ctx = build_source_context(uuids, "wortschatz")
    if ctx is None:
        db.fail_exercise_set(set_id)
        return
    # Ohne diesen Block bekaeme ein zweites Set aus demselben Dokument leicht denselben
    # Titel: die anderen Werkzeuge lesen ihn schon, der Lückentext tat es bisher nicht.
    title_avoidance = build_title_avoidance_block(ex_set.get("workspace_id"), "wortschatz")
    result = generate_cloze_from_source(
        client, model, ctx, count, words=words, language=language,
        adaptive_suffix=adaptive_suffix, title_avoidance=title_avoidance,
    )
    if result is None:
        db.fail_exercise_set(set_id)
        return
    items, title = result
    if uses_pool(tool="wortschatz", mode=mode):
        store_in_pool(items, ctx, "wortschatz", level)
    # _kind hat seinen Zweck erfuellt, sobald der Vorrat ihn gesehen hat (oder, ausserhalb
    # des Vorrats, gar nicht gebraucht wurde). Im gespeicherten Satz hat er nichts
    # verloren, dort traegt die Aufgabe ihre Anweisung schon selbst (dieselbe Regel wie
    # bei der Grammatik-Uebung, siehe _plan.py).
    for item in items:
        item.pop("_kind", None)
    # Kein header=: Anweisung und Beispiel hängen in extras an der Aufgabe, damit
    # sie den Vorrat überleben.
    db.finalize_exercise_set(set_id, title, items)


__all__ = ["clean_gaps", "generate_cloze_from_source", "placeholders",
           "run_cloze_set", "usable_flashcard_set"]
