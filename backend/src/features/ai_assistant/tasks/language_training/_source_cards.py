"""Card generation from source (mode='source'): 2-pass - generate questions, then
answer each question via the SAME chat pipeline (AIA_SYSTEM_RAG + chat citation
format) so chip behaviour is identical to chat citations."""

import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import AIA_KARTEIKARTEN_QUESTIONS_PROMPT, aia_system_rag

from src.features.ai_assistant.tasks.language_training._card_base import with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


# Same regex shape used by chat - see backend/src/features/ai_assistant/routes/chat.py
# and frontend/src/app/workspace/[uuid]/_components/chat/_citations.tsx.
# Captures: 1=doc index N, 2=page number (or None), 3=timestamp (or None), 4=keywords.
_CITATION_RE = re.compile(
    r"[\[【](?:Q?(\d+),\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*\|\s*([^\]】]+))?\s*[\]】]"
)

_MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".mov", ".mkv"}


def _language_label(locale: str) -> str:
    return "English" if (locale or "").lower().startswith("en") else "German"


def generate_cards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    existing_fronts: list[str],
    locale: str = "de",
) -> tuple[list[dict], str]:
    # Pass 1: generate the questions
    title, questions = _generate_questions(client, model, ctx, count, existing_fronts, locale)
    if not questions:
        return [], title or ctx.multi_label

    # Pass 2: answer each question via the chat pipeline.
    # Cap parallelism at 2 - KISSKI returns 429 for higher concurrency on a single
    # user, and we don't want to lose questions to rate limits.
    chat_ctx, qmap = _build_chat_context(ctx)
    with ThreadPoolExecutor(max_workers=min(2, len(questions))) as pool:
        answers = list(pool.map(
            lambda q: _answer_via_chat(client, model, q, chat_ctx, locale),
            questions,
        ))

    items: list[dict] = []
    for q, raw_answer in zip(questions, answers):
        if not raw_answer:
            continue
        chips = _parse_citations_to_chips(raw_answer, qmap)
        clean_back = _strip_citations(raw_answer)
        item: dict = {"front": q, "back": clean_back}
        if chips:
            item["sources"] = chips
            item["source_label"] = chips[0]["source_label"]
            item["page_number"] = chips[0]["page_number"]
            item["start_time"] = chips[0].get("start_time")
        items.append(item)

    return items, title or ctx.multi_label


# ─── Pass 1 ──────────────────────────────────────────────────────────────────

