"""KI-Assistent Celery tasks — sprachtraining exercise-set generation."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    TUTOR_SUMMARY_MAX_RETRIES,
    TUTOR_SUMMARY_TIMEOUT_SMALL,
    TUTOR_SUMMARY_TIMEOUT_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_SMALL,
    TUTOR_SUMMARY_MAX_TOKENS_LARGE,
    TUTOR_SUMMARY_MAX_TOKENS_BATCH,
    TUTOR_SUMMARY_CONTENT_MAX_CHARS,
    TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL,
    TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE,
    TUTOR_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    TUTOR_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    TUTOR_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    TUTOR_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    TUTOR_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    TUTOR_MINDMAP_PROMPT,
)

from src.features.ki_assistent.tasks._helpers import (
    _format_ts,
    _save_ki_tutor_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
)

@celery_app.task(bind=True, name="ki_tutor.generate_exercise_set", queue="ki_tutor",
                 soft_time_limit=120, time_limit=180)
@observe(name="ki-tutor-exercise-set")
def run_generate_exercise_set(self, set_id: int, module_id: int, tool: str,
                              mode: str, count: int, source_uuid: str | None = None,
                              source_uuids: list[str] | None = None):
    """Generate items for an exercise set (lernkarten/lueckentext/vokabeltest)."""
    import json as _json
    import random
    from src.tool_prompts import TUTOR_LERNKARTEN_PROMPT, TUTOR_KARTEIKARTEN_PROMPT

    try:
        module = db.get_ki_tutor_module_by_id(module_id)
        if not module:
            db.fail_exercise_set(set_id)
            return

        items = []
        title = "Wird generiert…"
        client, model, _ = _get_llm_client()

        existing_fronts = db.get_existing_exercise_fronts(module_id, tool)

        def _with_avoid(base_content: str) -> str:
            """Append an 'avoid duplicates' block so the LLM produces variations
            instead of repeating items from earlier sets of the same tool."""
            if not existing_fronts:
                return base_content
            preview = "\n".join(f"- {(f or '')[:160]}" for f in existing_fronts)
            return base_content + (
                "\n\n---\n"
                "Bereits existierende Einträge in diesem Workspace:\n"
                f"{preview}\n\n"
                "Regel: Erstelle UNTERSCHIEDLICHE Einträge, die thematisch NICHT "
                "dasselbe abdecken. Wenn dein Material erschöpft ist und du ein "
                "Thema wiederverwenden musst, erstelle eine klare VARIATION "
                "(anderer Blickwinkel, andere Fragestellung, anderer Schwerpunkt), "
                "keine Wiederholung mit nur umformuliertem Wortlaut."
            )

        if mode == "glossar":
            glossary = db.get_ki_tutor_glossary_by_module(module_id)
            if not glossary:
                db.fail_exercise_set(set_id)
                return
            selected = random.sample(glossary, min(count, len(glossary)))

            if tool == "lernkarten":
                items = [
                    {"front": e["term_de"],
                     "back": f"{e['term_de']} — {e['definition']}",
                     "back_en": f"{e['term_en']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
            elif tool == "karteikarten":
                items = [
                    {"front": e["term_de"], "back": f"{e['term_en']} — {e['definition']}",
                     "source_label": e.get("filename", ""), "page_number": e.get("page_number")}
                    for e in selected
                ]
            elif tool == "lueckentext":
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
                exercises = _json.loads(answer)[:count]
                items = [
                    {"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                     "correct_idx": ex["correct_idx"],
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == ex.get("term_de")), ""),
                     "page_number": ex.get("page_number")}
                    for ex in exercises
                ]
            elif tool == "vokabeltest":
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
                questions = _json.loads(answer)[:count]
                items = [
                    {"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                     "correct_idx": q["correct_idx"], "explanation": q.get("explanation"),
                     "source_label": next((e.get("filename", "") for e in selected if e["term_de"] == q.get("term_de")), ""),
                     "page_number": q.get("page_number")}
                    for q in questions
                ]

            # Generate a short title via LLM from glossary terms
            terms_summary = ", ".join(e["term_de"] for e in selected)
            try:
                title_resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "Gib einen kurzen, prägnanten Titel der das Thema dieser Fachbegriffe zusammenfasst. Antworte NUR mit dem Titel, ohne Anführungszeichen."},
                        {"role": "user", "content": terms_summary},
                    ],
                    temperature=0.3,
                    max_tokens=80,
                )
                title = (title_resp.choices[0].message.content or "").strip().strip('"\'')
                if not title:
                    title = ", ".join(e["term_de"] for e in selected)
            except Exception:
                title = ", ".join(e["term_de"] for e in selected)

        elif mode == "quelle":
            # Support multi-source: prefer source_uuids list, fall back to single source_uuid
            uuids = source_uuids or ([source_uuid] if source_uuid else [])
            if not uuids:
                db.fail_exercise_set(set_id)
                return

            # Build context from all sources
            context_parts: list[str] = []
            first_label = ""
            # Mapping: (source_label, page_number) → start_time for media files
            _time_map: dict[tuple[str, int], float] = {}
            # Mapping: filename → source dict (for chunk lookup in lernkarten)
            _source_by_name: dict[str, dict] = {}
            # Mapping: filename → list[{start,end,text}] of Whisper segments (media sources)
            _segments_by_label: dict[str, list[dict]] = {}
            for suuid in uuids:
                source = db.get_ki_tutor_source(suuid)
                if not source:
                    continue
                source_label = source["filename"]
                _source_by_name[source_label] = source
                if not first_label:
                    first_label = source_label
                # For karteikarten: use raw chunks so LLM can quote verbatim for evidence validation
                # For other tools: use summaries (faster, denser)
                use_chunks = tool == "karteikarten"
                chunks_all = db.get_chunks_by_source(source["id"]) if use_chunks else None
                summaries = None if use_chunks else db.get_paragraph_summaries_by_source(source["id"])
                if use_chunks and chunks_all:
                    for c in chunks_all:
                        if c.get("start_time") is not None:
                            _time_map[(source_label, c["page_number"])] = c["start_time"]
                    # Load Whisper segments once per media source for sub-chunk timestamp resolution
                    if any(c.get("start_time") is not None for c in chunks_all):
                        from src.features.ki_assistent.routes._helpers import _load_transcript_segments
                        _segments_by_label[source_label] = _load_transcript_segments(source)
                    parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks_all]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
                elif summaries:
                    pages_map: dict[int, list[str]] = {}
                    for s in summaries:
                        pages_map.setdefault(s["page_number"], []).append(s["summary"])
                    parts = [f"[{source_label}, S. {p}] {' '.join(texts)}" for p, texts in sorted(pages_map.items())]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
                else:
                    chunks = db.get_chunks_by_source(source["id"])
                    if chunks:
                        for c in chunks:
                            if c.get("start_time") is not None:
                                _time_map[(source_label, c["page_number"])] = c["start_time"]
                        parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks[:30]]
                        context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))

            if not context_parts:
                db.fail_exercise_set(set_id)
                return

            # Fair budget split per source (200k total, whole lines only)
            budget_per_source = 200000 // len(context_parts)
            trimmed: list[str] = []
            for part in context_parts:
                lines = part.split("\n")
                header = lines[0]
                kept = [header]
                size = len(header)
                for line in lines[1:]:
                    if size + len(line) + 1 > budget_per_source:
                        break
                    kept.append(line)
                    size += len(line) + 1
                trimmed.append("\n".join(kept))
            context = "\n\n".join(trimmed)
            multi_label = first_label if len(uuids) == 1 else f"{len(uuids)} Quellen"
            source_hint = "folgender Quelle" if len(uuids) == 1 else "folgenden Quellen"

            def _title_from_items(items_list: list[dict], fallback: str) -> str:
                """Generate a distinct title from the actual item fronts so sets from the
                same source get different titles."""
                if not items_list:
                    return fallback
                preview = "\n".join(
                    f"- {(it.get('front') or '')[:160]}" for it in items_list[:10]
                )
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": (
                                "Gib einen kurzen, prägnanten Titel (max. 6 Wörter) für diese Übung, "
                                "der das konkrete Thema der unten stehenden Einträge widerspiegelt. "
                                "Antworte NUR mit dem Titel, ohne Anführungszeichen."
                            )},
                            {"role": "user", "content": f"Einträge:\n{preview}"},
                        ],
                        temperature=0.7,
                        max_tokens=30,
                    )
                    t = (resp.choices[0].message.content or "").strip().strip('"\'')
                    return t or fallback
                except Exception:
                    return fallback

            import re as _re_card

            def _normalize_chunk(text: str) -> str:
                text = _re_card.sub(r"-\s*\n\s*", "", text)
                text = _re_card.sub(r"\s*\n\s*", " ", text)
                return text.strip()

            def _resolve_segment_start(source_label: str, evidence: str, fallback: float | None) -> float | None:
                """For media sources: find the segment that best contains the evidence text and
                return its start_time. Falls back to the chunk's start_time when no match is found.

                Fixes the common case where a single merged chunk (~1000 chars) spans 60-120s and
                multiple topics — without this, every citation gets the chunk's start, not the moment
                the quote actually appears.
                """
                segments = _segments_by_label.get(source_label) or []
                if not segments or not evidence:
                    return fallback

                def _norm(t: str) -> str:
                    t = _re_card.sub(r"-\s*\n\s*", "", t)
                    t = _re_card.sub(r"[^\w\säöüßÄÖÜ]+", " ", t)
                    t = _re_card.sub(r"\s+", " ", t)
                    return t.strip().lower()

                ev = _norm(evidence)
                if not ev:
                    return fallback

                # Sliding-window match: find the segment whose normalized text maximally overlaps
                # the start of the evidence (the first words tell us where the quote begins).
                ev_words = ev.split()
                probe = " ".join(ev_words[: min(12, len(ev_words))])
                if len(probe) < 8:
                    return fallback
                best: tuple[int, float] | None = None  # (shared_chars, seg_start)
                for i, seg in enumerate(segments):
                    seg_norm = _norm(seg["text"])
                    if not seg_norm:
                        continue
                    if probe in seg_norm:
                        return seg["start"]
                    # If the evidence spans a boundary, look for a suffix match + next-segment prefix
                    overlap = 0
                    for k in range(min(len(seg_norm), len(probe)), 6, -1):
                        if seg_norm.endswith(probe[:k]):
                            overlap = k
                            break
                    if overlap and i + 1 < len(segments):
                        nxt = _norm(segments[i + 1]["text"])
                        if nxt.startswith(probe[overlap:overlap + 40]):
                            return seg["start"]
                    if overlap and (best is None or overlap > best[0]):
                        best = (overlap, seg["start"])
                return best[1] if best else fallback

            def _find_all_pages(search_term: str) -> list[dict]:
                """Find all pages where search_term appears in chunk text."""
                term_lower = search_term.lower()
                if not term_lower:
                    return []
                seen: set[tuple[str, int]] = set()
                result: list[dict] = []
                for sname, src in _source_by_name.items():
                    for ch in db.get_chunks_by_source(src["id"]):
                        key = (sname, ch["page_number"])
                        if key in seen:
                            continue
                        if term_lower in _normalize_chunk(ch["content"]).lower():
                            seen.add(key)
                            chunk_start = _time_map.get(key)
                            seg_start = _resolve_segment_start(sname, search_term, chunk_start)
                            result.append({
                                "source_label": sname,
                                "page_number": ch["page_number"],
                                "start_time": seg_start,
                            })
                # Sort: by filename, then by start_time (media) or page_number
                result.sort(key=lambda s: (
                    s.get("source_label", ""),
                    s.get("start_time") if s.get("start_time") is not None else (s.get("page_number") or 0),
                ))
                return result

            def _parse_card(c: dict, include_back_en: bool = False, search_term: str = "", multi_source: bool = False) -> dict:
                """Parse card. search_term validates/corrects page. multi_source=True stores all pages."""
                sl = c.get("source_label", first_label)
                pn = c.get("page_number")
                item: dict = {
                    "front": c["front"], "back": c["back"],
                    "source_label": sl,
                    "page_number": pn,
                    "start_time": _time_map.get((sl, pn or 0)),
                }
                if include_back_en:
                    item["back_en"] = c.get("back_en", "")
                if search_term:
                    pages = _find_all_pages(search_term)
                    if pages:
                        if multi_source:
                            item["sources"] = pages
                        # Keep LLM-assigned page if it contains the term, otherwise use first match
                        llm_page_valid = any(
                            p["source_label"] == sl and p["page_number"] == pn
                            for p in pages
                        )
                        if not llm_page_valid:
                            item["source_label"] = pages[0]["source_label"]
                            item["page_number"] = pages[0]["page_number"]
                            item["start_time"] = pages[0].get("start_time")
                return item

            if tool == "lernkarten":
                prompt = TUTOR_LERNKARTEN_PROMPT.replace("{count}", str(count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": _with_avoid(f"Erstelle Lernkarten aus {source_hint}:\n\n{context}")},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                data = _json.loads(answer)

                def _format_lernkarte(c: dict) -> dict:
                    """Format lernkarte: begriff/definition in front/back columns, rest in extras JSONB."""
                    begriff = (c.get("begriff") or "").strip()
                    definition = (c.get("definition") or "").strip()
                    # Map semantic names to shared DB columns (front/back) so karteikarten logic stays untouched
                    normalized = {
                        "front": begriff,
                        "back": definition,
                        "back_en": (c.get("begriff_en") or "").strip(),
                        "source_label": c.get("source_label"),
                        "page_number": c.get("page_number"),
                    }
                    item = _parse_card(normalized, include_back_en=True, search_term=begriff, multi_source=True)
                    extras = {
                        k: (c.get(k) or "").strip()
                        for k in ("word_parts", "word_parts_explained", "example_sentence")
                        if (c.get(k) or "").strip()
                    }
                    if extras:
                        item["extras"] = extras
                    return item
                items = [_format_lernkarte(c) for c in data.get("cards", [])][:count]
                title = _title_from_items(items, multi_label)
            elif tool == "karteikarten":
                prompt = TUTOR_KARTEIKARTEN_PROMPT.replace("{count}", str(count))
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": _with_avoid(f"Erstelle Karteikarten aus {source_hint}:\n\n{context}")},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                data = _json.loads(answer)
                def _normalize_for_match(text: str) -> str:
                    """Normalize text for fuzzy substring matching (whitespace, punctuation, case)."""
                    text = _normalize_chunk(text).lower()
                    text = _re_card.sub(r"[^\w\säöüß]+", " ", text)
                    text = _re_card.sub(r"\s+", " ", text)
                    return text.strip()

                def _evidence_matches_page(evidence_norm: str, page_text_norm: str) -> bool:
                    """Check if evidence is fully or partially (6+ consecutive words) contained in page."""
                    if not evidence_norm or not page_text_norm:
                        return False
                    if evidence_norm in page_text_norm:
                        return True
                    ev_words = evidence_norm.split()
                    if len(ev_words) < 6:
                        return False
                    for window in range(min(len(ev_words), 20), 5, -1):
                        for i in range(len(ev_words) - window + 1):
                            phrase = " ".join(ev_words[i:i + window])
                            if phrase in page_text_norm:
                                return True
                    return False

                def _parse_karteikarte(c: dict) -> dict:
                    # Build back text from answer_parts statements
                    answer_parts = c.get("answer_parts") or []
                    back_text = " ".join((p.get("statement") or "").strip() for p in answer_parts if p.get("statement"))
                    c_merged = dict(c)
                    c_merged["back"] = back_text or c.get("back", "")
                    item = _parse_card(c_merged)

                    # Enforce single source per karteikarte
                    sl = c.get("source_label") or first_label
                    src_obj = _source_by_name.get(sl)
                    if not src_obj:
                        return item

                    # Build original page_text lookup (deduped for overlapping chunks)
                    def _build_page_text(chunks: list) -> str:
                        """Concatenate chunks, removing overlap between consecutive chunks."""
                        result = ""
                        for ch in chunks:
                            content = (ch.get("content") or "").strip()
                            if not content:
                                continue
                            if not result:
                                result = content
                                continue
                            # Find overlap: check if last 100 chars of result appear at start of content
                            overlap_max = min(200, len(result), len(content))
                            best_overlap = 0
                            for n in range(overlap_max, 20, -1):
                                if result[-n:] == content[:n]:
                                    best_overlap = n
                                    break
                            if best_overlap > 0:
                                result += content[best_overlap:]
                            else:
                                result += " " + content
                        return result

                    page_chunks_raw: dict[int, list] = {}
                    for ch in db.get_chunks_by_source(src_obj["id"]):
                        page_chunks_raw.setdefault(ch["page_number"], []).append(ch)
                    page_texts: dict[int, str] = {p: _build_page_text(chs) for p, chs in page_chunks_raw.items()}
                    page_texts_norm = {p: _normalize_for_match(t) for p, t in page_texts.items()}


                    # Validate each answer_part's evidence — allow multiple chips per page
                    # but dedupe if two evidences share a long substring (likely the same fact)
                    validated_chips: list[dict] = []
                    seen_norms: list[str] = []

                    def _is_duplicate_evidence(new_norm: str) -> bool:
                        new_words = new_norm.split()
                        if len(new_words) < 4:
                            return new_norm in seen_norms
                        for seen in seen_norms:
                            seen_words = seen.split()
                            # Check if longest common substring is ≥70% of the shorter evidence
                            shorter_len = min(len(new_words), len(seen_words))
                            threshold = max(4, int(shorter_len * 0.7))
                            # Look for any sequence of `threshold` words from new in seen
                            for i in range(len(new_words) - threshold + 1):
                                phrase = " ".join(new_words[i:i + threshold])
                                if phrase in seen:
                                    return True
                        return False

                    for part in answer_parts:
                        ev_text = (part.get("evidence") or "").strip()
                        ev_page = part.get("page_number")
                        if not ev_text or ev_page is None:
                            continue
                        ev_norm = _normalize_for_match(ev_text)
                        if _is_duplicate_evidence(ev_norm):
                            continue
                        target_page: int | None = None
                        if ev_page in page_texts_norm and _evidence_matches_page(ev_norm, page_texts_norm[ev_page]):
                            target_page = ev_page
                        else:
                            for p, pt in page_texts_norm.items():
                                if _evidence_matches_page(ev_norm, pt):
                                    target_page = p
                                    break
                        if target_page is None:
                            continue
                        seen_norms.append(ev_norm)
                        chunk_start = _time_map.get((sl, target_page))
                        seg_start = _resolve_segment_start(sl, ev_text, chunk_start)
                        validated_chips.append({
                            "source_label": sl,
                            "page_number": target_page,
                            "start_time": seg_start,
                            "highlight_text": ev_text,
                        })

                    # Merge all chips on the same page into one (full span from first to last evidence)
                    def _find_orig_span(orig: str, ev_text: str) -> tuple[int, int] | None:
                        """Find a fuzzy position of ev_text inside orig. Returns (start, end) in orig."""
                        orig_norm = _normalize_for_match(orig)
                        ev_norm = _normalize_for_match(ev_text)
                        if not ev_norm:
                            return None
                        # Find position in normalized, then map to original by finding first word
                        pos_norm = orig_norm.find(ev_norm)
                        phrase_len = len(ev_norm)
                        if pos_norm < 0:
                            ev_words = ev_norm.split()
                            if len(ev_words) < 6:
                                return None
                            for window in range(min(len(ev_words), 20), 5, -1):
                                for i in range(len(ev_words) - window + 1):
                                    phrase = " ".join(ev_words[i:i + window])
                                    found = orig_norm.find(phrase)
                                    if found >= 0:
                                        pos_norm = found
                                        phrase_len = len(phrase)
                                        break
                                if pos_norm >= 0:
                                    break
                        if pos_norm < 0:
                            return None
                        # Map norm position to orig position by searching for the first few words
                        first_words = orig_norm[pos_norm:pos_norm + min(40, phrase_len)].split()
                        if not first_words:
                            return None
                        # Search in original for a sequence matching the first word(s)
                        import re as _re_find
                        for first_w in first_words[:3]:
                            if len(first_w) < 3:
                                continue
                            pattern = _re_find.escape(first_w)
                            for m in _re_find.finditer(pattern, orig, _re_find.IGNORECASE):
                                # Verify: the rest of the phrase also matches from here
                                tail_norm = _normalize_for_match(orig[m.start():m.start() + phrase_len + 100])
                                if tail_norm.startswith(orig_norm[pos_norm:pos_norm + min(30, phrase_len)]):
                                    start = m.start()
                                    # End: consume phrase_len worth of non-whitespace chars from original
                                    end = start
                                    consumed_norm = 0
                                    while end < len(orig) and consumed_norm < phrase_len:
                                        if not orig[end].isspace():
                                            consumed_norm += 1
                                        end += 1
                                    return (start, end)
                            break
                        return None

                    def _merge_page_chips(chips: list[dict]) -> list[dict]:
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
                            # Find position of each evidence in the ORIGINAL page text
                            positions: list[tuple[int, int]] = []
                            for ch in page_chips:
                                span = _find_orig_span(page_orig, ch["highlight_text"])
                                if span:
                                    positions.append(span)
                            if not positions:
                                merged.append(page_chips[0])
                                continue
                            span_start = min(p[0] for p in positions)
                            span_end = max(p[1] for p in positions)
                            combined = page_orig[span_start:span_end].strip()
                            # Collapse internal whitespace (keep paragraph breaks)
                            combined = _re_card.sub(r"[ \t]+", " ", combined)
                            combined = _re_card.sub(r" *\n *", "\n", combined)
                            first_ch = page_chips[0]
                            merged.append({
                                "source_label": first_ch["source_label"],
                                "page_number": first_ch["page_number"],
                                "start_time": first_ch.get("start_time"),
                                "highlight_text": combined,
                            })
                        return merged

                    validated_chips = _merge_page_chips(validated_chips)

                    # Sort chips by page number (or start_time for media)
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
                                item["start_time"] = _time_map.get((sl, first_pn))
                    return item
                items = [_parse_karteikarte(c) for c in data.get("cards", [])][:count]
                title = _title_from_items(items, multi_label)
            else:
                tool_prompt = "Du erstellst Übungen basierend auf dem gegebenen Quelltext.\n\n"
                _source_rule = "- Gib für jede Frage source_label und page_number an — die Quelle/Seite aus der der Inhalt stammt.\n"
                if tool == "lueckentext":
                    tool_prompt += (
                        "Erstelle Lückentext-Übungen. Antworte NUR mit einem JSON-Array:\n"
                        '[{"sentence": "Satz mit ___ als Lücke", "answer": "Antwort", '
                        '"options": ["A", "B", "C", "D"], "correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Übungen."
                    )
                elif tool == "quiz":
                    tool_prompt += (
                        "Erstelle Multiple-Choice Verständnisfragen zum gegebenen Text. "
                        "Die Fragen sollen das Verständnis des Inhalts prüfen.\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Verständnisfrage?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Fragen. Mische leichte und schwierige Fragen."
                    )
                else:
                    tool_prompt += (
                        "Erstelle ein Begriffe-Quiz: Multiple-Choice-Fragen zu Fachbegriffen aus dem Quelltext.\n\n"
                        "Identifiziere zuerst die wichtigsten Fachbegriffe im Text, dann erstelle Fragen dazu.\n"
                        "Fragetypen mischen:\n"
                        "- Was bedeutet der Begriff X?\n"
                        "- Wie lautet die englische Übersetzung von X? (bzw. deutsche Übersetzung)\n"
                        "- Welcher Fachbegriff beschreibt folgendes: [Definition]?\n\n"
                        "Wähle Fachbegriffe, die sich gut für Multiple Choice eignen "
                        "(klare Definition, plausible Distraktoren möglich).\n\n"
                        "Antworte NUR mit einem JSON-Array:\n"
                        '[{"question": "Frage zum Fachbegriff?", "options": ["A", "B", "C", "D"], '
                        '"correct_idx": 0, '
                        '"source_label": "Dateiname.pdf", "page_number": 5}]\n'
                        "WICHTIG:\n"
                        "- Verwende KEINE Personennamen in Fragen. Statt 'laut Prof. X' schreibe 'laut Quelle'.\n"
                        + _source_rule +
                        f"Erstelle genau {count} Fragen."
                    )
                messages = [
                    {"role": "system", "content": tool_prompt},
                    {"role": "user", "content": _with_avoid(f"Quellen:\n\n{context}")},
                ]
                response = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
                answer = _clean_llm_json(response.choices[0].message.content or "")
                exercises = _json.loads(answer)
                if isinstance(exercises, list):
                    exercises = exercises[:count]
                # Build page index from context for text matching
                import re as _re
                _page_index: list[tuple[str, int, str]] = []  # (source_label, page, text)
                for line in context.split("\n"):
                    m = _re.match(r"\[(.+?),\s*S\.\s*(\d+)\]\s*(.*)", line)
                    if m:
                        _page_index.append((m.group(1), int(m.group(2)), m.group(3).lower()))

                def _find_page(search_text: str) -> tuple[str, int | None]:
                    """Match exercise text against context lines to find source + page."""
                    words = _re.findall(r"\w+", search_text.lower())
                    if not words or not _page_index:
                        return first_label, None
                    best_label, best_page, best_score = first_label, None, 0
                    for label, page, text in _page_index:
                        score = sum(1 for w in words if w in text)
                        if score > best_score:
                            best_label, best_page, best_score = label, page, score
                    return best_label, best_page

                # Lazy per-source page-text lookup for highlight_text
                _chunks_by_source: dict[str, list] = {}
                def _page_highlight(sl: str | None, pn: int | None) -> str | None:
                    if not sl or pn is None:
                        return None
                    if sl not in _chunks_by_source:
                        src = _source_by_name.get(sl)
                        _chunks_by_source[sl] = db.get_chunks_by_source(src["id"]) if src else []
                    parts = [
                        (ch.get("content") or "").strip()
                        for ch in _chunks_by_source[sl]
                        if ch.get("page_number") == pn and (ch.get("content") or "").strip()
                    ]
                    if not parts:
                        return None
                    return _normalize_chunk(" ".join(parts))

                def _build_item_sources(sl: str, pn: int | None, st: float | None) -> list[dict] | None:
                    highlight = _page_highlight(sl, pn)
                    if not highlight or pn is None:
                        return None
                    return [{
                        "source_label": sl,
                        "page_number": pn,
                        "start_time": st,
                        "highlight_text": highlight,
                    }]

                if tool == "lueckentext":
                    items = []
                    for ex in exercises:
                        sl = ex.get("source_label") or first_label
                        pn = ex.get("page_number")
                        if not pn:
                            sl, pn = _find_page(ex["sentence"] + " " + ex["answer"])
                        st = _time_map.get((sl, pn or 0))
                        items.append({"front": ex["sentence"], "back": ex["answer"], "options": ex["options"],
                            "correct_idx": ex["correct_idx"],
                            "source_label": sl, "page_number": pn,
                            "start_time": st,
                            "sources": _build_item_sources(sl, pn, st)})
                else:  # quiz + vokabeltest
                    items = []
                    for q in exercises:
                        sl = q.get("source_label") or first_label
                        pn = q.get("page_number")
                        if not pn:
                            sl, pn = _find_page(q["question"] + " " + q["options"][q["correct_idx"]])
                        st = _time_map.get((sl, pn or 0))
                        items.append({"front": q["question"], "back": q["options"][q["correct_idx"]], "options": q["options"],
                            "correct_idx": q["correct_idx"],
                            "source_label": sl, "page_number": pn,
                            "start_time": st,
                            "sources": _build_item_sources(sl, pn, st)})
                title = _title_from_items(items, multi_label)

        if not items:
            db.fail_exercise_set(set_id)
            return

        db.finalize_exercise_set(set_id, title, items)
        logger.info("KI Tutor: exercise set {} generated ({} items)", set_id, len(items))

    except Exception as e:
        logger.error("KI Tutor: exercise set {} generation failed: {}", set_id, e)
        db.fail_exercise_set(set_id)

