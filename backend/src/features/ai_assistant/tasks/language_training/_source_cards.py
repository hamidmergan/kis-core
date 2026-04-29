"""Card generation from source text (mode='source'): one chip per evidence with short keyword."""

import json

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import KIA_KARTEIKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._card_base import parse_card, with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext, resolve_segment_start
from src.features.ai_assistant.tasks.language_training._text_utils import (
    build_page_text,
    evidence_matches_page,
    is_duplicate_evidence,
    normalize_for_match,
)
from src.features.ai_assistant.tasks.language_training._title import title_from_items


def generate_cards_from_source(
    client, model,
    ctx: QuelleContext,
    count: int,
    existing_fronts: list[str],
) -> tuple[list[dict], str]:
    prompt = KIA_KARTEIKARTEN_PROMPT.replace("{count}", str(count))
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": with_avoid(
            existing_fronts,
            f"Create study cards from {ctx.source_hint} (respond in the source-text language):\n\n{ctx.context}",
        )},
    ]
    response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    answer = _clean_llm_json(response.choices[0].message.content or "")
    data = json.loads(answer)

    items = [_parse_card(ctx, c) for c in data.get("cards", [])][:count]
    title = title_from_items(client, model, items, ctx.multi_label)
    return items, title


def _parse_card(ctx: QuelleContext, c: dict) -> dict:
    """Parse + validate a card object: one chip per answer_part with a short highlight keyword."""
    answer_parts = c.get("answer_parts") or []
    back_text = " ".join((p.get("statement") or "").strip() for p in answer_parts if p.get("statement"))
    c_merged = dict(c)
    c_merged["back"] = back_text or c.get("back", "")
    item = parse_card(ctx, c_merged)

    # Single-source enforcement for cards
    sl = c.get("source_label") or ctx.first_label
    src_obj = ctx.source_by_name.get(sl)
    if not src_obj:
        return item

    # Page text lookup (deduped for overlapping chunks)
    page_chunks_raw: dict[int, list] = {}
    for ch in db.get_chunks_by_source(src_obj["id"]):
        page_chunks_raw.setdefault(ch["page_number"], []).append(ch)
    page_texts: dict[int, str] = {p: build_page_text(chs) for p, chs in page_chunks_raw.items()}
    page_texts_norm = {p: normalize_for_match(t) for p, t in page_texts.items()}

    # Validate evidence + use the LLM-supplied short `highlight` keyword as
    # highlight_text — same pattern as chat citations and DataTable.
    # Frontend tryHighlightOnPage finds the keyword and expands via sentence/paragraph
    # heuristic. Long verbatim quotes don't match reliably across PDF line wraps.
    validated_chips: list[dict] = []
    seen_norms: list[str] = []

    for part in answer_parts:
        ev_text = (part.get("evidence") or "").strip()
        ev_page = part.get("page_number")
        highlight = (part.get("highlight") or "").strip()
        if not ev_text or ev_page is None:
            continue
        ev_norm = normalize_for_match(ev_text)
        if is_duplicate_evidence(ev_norm, seen_norms):
            continue
        target_page: int | None = None
        if ev_page in page_texts_norm and evidence_matches_page(ev_norm, page_texts_norm[ev_page]):
            target_page = ev_page
        else:
            for p, pt in page_texts_norm.items():
                if evidence_matches_page(ev_norm, pt):
                    target_page = p
                    break
        if target_page is None:
            continue
        # Verify the highlight keyword actually appears on the target page; fall
        # back to the first 3 words of the evidence if it's missing or unfindable.
        hl_norm = normalize_for_match(highlight) if highlight else ""
        if not hl_norm or hl_norm not in page_texts_norm[target_page]:
            highlight = " ".join(ev_text.split()[:3])
        seen_norms.append(ev_norm)
        chunk_start = ctx.time_map.get((sl, target_page))
        seg_start = resolve_segment_start(ctx.segments_by_label, sl, highlight, chunk_start)
        validated_chips.append({
            "source_label": sl,
            "page_number": target_page,
            "start_time": seg_start,
            "highlight_text": highlight,
        })

    # Sort by page_number or start_time (media)
    validated_chips.sort(key=lambda s: (
        s.get("start_time") if s.get("start_time") is not None else (s.get("page_number") or 0),
    ))

    if validated_chips:
        item["sources"] = validated_chips
        item["source_label"] = validated_chips[0]["source_label"]
        item["page_number"] = validated_chips[0]["page_number"]
        item["start_time"] = validated_chips[0].get("start_time")
    else:
        item["source_label"] = sl
        if answer_parts:
            first_pn = answer_parts[0].get("page_number")
            if first_pn is not None:
                item["page_number"] = first_pn
                item["start_time"] = ctx.time_map.get((sl, first_pn))
    return item
