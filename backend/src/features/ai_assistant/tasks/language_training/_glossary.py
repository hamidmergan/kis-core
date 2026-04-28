"""mode='glossary': Exercise-Items aus bereits indiziertem Glossary generieren."""

import json
import random

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json

from src.features.ai_assistant.tasks.language_training._title import title_from_glossary_terms


def generate_from_glossary(
    client, model,
    module_id: int,
    tool: str,
    count: int,
) -> tuple[list[dict], str] | None:
    """Returns (items, title) oder None wenn kein Glossary vorhanden."""
    glossary = db.get_aia_glossary_by_module(module_id)
    if not glossary:
        return None

    selected = random.sample(glossary, min(count, len(glossary)))
    items: list[dict] = []

    if tool == "flashcards":
        items = [
            {
                "front": e["term_de"],
                "back": f"{e['term_de']} — {e['definition']}",
                "back_en": e["term_en"],
                "source_label": e.get("filename", ""),
                "page_number": e.get("page_number"),
            }
            for e in selected
        ]
    elif tool == "karteikarten":
        items = [
            {
                "front": e["term_de"],
                "back": f"{e['term_en']} — {e['definition']}",
                "source_label": e.get("filename", ""),
                "page_number": e.get("page_number"),
            }
            for e in selected
        ]
    elif tool == "lueckentext":
        items = _generate_lueckentext(client, model, selected, count)
    elif tool == "vokabeltest":
        items = _generate_vokabeltest(client, model, selected, count)

    title = title_from_glossary_terms(client, model, [e["term_de"] for e in selected])
    return items, title


def _generate_lueckentext(client, model, selected: list[dict], count: int) -> list[dict]:
    terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
    messages = [
        {"role": "system", "content": (
            "You create cloze (gap-filling) exercises. For every term, build a sentence "
            "with a gap that must be filled by the term. "
            "Write sentences and answers in the SAME language as the input terms (German terms -> German sentences).\n\n"
            "Respond ONLY with a JSON array:\n"
            '[{"sentence": "Der Prozess der ___ reduziert Redundanz.", '
            '"answer": "Normalisierung", '
            '"options": ["Indexierung", "Normalisierung", "Partitionierung", "Denormalisierung"], '
            '"correct_idx": 1, "term_de": "Normalisierung", "page_number": 12}]\n\n'
            "Rules:\n- Exactly 4 options per question, one of them correct\n"
            "- correct_idx = index of the correct option (0-3)\n"
            "- ___ as the gap placeholder\n"
            "- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Source'\n"
            "- Respond ONLY with the JSON array."
        )},
        {"role": "user", "content": f"Create cloze exercises (in the source language of the terms):\n\n{terms_text}"},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    exercises = json.loads(answer)[:count]
    return [
        {
            "front": ex["sentence"],
            "back": ex["answer"],
            "options": ex["options"],
            "correct_idx": ex["correct_idx"],
            "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == ex.get("term_de")), ""),
            "page_number": ex.get("page_number"),
        }
        for ex in exercises
    ]


def _generate_vokabeltest(client, model, selected: list[dict], count: int) -> list[dict]:
    terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
    messages = [
        {"role": "system", "content": (
            "You create a vocabulary quiz on technical terms (multiple choice). "
            "Write questions and explanations in the SAME language as the input terms (German terms -> German questions).\n\n"
            "Respond ONLY with a JSON array:\n"
            '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
            '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
            '"correct_idx": 1, "explanation": "Normalization ist...", '
            '"term_de": "Normalisierung"}]\n\n'
            "Rules:\n- Mix DE -> EN, EN -> DE, and definition questions\n"
            "- Pick terms suitable for MC (clear definition, plausible distractors)\n"
            "- Exactly 4 options, one correct\n- correct_idx = 0-3\n"
            "- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Source'\n"
            "- Respond ONLY with the JSON array."
        )},
        {"role": "user", "content": f"Create vocabulary-quiz questions for these technical terms (in the source language of the terms):\n\n{terms_text}"},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    questions = json.loads(answer)[:count]
    return [
        {
            "front": q["question"],
            "back": q["options"][q["correct_idx"]],
            "options": q["options"],
            "correct_idx": q["correct_idx"],
            "explanation": q.get("explanation"),
            "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == q.get("term_de")), ""),
            "page_number": q.get("page_number"),
        }
        for q in questions
    ]
