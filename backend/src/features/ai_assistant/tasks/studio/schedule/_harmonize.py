"""Cross-Candidate-Title-Harmonisierung: gleiche Events am gleichen Datum → gleicher Titel."""

import json
from collections import defaultdict
from datetime import date

from loguru import logger

from src.features.ai_assistant.tasks._helpers import _clean_llm_json
from src.features.ai_assistant.prompts.schedule_prompts import AIA_SCHEDULE_HARMONIZE_PROMPT

from src.features.ai_assistant.tasks.studio.schedule._classify import _CLASSIFY_TIMEOUT_SECS
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _parse_date,
    _resolve_current_year,
)


def _harmonize_same_date_titles(
    client, model, all_candidates: list[dict], classifications: list[dict],
    today_d: date, existing_entries: list[dict],
) -> None:
    """Cross-candidate dedup pass. Shows the LLM ALL events on one date -
    both new candidates (title can be rewritten) and existing DB entries
    (title is fixed). The LLM groups same-events; any new candidate whose
    group contains an existing entry gets rewritten to that existing title,
    so fuzzy-merge downstream picks it up instead of creating a duplicate.
    Mutates `classifications` in place.

    Termine OHNE Datum bilden eine eigene Gruppe (Schluessel None). Sie brauchen den
    Schritt am dringendsten: dieselbe Zeile "Praesentationen nach Vereinbarung" kommt
    aus der PDF und aus dem Video mit verschiedenen Worten an, und ohne Datum gibt es
    nichts, woran der Textvergleich sie sonst zusammenbinden koennte. Das gemeinsame
    leere Datum ist dabei KEIN Hinweis auf dieselbe Veranstaltung, darauf weist die
    Anfrage fuer diese Gruppe eigens hin.
    """
    # Gruppenschluessel ist (Tag, Genauigkeit). "im Juli" und der 01.07. teilen sich zwar
    # den Sortierpunkt, sind aber nicht dieselbe Aussage und gehoeren nicht in eine Gruppe.
    cand_groups: dict[tuple, list[int]] = defaultdict(list)
    for idx, (cand, cls) in enumerate(zip(all_candidates, classifications)):
        if not cls["keep"] or cls["is_footer"] or cls.get("is_header") or cls.get("is_historical"):
            continue
        if cand.get("date_iso"):
            d = _parse_date(cand["date_iso"])
        elif cand.get("partial_date"):
            mo, da = cand["partial_date"]
            d = _resolve_current_year(today_d, mo, da)
        else:
            d = None
        cand_groups[(d, cand.get("date_precision") or "day")].append(idx)

    existing_by_date: dict[tuple, list[dict]] = defaultdict(list)
    for e in existing_entries:
        existing_by_date[(e.get("due_date"), e.get("date_precision") or "day")].append(e)

    for (d, precision), indices in cand_groups.items():
        existing_at_d = existing_by_date.get((d, precision), [])
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

        if d is None:
            label = "ohne Datum"
        elif precision == "month":
            label = d.strftime("%Y-%m") + " (nur Monat)"
        else:
            label = d.isoformat()
        rollen = (
            "Some items are NEW candidates (role=candidate, title can be rewritten).\n"
            "Others are EXISTING entries in the DB (role=existing, title is fixed).\n"
            "If a candidate describes the SAME event as an existing entry, put them\n"
            "in the same group AND set canonical_title = the existing entry's title.\n\n"
        )
        if d is None:
            user_msg = (
                "These events have NO fixed date, their date is still to be arranged.\n"
                "IMPORTANT: the missing date is NOT shared evidence. The rule 'bias toward "
                "merging on the same date' does NOT apply here. Group two items ONLY when "
                "they clearly name the SAME real event; when in doubt, leave each in its "
                "own group.\n\n"
                + rollen
                + f"Events without a fixed date:\n{json.dumps(items, ensure_ascii=False)}"
            )
        elif precision == "month":
            user_msg = (
                f"Month: {d.strftime('%Y-%m')}. The sources name only this month for all "
                "of these events, no day.\n"
                + rollen
                + f"Events in this month:\n{json.dumps(items, ensure_ascii=False)}"
            )
        else:
            user_msg = (
                f"Date: {d.isoformat()}\n"
                + rollen
                + f"Events on this date:\n{json.dumps(items, ensure_ascii=False)}"
            )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": AIA_SCHEDULE_HARMONIZE_PROMPT},
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
                    "Schedule harmonize: date {} - candidates {} aligned to '{}'",
                    label, cand_ids, canonical,
                )
        except Exception as e:
            logger.warning("Schedule harmonize failed for {}: {}", label, e)
