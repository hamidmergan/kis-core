"""MC-basierte Tools (lueckentext, quiz, vokabeltest) aus Quelltext (mode='source')."""

import json
import re

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json

from src.features.ai_assistant.tasks.language_training._card_base import with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._text_utils import normalize_chunk
from src.features.ai_assistant.tasks.language_training._title import title_from_items


_SOURCE_RULE = (
    "- For every question, include source_label and page_number, the source/page the content came from.\n"
)
_PERSONAL_RULE = (
    "IMPORTANT:\n- Do NOT use personal names in questions. Instead of 'laut Prof. X', write 'laut Quelle' (German) or 'according to the source' (English), matching the output language.\n"
)


def _language_label(locale: str) -> str:
    return "English" if (locale or "").lower().startswith("en") else "German"


def generate_mc_from_source(
    client, model,
    ctx: QuelleContext,
    tool: str,
    count: int,
    existing_fronts: list[str],
    locale: str = "de",
) -> tuple[list[dict], str]:
    language = _language_label(locale)
    tool_prompt = _build_prompt(tool, count, language)
    messages = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Write the output in {language}.\n\nSources:\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    exercises = json.loads(answer)
    if isinstance(exercises, list):
        exercises = exercises[:count]

    page_index = _build_page_index(ctx.context)
    chunks_by_source: dict[str, list] = {}

    def find_page(search_text: str) -> tuple[str, int | None]:
        return _match_page(page_index, ctx.first_label, search_text)

    def page_highlight(sl: str | None, pn: int | None) -> str | None:
        return _page_highlight(chunks_by_source, ctx.source_by_name, sl, pn)

    if tool == "lueckentext":
        items = _build_lueckentext_items(ctx, exercises, find_page, page_highlight)
    else:  # quiz + vokabeltest
        items = _build_quiz_items(ctx, exercises, find_page, page_highlight)

    title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _build_prompt(tool: str, count: int, language: str) -> str:
    base = (
        f"You create exercises based on the given source text. "
        f"Write ALL questions, sentences, options, and answers in {language}, "
        f"regardless of the source-text language. Translate source content into {language} if needed.\n\n"
    )
    if tool == "lueckentext":
        return base + (
            "Create cloze (gap-filling) exercises. Respond ONLY with a JSON array:\n"
            '[{"sentence": "Sentence with ___ as a gap", "answer": "Answer", '
            '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
            '"source_label": "Filename.pdf", "page_number": 5}]\n'
            + _PERSONAL_RULE + _SOURCE_RULE +
            f"Create exactly {count} exercises."
        )
    if tool == "quiz":
        return base + (
            "Create multiple-choice comprehension questions for the given text. "
            "The questions should test understanding of the content.\n\n"
            "Respond ONLY with a JSON array:\n"
            '[{"question": "Comprehension question?", "options": ["A", "B", "C", "D"], '
            '"correct_idx": 0, '
            '"source_label": "Filename.pdf", "page_number": 5}]\n'
            + _PERSONAL_RULE + _SOURCE_RULE +
            f"Create exactly {count} questions. Mix easy and hard ones."
        )
    # vokabeltest (default)
    return base + (
        "Create a vocabulary quiz: multiple-choice questions on technical terms from the source text.\n\n"
        "First identify the most important technical terms in the text, then create questions for them.\n"
        "Mix question types:\n"
        "- What does the term X mean?\n"
        "- What is the English translation of X (or German translation)?\n"
        "- Which technical term describes the following: [definition]?\n\n"
        "Pick terms suitable for multiple choice "
        "(clear definition, plausible distractors possible).\n\n"
        "Respond ONLY with a JSON array:\n"
        '[{"question": "Question about the technical term?", "options": ["A", "B", "C", "D"], '
        '"correct_idx": 0, '
        '"source_label": "Filename.pdf", "page_number": 5}]\n'
        + _PERSONAL_RULE + _SOURCE_RULE +
        f"Create exactly {count} questions."
    )


def _build_page_index(context: str) -> list[tuple[str, int, str]]:
    """Baut einen durchsuchbaren Index (label, page, lowered_text) aus den Kontext-Zeilen."""
    idx: list[tuple[str, int, str]] = []
    for line in context.split("\n"):
        m = re.match(r"\[(.+?),\s*S\.\s*(\d+)\]\s*(.*)", line)
        if m:
            idx.append((m.group(1), int(m.group(2)), m.group(3).lower()))
    return idx


def _match_page(
    page_index: list[tuple[str, int, str]],
    fallback_label: str,
    search_text: str,
) -> tuple[str, int | None]:
    """Matcht den Übungstext gegen Kontext-Zeilen, um Source + Seite zu finden."""
    words = re.findall(r"\w+", search_text.lower())
    if not words or not page_index:
        return fallback_label, None
    best_label, best_page, best_score = fallback_label, None, 0
    for label, page, text in page_index:
        score = sum(1 for w in words if w in text)
        if score > best_score:
            best_label, best_page, best_score = label, page, score
    return best_label, best_page


def _page_highlight(
    chunks_cache: dict[str, list],
    source_by_name: dict[str, dict],
    sl: str | None,
    pn: int | None,
) -> str | None:
    if not sl or pn is None:
        return None
    if sl not in chunks_cache:
        src = source_by_name.get(sl)
        chunks_cache[sl] = db.get_chunks_by_source(src["id"]) if src else []
    parts = [
        (ch.get("content") or "").strip()
        for ch in chunks_cache[sl]
        if ch.get("page_number") == pn and (ch.get("content") or "").strip()
    ]
    if not parts:
        return None
    return normalize_chunk(" ".join(parts))


def _build_item_sources(
    page_highlight_fn,
    sl: str,
    pn: int | None,
    st: float | None,
) -> list[dict] | None:
    highlight = page_highlight_fn(sl, pn)
    if not highlight or pn is None:
        return None
    return [{
        "source_label": sl,
        "page_number": pn,
        "start_time": st,
        "highlight_text": highlight,
    }]


def _build_lueckentext_items(ctx: QuelleContext, exercises, find_page, page_highlight) -> list[dict]:
    items = []
    for ex in exercises:
        sl = ex.get("source_label") or ctx.first_label
        pn = ex.get("page_number")
        if not pn:
            sl, pn = find_page(ex["sentence"] + " " + ex["answer"])
        st = ctx.time_map.get((sl, pn or 0))
        items.append({
            "front": ex["sentence"],
            "back": ex["answer"],
            "options": ex["options"],
            "correct_idx": ex["correct_idx"],
            "source_label": sl,
            "page_number": pn,
            "start_time": st,
            "sources": _build_item_sources(page_highlight, sl, pn, st),
        })
    return items


def _build_quiz_items(ctx: QuelleContext, exercises, find_page, page_highlight) -> list[dict]:
    items = []
    for q in exercises:
        sl = q.get("source_label") or ctx.first_label
        pn = q.get("page_number")
        if not pn:
            sl, pn = find_page(q["question"] + " " + q["options"][q["correct_idx"]])
        st = ctx.time_map.get((sl, pn or 0))
        items.append({
            "front": q["question"],
            "back": q["options"][q["correct_idx"]],
            "options": q["options"],
            "correct_idx": q["correct_idx"],
            "source_label": sl,
            "page_number": pn,
            "start_time": st,
            "sources": _build_item_sources(page_highlight, sl, pn, st),
        })
    return items
