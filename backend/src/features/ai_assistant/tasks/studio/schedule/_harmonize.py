"""Cross-candidate title harmonisation: same events on the same date get the same title."""

import json
from collections import defaultdict
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_HARMONIZE_PROMPT

from src.features.ai_assistant.tasks.studio.schedule._classify import _CLASSIFY_TIMEOUT_SECS

# Room for one group per item across every day of the request.
_MAX_TOKENS = 8000
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _candidate_start,
    _range_end_date,
)


def _harmonize_same_date_titles(
    client, model, all_candidates: list[dict], classifications: list[dict],
    today_d: date, existing_entries: list[dict], evidence: dict | None = None,
) -> None:
    """Harmonises the titles day by day in one request, undated appointments are a day of their own."""
    # The group key is day plus precision, 'in July' is not the 1st of July.
    cand_groups: dict[tuple, list[int]] = defaultdict(list)
    for idx, (cand, cls) in enumerate(zip(all_candidates, classifications)):
        if not cls["keep"] or cls["is_footer"] or cls.get("is_header") or cls.get("is_historical"):
            continue
        d, _ = _candidate_start(cand, today_d, evidence, use_end=bool(cls.get("is_range")))
        # The end belongs in the key, otherwise a span collapses into a single appointment.
        ende = _range_end_date(cand, d, today_d) if cls.get("is_range") else None
        cand_groups[(d, ende, cand.get("date_precision") or "day")].append(idx)

    # One anchor per title and day, many people with the same entry would bloat the answer.
    existing_by_date: dict[tuple, list[dict]] = defaultdict(list)
    seen_titles: set[tuple] = set()
    for e in existing_entries:
        key = (e.get("due_date"), e.get("end_date"), e.get("date_precision") or "day")
        title_key = (key, (e.get("title") or "").strip().casefold())
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        existing_by_date[key].append(e)

    rollen = (
        "Some items are NEW candidates (role=candidate, title can be rewritten).\n"
        "Others are EXISTING entries in the DB (role=existing, title is fixed).\n"
        "If a candidate describes the SAME event as an existing entry, put them\n"
        "in the same group AND set canonical_title = the existing entry's title.\n\n"
    )
    abschnitte: list[str] = []
    tag_von_kandidat: dict[int, tuple] = {}
    for (d, ende, precision), indices in cand_groups.items():
        existing_at_d = existing_by_date.get((d, ende, precision), [])
        titles = {classifications[i]["title"] for i in indices}
        # Skip only if: no existing entries AND candidates already share a title
        if not existing_at_d and len(titles) <= 1:
            continue

        items: list[dict] = []
        for i in indices:
            tag_von_kandidat[i] = (d, ende, precision)
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

        if d is None:
            abschnitte.append(
                "Events with NO fixed date, their date is still to be arranged.\n"
                "IMPORTANT: the missing date is NOT shared evidence. The rule 'bias toward "
                "merging on the same date' does NOT apply here. Group two items ONLY when "
                "they clearly name the SAME real event; when in doubt, leave each in its "
                "own group.\n"
                + json.dumps(items, ensure_ascii=False)
            )
        elif precision == "month":
            abschnitte.append(
                f"Month: {d.strftime('%Y-%m')}. The sources name only this month for all "
                "of these events, no day.\n" + json.dumps(items, ensure_ascii=False)
            )
        else:
            abschnitte.append(f"Date: {d.isoformat()}\n" + json.dumps(items, ensure_ascii=False))

    if not abschnitte:
        return

    # One request for every day, the sections keep the days apart.
    user_msg = (
        f"{len(abschnitte)} day sections follow. Group items ONLY within their own section, "
        "never across sections.\n\n" + rollen
        + "\n\n".join(f"### Section {n}\n{a}" for n, a in enumerate(abschnitte, 1))
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": AIA_SCHEDULE_HARMONIZE_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=_MAX_TOKENS,
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
            cand_ids = [int(i[1:]) for i in ids
                        if isinstance(i, str) and i.startswith("c") and i[1:].isdigit()]
            cand_ids = [i for i in cand_ids if i in tag_von_kandidat]
            if not cand_ids:
                continue
            # A group that mixes days is a model slip, the titles stay as they are.
            if len({tag_von_kandidat[i] for i in cand_ids}) > 1:
                logger.warning("Schedule harmonize: group {} spans several days, ignored", ids)
                continue
            for i in cand_ids:
                classifications[i]["title"] = canonical
            logger.info("Schedule harmonize: candidates {} aligned to '{}'", cand_ids, canonical)
    except Exception as e:
        logger.warning("Schedule harmonize failed: {}", e)