def _generate_questions(
    client, model, ctx: QuelleContext, count: int, existing_fronts: list[str],
    locale: str = "de",
) -> tuple[str, list[str]]:
    language = _language_label(locale)
    prompt = (
        AIA_KARTEIKARTEN_QUESTIONS_PROMPT
        .replace("{count}", str(count))
        .replace("{language}", language)
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Generate {count} questions from {ctx.source_hint} "
            f"(write them in {language}, regardless of the source-text language):\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    try:
        data = json.loads(_clean_llm_json(response.choices[0].message.content or ""))
    except json.JSONDecodeError as e:
        logger.error("Karteikarten questions JSON parse failed: {}", e)
        return "", []
    title = (data.get("title") or "").strip()
    questions = [q.strip() for q in (data.get("questions") or []) if isinstance(q, str) and q.strip()]
    return title, questions[:count]


# ─── Pass 2: chat pipeline ───────────────────────────────────────────────────

def _build_chat_context(ctx: QuelleContext) -> tuple[str, list[dict]]:
    """Build the same XML <documents> context that chat.py uses, plus a qmap that
    resolves doc index N -> {uuid, filename, source_label, chunks}.

    qmap entries carry their source chunks so citation parsing can resolve the
    real page where a keyword appears (LLM citations frequently point at the
    wrong page, same bug pattern that was fixed for the glossary task)."""
    from src import database as db

    parts: list[str] = []
    qmap: list[dict] = []
    for idx, (sname, src) in enumerate(ctx.source_by_name.items(), start=1):
        chunks = db.get_chunks_by_source(src["id"])
        if not chunks:
            continue
        chunk_lines: list[str] = []
        for c in chunks:
            if c.get("start_time") is not None:
                # keep media format consistent with chat
                m, s = divmod(int(c["start_time"]), 60)
                loc = f"{m:02d}:{s:02d}"
            else:
                loc = f"S. {c['page_number']}"
            chunk_lines.append(f"[{loc}] {c['content']}")
        content = "\n".join(chunk_lines)
        parts.append(
            f'<document index="{idx}">\n'
            f'<source>{sname}</source>\n'
            f'<content>\n{content}\n</content>\n'
            f'</document>'
        )
        qmap.append({
            "qnum": idx,
            "uuid": src["uuid"],
            "filename": sname,
            "is_media": Path(sname).suffix.lower() in _MEDIA_EXTS,
            "chunks": [(c["page_number"], (c["content"] or "").lower()) for c in chunks],
        })

    xml = f"<documents>\n{''.join(parts)}\n</documents>"
    return xml, qmap


def _answer_via_chat(client, model, question: str, chat_ctx: str, locale: str = "de") -> str:
    """Run aia_system_rag (chat's exact prompt) for a single question.
    Retries on 429 with jittered backoff so transient rate limits don't drop a card."""
    # Flashcard length constraint: chat answers full paragraphs, but a Karteikarte
    # back side needs to fit on a card. Add the constraint to the user message so
    # the RAG prompt (and its citation rules) stays byte-identical to chat.
    # Pin the answer language explicitly: aia_system_rag only says "follow the
    # question's language", which weaker models ignore and mirror the (German)
    # source instead — so state the target language outright, like the MC path.
    language = _language_label(locale)
    flashcard_hint = (
        f"Write the answer in {language}, regardless of the source-text language. "
        "Answer in MAX 2-3 short sentences. NO bullet points, NO markdown formatting "
        "(no **bold**, no lists). Plain flowing text. Keep citations [N, S. X | keywords] inline as instructed."
    )
    messages = [
        {"role": "system", "content": aia_system_rag(locale)},
        {"role": "user", "content": f"{chat_ctx}\n\nQuestion: {question}\n\n{flashcard_hint}"},
    ]
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            last_err = e
            if "429" not in str(e):
                break
            time.sleep(1.5 * (attempt + 1) + random.uniform(0, 0.5))
    logger.error("Karteikarten chat-answer failed for question {!r}: {}", question, last_err)
    return ""


# ─── Citation parsing (mirrors frontend _citations.tsx) ──────────────────────

def _parse_citations_to_chips(answer: str, qmap: list[dict]) -> list[dict]:
    """Extract one chip per `[N, S. X | keywords]` citation in the answer."""
    qmap_by_idx = {q["qnum"]: q for q in qmap}
    chips: list[dict] = []
    # Dedup by (filename, page): an answer with N sentences citing the same page
    # produces N citations - for the card view we collapse to one chip per page,
    # keeping the FIRST keyword (a representative term for that page).
    seen: set[tuple[str, int]] = set()
    for m in _CITATION_RE.finditer(answer):
        idx_str, page_str, time_str, keywords = m.group(1), m.group(2), m.group(3), m.group(4)
        idx = int(idx_str) if idx_str else (qmap[0]["qnum"] if qmap else 1)
        entry = qmap_by_idx.get(idx) or (qmap[0] if qmap else None)
        if not entry:
            continue
        page = int(page_str) if page_str else 0
        start_time: float | None = None
        if time_str:
            tp = [int(x) for x in time_str.split(":")]
            start_time = tp[0] * 3600 + tp[1] * 60 + tp[2] if len(tp) == 3 else tp[0] * 60 + tp[1]
        keyword = (keywords or "").strip().strip("\"'") if keywords else ""
        # Match the Lernkarten/Vokabeltest pattern: highlight_text must be a
        # single verbatim token so exactSelection=true matching succeeds. LLM
        # multi-word keyword phrases ("Mentorin Erika Mustermann") often don't
        # appear contiguously on the page and break exact match.
        keyword = keyword.split()[0] if keyword else ""
        # Same chunk-resolution as the glossary task: the LLM cites pages
        # unreliably. Look up the keyword in the source's chunks and override
        # the citation's page with the chunk where it actually appears, so the
        # frontend exactSelection match has something to find.
        if keyword and not start_time:
            kw_lower = keyword.lower()
            for chunk_page, chunk_content in entry.get("chunks", []):
                if kw_lower in chunk_content:
                    page = chunk_page
                    break
        key = (entry["filename"], page)
        if key in seen:
            continue
        seen.add(key)
        chips.append({
            "source_label": entry["filename"],
            "page_number": page,
            "start_time": start_time,
            "highlight_text": keyword or None,
        })
    return chips


def _strip_citations(answer: str) -> str:
    """Remove `[N, S. X | kws]` markers from the displayed answer text."""
    cleaned = _CITATION_RE.sub("", answer)
    cleaned = re.sub(r"[ \t]+([.!?,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()
