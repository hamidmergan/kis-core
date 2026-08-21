"""mode='glossary': Exercise-Items aus bereits indiziertem Glossary generieren."""

import json
import random

from loguru import logger

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.services.aia_grammar_check import normalize
from src.features.ai_assistant.prompts.language_training_prompts import (
    AIA_KARTEIKARTEN_GLOSSAR_PROMPT,
    AIA_LERNKARTEN_PROMPT,
)

from src.features.ai_assistant.tasks.language_training._source_flashcards import flashcard_extras
from src.features.ai_assistant.tasks.language_training._title import title_from_glossary_terms
from src.services.llm_context_healing import create_with_shrink


def _sources_for(e: dict) -> list[dict]:
    # Nav-only: glossary page comes from the index (authoritative), no highlight.
    return [{
        "source_label": e.get("filename", ""),
        "page_number": e.get("page_number"),
        "start_time": None,
    }]


def _terms_used(workspace_id: int, user_id: int, tool: str) -> set[str]:
    """Vergleichsformen der Begriffe, die diese Person in diesem Werkzeug schon hatte.

    ``normalize`` ist dieselbe Vergleichsform, die ``item_key`` benutzt. Sie faltet
    Gross- und Kleinschreibung, Klammereinschuebe und Satzzeichen und geht nach
    Unicode-Kategorie, gilt also in jeder Sprache.

    Ein Fehlschlag liefert die leere Menge, dann wird gezogen wie vor dieser Aenderung.
    Den Filter zu verlieren kostet eine wiederholte Karte, den Auftrag scheitern zu
    lassen kostet den ganzen Satz. Gleiche Haltung wie in ``seen_by_user``.
    """
    try:
        gehabt = db.glossary_terms_used(workspace_id, user_id, tool)
    except Exception as exc:  # noqa: BLE001 - ein Satz ohne Filter ist besser als keiner
        logger.warning("Glossar: gehabte Begriffe nicht lesbar, es wird frei gezogen: {}", exc)
        return set()
    return {schluessel for schluessel in (normalize(t) for t in gehabt) if schluessel}


def _pick_terms(glossary: list[dict], gehabt: set[str], count: int) -> list[dict]:
    """Frische Begriffe zuerst, danach mit schon benutzten auffuellen.

    Die Eindeutigkeit in der Datenbank sitzt je Quelle (``ON CONFLICT (user_id, source_id,
    lower(term_de))``), ein Kursraum hat aber mehrere Quellen. Zwei Zeilen mit derselben
    Vergleichsform sind darum moeglich, etwa "Abstract" aus einem Skript und "abstract"
    aus einer Vorlesung. Ohne Entdopplung waeren das zwei eigene Listenelemente, und
    ``random.sample`` zieht Elemente und nicht Werte, koennte also beide in denselben Satz
    ziehen. Die Liste kommt sortiert aus der Datenbank (``ORDER BY g.term_de``), darum
    gewinnt hier die erste Zeile je Vergleichsform.

    Danach ueberschneiden sich die beiden Toepfe nicht mehr, und ``random.sample`` zieht
    ohne Zuruecklegen. Ein Begriff kann also nicht zweimal im selben Satz stehen. Mehr als
    das Glossar hergibt kommt nie heraus, ein Glossar mit drei Begriffen liefert weiter
    drei Karten.

    Sind alle Begriffe verbraucht, ist ``frisch`` leer und es wird vollstaendig aus den
    benutzten gezogen. Das ist der zweite Durchlauf. Gezogen wird auch dort zufaellig und
    nicht nach Alter, so entschieden am 2026-08-12.
    """
    eindeutig: dict[str, dict] = {}
    for e in glossary:
        eindeutig.setdefault(normalize(e["term_de"]), e)
    frisch = [e for e in eindeutig.values() if normalize(e["term_de"]) not in gehabt]
    benutzt = [e for e in eindeutig.values() if normalize(e["term_de"]) in gehabt]
    gewaehlt = random.sample(frisch, min(count, len(frisch)))
    fehlt = count - len(gewaehlt)
    if fehlt > 0 and benutzt:
        gewaehlt += random.sample(benutzt, min(fehlt, len(benutzt)))
    return gewaehlt


