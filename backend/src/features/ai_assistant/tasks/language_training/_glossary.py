"""mode='glossary': Exercise-Items aus bereits indiziertem Glossary generieren."""

import json
import random

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _language_label

from src.features.ai_assistant.tasks.language_training._title import title_from_glossary_terms


def generate_from_glossary(
    client, model,
    workspace_id: int,
    user_id: int,
    tool: str,
    count: int,
    locale: str = "de",
) -> tuple[list[dict], str] | None:
    """Returns (items, title) oder None wenn kein Glossary vorhanden."""
    glossary = db.get_aia_glossary_by_workspace(workspace_id, user_id)
    if not glossary:
        return None

    selected = random.sample(glossary, min(count, len(glossary)))
    items: list[dict] = []
    language = _language_label(locale)

    def _sources_for(e: dict) -> list[dict]:
        # Nav-only: glossary page comes from the index (authoritative), no highlight.
        return [{
            "source_label": e.get("filename", ""),
            "page_number": e.get("page_number"),
            "start_time": None,
        }]

    if tool == "flashcards":
        items = [
            {
                "front": e["term_de"],
                "back": f"{e['term_de']} - {e['definition']}",
                "back_en": e["term_en"],
                "source_label": e.get("filename", ""),
                "page_number": e.get("page_number"),
                "sources": _sources_for(e),
            }
            for e in selected
        ]
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
    elif tool == "lueckentext":
        items = _generate_lueckentext(client, model, selected, count, language)
    elif tool == "vokabeltest":
        items = _generate_vokabeltest(client, model, selected, count, language)

    title = title_from_glossary_terms(client, model, [e["term_de"] for e in selected])
    return items, title


def _build_term_lookup(selected: list[dict]):
    """Build a robust 'find matching glossary entry for an LLM item' function.
    Tries exact term_de, lowercase term_de, lowercase term_en, then positional fallback."""
    by_term = {e["term_de"]: e for e in selected}
    by_term_lower = {e["term_de"].lower(): e for e in selected}
    by_term_en_lower = {e["term_en"].lower(): e for e in selected if e.get("term_en")}

    def find(item: dict, idx: int, extra_keys: tuple[str, ...] = ()) -> dict:
        keys = (item.get("term_de"),) + tuple(item.get(k) for k in extra_keys)
        for key in keys:
            if not key:
                continue
            if key in by_term:
                return by_term[key]
            k = key.lower()
            if k in by_term_lower:
                return by_term_lower[k]
            if k in by_term_en_lower:
                return by_term_en_lower[k]
        if idx < len(selected):
            return selected[idx]
        return {}

    return find


def _generate_lueckentext(client, model, selected: list[dict], count: int, language: str) -> list[dict]:
    terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
    messages = [
        {"role": "system", "content": (
            "You create cloze (gap-filling) exercises. For every term, build a sentence "
            "with a gap that must be filled by the term. "
            f"Write ALL sentences, options, and answers in {language}. "
            f"If the input term is not in {language}, use its {language} equivalent in the sentence and options "
            "(but keep term_de exactly as given so the source page can be looked up).\n\n"
            "Respond ONLY with a JSON array:\n"
            '[{"sentence": "Der Prozess der ___ reduziert Redundanz.", '
            '"answer": "Normalisierung", '
            '"options": ["Indexierung", "Normalisierung", "Partitionierung", "Denormalisierung"], '
            '"correct_idx": 1, "term_de": "Normalisierung"}]\n\n'
            "Rules:\n- Exactly 4 options per question, one of them correct\n"
            "- correct_idx = index of the correct option (0-3)\n"
            "- ___ as the gap placeholder\n"
            "- term_de MUST exactly match the input term (used to look up the source page)\n"
            "- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Quelle' (German) or 'according to the source' (English), matching the output language\n"
            "- Respond ONLY with the JSON array."
        )},
        {"role": "user", "content": f"Create cloze exercises in {language}:\n\n{terms_text}"},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    exercises = json.loads(answer)[:count]

    find_entry = _build_term_lookup(selected)
    items: list[dict] = []
    for idx, ex in enumerate(exercises):
        entry = find_entry(ex, idx, extra_keys=("answer",))
        sl = entry.get("filename") or ""
        pn = entry.get("page_number")
        st = entry.get("start_time")
        item = {
            "front": ex["sentence"],
            "back": ex["answer"],
            "options": ex["options"],
            "correct_idx": ex["correct_idx"],
            "source_label": sl,
            "page_number": pn,
            "start_time": st,
        }
        if sl:
            item["sources"] = [{
                "source_label": sl,
                "page_number": pn,
                "start_time": st,
            }]
        items.append(item)
    return items


def _generate_vokabeltest(client, model, selected: list[dict], count: int, language: str) -> list[dict]:
    terms_text = "\n".join(f"- {e['term_de']} ({e['term_en']}): {e['definition']}" for e in selected)
    messages = [
        {"role": "system", "content": (
            "You create a vocabulary quiz on technical terms (multiple choice). "
            f"Write ALL questions and explanations in {language}. "
            "Translation questions (e.g. 'What is the English translation of X?' / "
            "'Was ist die deutsche Übersetzung von X?') are allowed and keep their target term in "
            "the other language — but the question wording itself is in the output language.\n\n"
            "Respond ONLY with a JSON array:\n"
            '[{"question": "Was ist die englische Übersetzung von Normalisierung?", '
            '"options": ["Indexing", "Normalization", "Partitioning", "Denormalization"], '
            '"correct_idx": 1, "explanation": "Normalization ist...", '
            '"term_de": "Normalisierung"}]\n\n'
            "Rules:\n- Mix DE -> EN, EN -> DE, and definition questions\n"
            "- Pick terms suitable for MC (clear definition, plausible distractors)\n"
            "- Exactly 4 options, one correct\n- correct_idx = 0-3\n"
            "- term_de MUST exactly match the input term (used to look up the source page)\n"
            "- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Quelle' (German) or 'according to the source' (English), matching the output language\n"
            "- Respond ONLY with the JSON array."
        )},
        {"role": "user", "content": f"Create vocabulary-quiz questions in {language} for these technical terms:\n\n{terms_text}"},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    questions = json.loads(answer)[:count]

    find_entry = _build_term_lookup(selected)
    items: list[dict] = []
    for idx, q in enumerate(questions):
        entry = find_entry(q, idx)
        sl = entry.get("filename") or ""
        pn = entry.get("page_number")
        st = entry.get("start_time")
        item = {
            "front": q["question"],
            "back": q["options"][q["correct_idx"]],
            "options": q["options"],
            "correct_idx": q["correct_idx"],
            "explanation": q.get("explanation"),
            "source_label": sl,
            "page_number": pn,
            "start_time": st,
        }
        if sl:
            item["sources"] = [{
                "source_label": sl,
                "page_number": pn,
                "start_time": st,
            }]
        items.append(item)
    return items
