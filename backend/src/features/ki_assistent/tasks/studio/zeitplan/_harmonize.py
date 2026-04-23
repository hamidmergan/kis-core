"""Cross-Candidate-Title-Harmonisierung: gleiche Events am gleichen Datum → gleicher Titel."""

import json
from collections import defaultdict
from datetime import date

from loguru import logger

from src.features.ki_assistent.tasks._helpers import _clean_llm_json
from src.tool_prompts import KIA_ZEITPLAN_HARMONIZE_PROMPT

from src.features.ki_assistent.tasks.studio.zeitplan._classify import _CLASSIFY_TIMEOUT_SECS
from src.features.ki_assistent.tasks.studio.zeitplan._parse import (
    _parse_date,
    _resolve_current_year,
)


def _harmonize_same_date_titles(
    client, model, all_candidates: list[dict], classifications: list[dict],
    today_d: date, existing_entries: list[dict],
) -> None:
    """Cross-candidate dedup pass. Shows the LLM ALL events on one date —
    both new candidates (title can be rewritten) and existing DB entries
    (title is fixed). The LLM groups same-events; any new candidate whose
    group contains an existing entry gets rewritten to that existing title,
    so fuzzy-merge downstream picks it up instead of creating a duplicate.
    Mutates `classifications` in place.
    """
    cand_groups: dict[date, list[int]] = defaultdict(list)
    for idx, (cand, cls) in enumerate(zip(all_candidates, classifications)):
        if not cls["keep"] or cls["is_footer"] or cls.get("is_historical"):
            continue
        if cand.get("date_iso"):
            d = _parse_date(cand["date_iso"])
        elif cand.get("partial_date"):
            mo, da = cand["partial_date"]
            d = _resolve_current_year(today_d, mo, da)
        else:
            d = None
        if d is not None:
            cand_groups[d].append(idx)

    existing_by_date: dict[date, list[dict]] = defaultdict(list)
    for e in existing_entries:
        d = e.get("due_date")
        if d is not None:
            existing_by_date[d].append(e)

    for d, indices in cand_groups.items():
        existing_at_d = existing_by_date.get(d, [])
        titles = {classifications[i]["title"] for i in indices}
        # Skip only if: no existing entries AND candidates already share a title
        if not existing_at_d and len(titles) <= 1:
            continue

        items: list[dict] = []
        for i in indices:
            items.append({
                "id": f"c{i}",  # 'c' prefix = candidate (rewritable)
                "role": "candidate",
                "title": classifications[i]["title"],
                "description": classifications[i].get("description"),
                "type": classifications[i]["type"],
            })
        for e in existing_at_d:
            items.append({
                "id": f"e{e['id']}",  # 'e' prefix = existing (fixed title)
                "role": "existing",
                "title": e.get("title") or "",
                "description": e.get("description"),
                "type": e.get("type"),
            })

        user_msg = (
            f"Date: {d.isoformat()}\n"
            "Some items are NEW candidates (role=candidate, title can be rewritten).\n"
            "Others are EXISTING entries in the DB (role=existing, title is fixed).\n"
            "If a candidate describes the SAME event as an existing entry, put them\n"
            "in the same group AND set canonical_title = the existing entry's title.\n\n"
            f"Events on this date:\n{json.dumps(items, ensure_ascii=False)}"
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": KIA_ZEITPLAN_HARMONIZE_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=_CLASSIFY_TIMEOUT_SECS,
            )
            raw = _clean_llm_json((response.choices[0].message.content or "").strip())
            parsed = json.loads(raw)
            groups_out = parsed.get("groups") or []
            for g in groups_out:
                ids = g.get("ids") or []
                canonical = (g.get("canonical_title") or "").strip()
                if not canonical:
                    continue
                # Only rewrite candidates (c-prefixed); existing entries stay fixed.
                cand_ids = [int(i[1:]) for i in ids if isinstance(i, str) and i.startswith("c") and i[1:].isdigit()]
                if not cand_ids:
                    continue
                for i in cand_ids:
                    if 0 <= i < len(classifications):
                        classifications[i]["title"] = canonical
                logger.info(
                    "Zeitplan harmonize: date {} — candidates {} aligned to '{}'",
                    d.isoformat(), cand_ids, canonical,
                )
        except Exception as e:
            logger.warning("Zeitplan harmonize failed for {}: {}", d.isoformat(), e)
