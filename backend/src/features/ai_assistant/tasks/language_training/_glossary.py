"""mode='glossar': Exercise-Items aus bereits indiziertem Glossar generieren."""

import json
import random

from src import database as db
from src.features.ki_assistent.tasks._helpers import _clean_llm_json

from src.features.ki_assistent.tasks.sprachtraining._title import title_from_glossary_terms


def generate_from_glossary(
    client, model,
    module_id: int,
    tool: str,
    count: int,
) -> tuple[list[dict], str] | None:
    """Returns (items, title) oder None wenn kein Glossar vorhanden."""
    glossary = db.get_kia_glossary_by_module(module_id)
    if not glossary:
        return None

    selected = random.sample(glossary, min(count, len(glossary)))
    items: list[dict] = []

    if tool == "lernkarten":
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
            "Du erstellst Lückentext-Übungen. Für jeden Begriff erstelle einen Satz "
            "mit einer Lücke, die durch den Begriff gefüllt werden muss.\n\n"
            "Antworte NUR mit einem JSON-Array:\n"
            '[{"sentence": "Der Prozess der ___ reduziert Redundanz.", '
            '"answer": "Normalisierung", '
            '"options": ["Indexierung", "Normalisierung", "Partitionierung", "Denormalisierung"], '
            '"correct_idx": 1, "term_de": "Normalisierung", "page_number": 12}]\n\n'
            "Regeln:\n- Genau 4 Optionen pro Frage, eine davon korrekt\n"
            "- correct_idx = Index der richtigen Option (0-3)\n"
            "- ___ als Lücken-Platzhalter\n"
            "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'\n"
            "- Antworte NUR mit dem JSON-Array"
        )},
        {"role": "user", "content": f"Erstelle Lückentext-Übungen:\n\n{terms_text}"},
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
            "Du erstellst ein Begriffe-Quiz zu Fachbegriffen (Multiple Choice).\n\n"
            "Antworte NUR mit einem JSON-Array:\n"
            '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
            '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
            '"correct_idx": 1, "explanation": "Normalization ist...", '
            '"term_de": "Normalisierung"}]\n\n'
            "Regeln:\n- Mische DE→EN, EN→DE, Definitionsfragen\n"
            "- Wähle Begriffe die sich gut für MC eignen (klare Definition, plausible Distraktoren)\n"
            "- Genau 4 Optionen, eine korrekt\n- correct_idx = 0-3\n"
            "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'\n"
            "- Antworte NUR mit dem JSON-Array"
        )},
        {"role": "user", "content": f"Erstelle Begriffe-Quiz-Fragen zu diesen Fachbegriffen:\n\n{terms_text}"},
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