def generate_from_glossary(
    client, model,
    workspace_id: int,
    user_id: int,
    tool: str,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
) -> tuple[list[dict], str] | None:
    """Returns (items, title) oder None wenn kein Glossary vorhanden."""
    glossary = db.get_aia_glossary_by_workspace(workspace_id, user_id)
    if not glossary:
        return None

    selected = _pick_terms(glossary, _terms_used(workspace_id, user_id, tool), count)
    items: list[dict] = []

    if tool == "flashcards":
        items = _generate_flashcards(client, model, selected, language, adaptive_suffix)
    elif tool == "karteikarten":
        items = _generate_karteikarten(client, model, selected, language, adaptive_suffix)

    title = title_from_glossary_terms(client, model, [e["term_de"] for e in selected])
    return items, title


def _plain_flashcard(e: dict) -> dict:
    """Glossary flashcard without enrichment: the plain definition (no 'term - ' prefix)."""
    return {
        "front": e["term_de"],
        "back": e["definition"],
        "back_en": e.get("term_en", ""),
        "source_label": e.get("filename", ""),
        "page_number": e.get("page_number"),
        "sources": _sources_for(e),
        # Woran diese Karte haengt. Die Auswahl beim naechsten Mal liest genau das.
        "glossary_term": e["term_de"],
    }


# Die eine Frage des Auffangnetzes, je eingestellter Sprache. Der Begriff kommt an die
# Stelle von {0}.
_FALLBACK_FRAGE = {
    "German": "Was bedeutet „{0}\"?",
    "English": "What does \"{0}\" mean?",
    "French": "Que signifie « {0} » ?",
    "Spanish": "¿Qué significa «{0}»?",
    "Italian": "Che cosa significa «{0}»?",
    "Turkish": "“{0}” ne anlama gelir?",
    "Arabic": "ما معنى “{0}”؟",
    "Russian": "Что означает «{0}»?",
}


def _fallback_karteikarte(e: dict, language: str) -> dict:
    """Karte ohne Modellaufruf: die Frage nach der Bedeutung des Begriffs.

    Nur das Auffangnetz. Sie ist auf jeder Karte gleich formuliert und deshalb langweilig,
    aber sie ist eine Frage, und eine langweilige Frage ist besser als gar keine.
    """
    frage = _FALLBACK_FRAGE.get(language, _FALLBACK_FRAGE["German"]).format(e["term_de"])
    return {
        "front": frage,
        "back": e["definition"],
        "source_label": e.get("filename", ""),
        "page_number": e.get("page_number"),
        "sources": _sources_for(e),
        "glossary_term": e["term_de"],
    }


