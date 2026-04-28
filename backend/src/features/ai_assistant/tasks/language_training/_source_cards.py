"""Card generation from source text with evidence validation + chip merge (mode='source')."""

import json
import re

from src import database as db
from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.tool_prompts import KIA_KARTEIKARTEN_PROMPT

from src.features.ai_assistant.tasks.language_training._card_base import parse_card, with_avoid
from src.features.ai_assistant.tasks.language_training._context import QuelleContext, resolve_segment_start
from src.features.ai_assistant.tasks.language_training._text_utils import (
    build_page_text,
    evidence_matches_page,
    find_orig_span,
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
    """Parse + validate a card object: builds evidence chips, merges per page."""
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

    # Validate the evidence of each answer_part - multiple chips per page allowed,
    # but deduplicated if they share a long common substring
    validated_chips: list[dict] = []
    seen_norms: list[str] = []

    for part in answer_parts:
        ev_text = (part.get("evidence") or "").strip()
        ev_page = part.get("page_number")
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
        seen_norms.append(ev_norm)
        chunk_start = ctx.time_map.get((sl, target_page))
        seg_start = resolve_segment_start(ctx.segments_by_label, sl, ev_text, chunk_start)
        validated_chips.append({
            "source_label": sl,
            "page_number": target_page,
            "start_time": seg_start,
            "highlight_text": ev_text,
        })

    validated_chips = _merge_page_chips(page_texts, validated_chips)

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


def _merge_page_chips(page_texts: dict[int, str], chips: list[dict]) -> list[dict]:
    """Merge all chips of the same page into one (span from first to last evidence)."""
    by_page: dict[int, list[dict]] = {}
    for ch in chips:
        pn = ch.get("page_number") or 0
        by_page.setdefault(pn, []).append(ch)
    merged: list[dict] = []
    for pn, page_chips in by_page.items():
        if len(page_chips) == 1:
            merged.append(page_chips[0])
            continue
        page_orig = page_texts.get(pn, "")
        if not page_orig:
            merged.append(page_chips[0])
            continue
        positions: list[tuple[int, int]] = []
        for ch in page_chips:
            span = find_orig_span(page_orig, ch["highlight_text"])
            if span:
                positions.append(span)
        if not positions:
            merged.append(page_chips[0])
            continue
        span_start = min(p[0] for p in positions)
        span_end = max(p[1] for p in positions)
        combined = page_orig[span_start:span_end].strip()
        combined = re.sub(r"[ \t]+", " ", combined)
        combined = re.sub(r" *\n *", "\n", combined)
        first_ch = page_chips[0]
        merged.append({
            "source_label": first_ch["source_label"],
            "page_number": first_ch["page_number"],
            "start_time": first_ch.get("start_time"),
            "highlight_text": combined,
        })
    return merged
