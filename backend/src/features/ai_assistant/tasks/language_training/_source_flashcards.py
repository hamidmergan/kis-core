"""Flashcards-Generierung aus Quelltext (mode='source')."""

import json

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.language_training_prompts import AIA_LERNKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._title import title_from_items
from src.features.ai_assistant.tasks.language_training._wortteile import clean_word_parts
from src.services.llm_context_healing import create_with_shrink


# Gemeinsame Schlüssel für extras in Lernkarten (Quelltext-Weg und Glossar-Weg).
# Beide Modi enrichen Karten mit denselben Felder: Wortzerlegung, Beispielsatz,
# Wortart (mit Klammer für Verben: Art/Reflexivität), und für Verben die drei
# Zeitformen (3. Person Singular: Präsens, Präteritum, Perfekt mit Hilfsverb).
AIA_FLASHCARD_EXTRAS_FIELDS = (
    "word_parts", "word_parts_explained", "example_sentence",
    "word_class", "singular", "plural",
    "verb_present", "verb_past", "verb_perfect"
)


def flashcard_extras(c: dict, begriff: str) -> dict:
    """Die extras einer Lernkarte, gemeinsam für den Quelltext- und den Glossar-Weg.

    Die Wortzerlegung wird dabei nachgerechnet (siehe ``_wortteile``): das Modell hat
    Teile erfunden, die im Begriff gar nicht vorkommen. Leere Felder entstehen erst gar
    nicht, denn die Ansicht zeichnet eine Zeile, sobald der Schlüssel da ist.
    """
    extras = {
        k: (c.get(k) or "").strip()
        for k in AIA_FLASHCARD_EXTRAS_FIELDS
        if (c.get(k) or "").strip()
    }
    parts, explained = clean_word_parts(
        begriff, extras.get("word_parts", ""), extras.get("word_parts_explained", ""))
    if extras.get("word_parts") and not parts:
        # Damit sichtbar bleibt, wie oft das Modell danebenliegt. Ohne diese Zeile wäre
        # die Bremse unsichtbar und niemand merkte, wenn sie zu oft oder gar nicht greift.
        logger.info("Lernkarte {}: Wortzerlegung {!r} verworfen, ein Teil steht nicht im Begriff",
                    begriff, extras["word_parts"])
    for schluessel, wert in (("word_parts", parts), ("word_parts_explained", explained)):
        if wert:
            extras[schluessel] = wert
        else:
            extras.pop(schluessel, None)
    return extras


def generate_flashcards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    locale: str = "de",
    language: str = "German",
    adaptive_suffix: str = "",
    title_avoidance: str = "",
    coverage: str = "",
) -> tuple[list[dict], str]:
    # Explanations follow the UI language; the term itself (begriff) stays in the
    # source language for study and highlighting (see prompt LANGUAGE rule).
    # adaptive_suffix pitches the definitions at the learner's CEFR level (empty
    # when they have no level); it OVERRIDES the prompt's default register.
    prompt = (
        AIA_LERNKARTEN_PROMPT.replace("{count}", str(count)).replace("{language}", language)
        + adaptive_suffix + title_avoidance + coverage
    )
    # No "avoid these existing cards" block: feeding them back made the model copy them.
    # Variation comes from the context sweep in build_source_context, and a repeat that
    # still gets through is dropped afterwards by _dedup. Only the
    # TITLE gets a do-not-repeat list (title_avoidance), which has no such pull.
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": (
            f"Create flashcards from {ctx.source_hint}. Write the explanations in {language}, "
            f"keep the term itself in the source-text language:\n\n{ctx.context}"
        )},
    ]
    # 0.6 for a little wording diversity; the real variation is the context sweep in
    # build_source_context (different chunks per run). Still JSON-safe.
    response = create_with_shrink(client, endpoint="lernkarten", model=model, messages=messages, temperature=0.6)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)

    cards = (data.get("cards") or [])[:count]
    items = [_format_lernkarte(c) for c in cards]
    # One batched attribution for the whole set: each card cites where its term+definition
    # actually appears (same pgvector gate as chat), nav-only, no highlight. A card is one
    # atomic fact, so multi=False -> exactly the single best-matching source, never several.
    attach_chips(items, [_card_claim(c) for c in cards], ctx, multi=False)
    # The generation prompt already asks for a "title" (see AIA_LERNKARTEN_PROMPT), so take it
    # from this same response instead of spending a second call on it. title_from_items stays
    # as the fallback for models that skip the field.
    title = (data.get("title") or "").strip()
    if not title:
        title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _format_lernkarte(c: dict) -> dict:
    """Map the LLM card to shared DB columns (front/back). Source attribution is added
    afterwards by attach_chips, not guessed here."""
    item = {
        "front": (c.get("begriff") or "").strip(),
        "back": (c.get("definition") or "").strip(),
        "back_en": (c.get("begriff_en") or "").strip(),
        # Which numbered context section the model says it used. Not persisted
        # (finalize_exercise_set only reads known keys), it exists so the caller can
        # check that every section was actually served.
        "_section": c.get("section"),
    }
    extras = flashcard_extras(c, item["front"])
    if extras:
        item["extras"] = extras
    return item


def _card_claim(c: dict) -> str:
    """Text attributed back to the source: the term plus its definition."""
    begriff = (c.get("begriff") or "").strip()
    definition = (c.get("definition") or "").strip()
    claim = f"{begriff}: {definition}".strip(": ").strip()
    return claim or begriff