def _generate_karteikarten(client, model, selected: list[dict], language: str,
                           adaptive_suffix: str = "") -> list[dict]:
    """Aus Glossarbegriffen echte Frage-Antwort-Karten machen.

    Bis 2026-08-09 stand hier der Begriff selbst als Vorderseite und die Definition als
    Rueckseite, ohne jeden Modellaufruf. Die Ansicht schreibt aber "FRAGE" darueber, und
    "Literaturrecherche" ist keine Frage. Gemessen: 9 von 10 Karten aus dem Glossar hatten
    eine Vorderseite ohne Frage, aus Quellen erzeugte 0 von 34.

    Ein gebuendelter Aufruf fuer den ganzen Satz. Faellt er aus oder fehlt ein Begriff,
    greift die feste Formulierung; ein Satz entsteht also in jedem Fall.
    """
    fallback = [_fallback_karteikarte(e, language) for e in selected]
    try:
        eintraege = "\n".join(
            f"- {e['term_de']}: {e['definition']}" for e in selected
        )
        messages = [
            {"role": "system", "content": (
                AIA_KARTEIKARTEN_GLOSSAR_PROMPT.replace("{language}", language)
                + adaptive_suffix
            )},
            {"role": "user", "content": (
                f"Turn these {len(selected)} glossary entries into cards:\n\n{eintraege}"
            )},
        ]
        response = create_with_shrink(client, model=model, messages=messages, temperature=0.5)
        cards = json.loads(_clean_llm_json(response.choices[0].message.content or "")).get("cards") or []
    except Exception as exc:  # noqa: BLE001 - eine feste Frage ist besser als ein Fehlschlag
        logger.warning("Karteikarten aus dem Glossar: Aufruf fehlgeschlagen, feste "
                       "Formulierung greift: {}", exc)
        return fallback

    nach_begriff: dict[str, dict] = {}
    for c in cards:
        begriff = (c.get("term") or "").strip().lower()
        if begriff:
            nach_begriff.setdefault(begriff, c)

    items: list[dict] = []
    for e, ersatz in zip(selected, fallback):
        c = nach_begriff.get(e["term_de"].strip().lower())
        frage = (c.get("question") or "").strip() if c else ""
        antwort = (c.get("answer") or "").strip() if c else ""
        if not frage or not antwort:
            items.append(ersatz)
            continue
        items.append({
            "front": frage,
            "back": antwort,
            "source_label": e.get("filename", ""),
            "page_number": e.get("page_number"),
            "sources": _sources_for(e),
            # Aus dem Glossar und nicht aus der Antwort des Modells. Das Modell darf den
            # Begriff umschreiben, das Gedaechtnis darf davon nicht abhaengen.
            "glossary_term": e["term_de"],
        })
    return items


def _generate_flashcards(client, model, selected: list[dict], language: str,
                         adaptive_suffix: str = "") -> list[dict]:
    """Enrich glossary flashcards so they match the source-derived Lernkarten.

    ONE batched LLM call reuses AIA_LERNKARTEN_PROMPT to add the word decomposition,
    word class, singular/plural forms and an example sentence, and to rewrite the
    definition simply in the UI language. The term itself and its source page stay
    authoritative from the glossary index (no pgvector attribution). Falls back to the
    plain card (definition only) per term if the model call fails or omits a term, so
    flashcards never break.
    """
    plain = [_plain_flashcard(e) for e in selected]
    try:
        terms_text = "\n".join(
            f"- {e['term_de']} ({e.get('term_en', '')}): {e['definition']}" for e in selected
        )
        prompt = (
            AIA_LERNKARTEN_PROMPT.replace("{count}", str(len(selected)))
            .replace("{language}", language)
            + adaptive_suffix
        )
        user = (
            "These glossary terms already have a definition. Create EXACTLY ONE card for "
            "EACH term listed below, in the same order, keeping each 'begriff' VERBATIM as "
            f"written. Base each definition STRICTLY on the one given: keep its meaning and make the "
            f"wording simpler and clearer in {language}. Do NOT add facts, examples, or specifics that "
            "are not in the given definition, do NOT narrow the term down to a special case, and do NOT "
            "replace real content with vague filler. Do NOT add or drop terms.\n\n"
            f"{terms_text}"
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user},
        ]
        response = create_with_shrink(client, model=model, messages=messages, temperature=0.4)
        answer = _clean_llm_json(response.choices[0].message.content or "")
        cards = json.loads(answer).get("cards") or []
    except Exception as exc:  # noqa: BLE001 - enrichment is best-effort, plain cards still work
        logger.warning("Glossary flashcard enrichment failed, using plain cards: {}", exc)
        return plain

    by_term = {}
    for c in cards:
        begriff = (c.get("begriff") or "").strip().lower()
        if begriff:
            by_term.setdefault(begriff, c)

    items: list[dict] = []
    for e, fallback in zip(selected, plain):
        c = by_term.get(e["term_de"].strip().lower())
        if not c:
            items.append(fallback)
            continue
        item = {
            "front": e["term_de"],
            "back": (c.get("definition") or "").strip() or e["definition"],
            "back_en": e.get("term_en", ""),
            "source_label": e.get("filename", ""),
            "page_number": e.get("page_number"),
            "sources": _sources_for(e),
            "glossary_term": e["term_de"],
        }
        extras = flashcard_extras(c, item["front"])
        if extras:
            item["extras"] = extras
        items.append(item)
    return items
