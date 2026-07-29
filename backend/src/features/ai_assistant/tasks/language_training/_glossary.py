"""mode='glossary': Exercise-Items aus bereits indiziertem Glossary generieren."""

import json
import random

from loguru import logger

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label
from src.tool_prompts import AIA_LERNKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._title import title_from_glossary_terms


def _sources_for(e: dict) -> list[dict]:
    # Nav-only: glossary page comes from the index (authoritative), no highlight.
    return [{
        "source_label": e.get("filename", ""),
        "page_number": e.get("page_number"),
        "start_time": None,
    }]


def generate_from_glossary(
    client, model,
    workspace_id: int,
    user_id: int,
    tool: str,
    count: int,
    locale: str = "de",
    adaptive_suffix: str = "",
) -> tuple[list[dict], str] | None:
    """Returns (items, title) oder None wenn kein Glossary vorhanden."""
    glossary = db.get_aia_glossary_by_workspace(workspace_id, user_id)
    if not glossary:
        return None

    selected = random.sample(glossary, min(count, len(glossary)))
    items: list[dict] = []
    language = _language_label(locale)

    if tool == "flashcards":
        items = _generate_flashcards(client, model, selected, language, adaptive_suffix)
    elif tool == "karteikarten":
        items = [
            {
                "front": e["term_de"],
                "back": f"{e['term_en']} - {e['definition']}",
                "source_label": e.get("filename", ""),
                "page_number": e.get("page_number"),
                "sources": _sources_for(e),
            }
            for e in selected
        ]

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
    }


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
        response = client.chat.completions.create(model=model, messages=messages, temperature=0.4)
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
        }
        extras = {
            k: (c.get(k) or "").strip()
            for k in ("word_parts", "word_parts_explained", "example_sentence",
                      "word_class", "singular", "plural")
            if (c.get(k) or "").strip()
        }
        if extras:
            item["extras"] = extras
        items.append(item)
    return items
