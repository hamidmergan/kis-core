"""AI assistant Celery tasks: mindmap generation."""

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
from src import database as db
from src.features.ai_assistant.prompts.studio_prompts import AIA_MINDMAP_PROMPT
from src.services.aia_adaptive_tools import build_adaptive_tool_suffix
from src.services.llm_context_healing import create_with_shrink

@celery_app.task(bind=True, name="aia.generate_mindmap", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-mindmap")
def run_generate_mindmap(self, mindmap_id: int, source_ids: list[int], source_uuids: list[str],
                          locale: str = "de", _aia_job_uuid: str | None = None,
                          user_id: int | None = None):
    """Generate a mindmap from source chunks as a background job.

    `locale` controls the label language (topic/labels); 'keyword' stays verbatim
    in the source language for highlighting. Defaults to 'de' for older queued tasks.
    `_aia_job_uuid` is set by the shared-pool dispatcher; when present we report
    completion so the freed slot is filled.
    `user_id` drives the adaptive language level (topic/labels pitched at the
    learner's CEFR level); None for older queued tasks keeps the shipped register.
    """
    import json as _json

    from src.features.ai_assistant.tasks._helpers import learning_tools_language
    # Wie bei Karteikarten und Quiz: der erzeugte Inhalt folgt der Sprache, die die
    # Verwaltung eingestellt hat, nicht der Sprachwahl der Person.
    _, language = learning_tools_language()

    try:
        db.update_aia_mindmap(mindmap_id, "running")
        logger.info("KI Tutor: generating mindmap {}", mindmap_id)

        # 1. Build context from chunks
        from pathlib import Path as _Path
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}

        def _fmt_time(seconds: float) -> str:
            s = int(seconds)
            h, s = divmod(s, 3600)
            m, s = divmod(s, 60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        context_parts: list[str] = []
        # Media sources keep their chunks here so we can later turn a node's keyword into a real
        # timestamp (the model emits a bogus integer page for audio/video, see post-process below).
        media_chunks_by_label: dict[str, list] = {}
        for sid, suuid in zip(source_ids, source_uuids):
            source = db.get_aia_source(suuid)
            source_label = source["filename"] if source else "Source"
            is_media = _Path(source_label).suffix.lower() in _MEDIA_EXTS if source else False

            if is_media:
                # For media: use chunks with start_time as label
                chunks = db.get_chunks_by_source(sid)
                if chunks:
                    media_chunks_by_label[source_label] = chunks
                    parts = []
                    for c in chunks:
                        st = c.get("start_time")
                        time_label = _fmt_time(st) if st is not None else f"Teil {c['page_number']}"
                        parts.append(f"[{source_label}, {time_label}] {c['content']}")
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))
            else:
                chunks = db.get_chunks_by_source(sid)
                if chunks:
                    parts = [f"[{source_label}, S. {c['page_number']}] {c['content']}" for c in chunks]
                    context_parts.append(f"--- {source_label} ---\n" + "\n".join(parts))

        if not context_parts:
            db.update_aia_mindmap(mindmap_id, "failed", error="Keine Inhalte vorhanden")
            return

        # Fair budget split per source from the admin tool-context setting (whole chunk lines
        # only). No fixed chunk cap anymore: each document is filled from the start until its
        # share is full, so a long source contributes far more than the old 20-chunk limit and
        # the map covers more than just the front of the document.
        from src.features.ai_assistant.tasks._context_budget import tool_context_budget
        budget_per_source = max(1000, tool_context_budget() // max(1, len(source_ids)))
        trimmed_parts: list[str] = []
        for part in context_parts:
            lines = part.split("\n")
            header = lines[0]  # "--- filename ---"
            kept = [header]
            size = len(header)
            for line in lines[1:]:
                if size + len(line) + 1 > budget_per_source:
                    break
                kept.append(line)
                size += len(line) + 1
            trimmed_parts.append("\n".join(kept))
        context = "\n\n".join(trimmed_parts)

        # 2. Call LLM
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        _api_key, _base_url, _model, _provider = _resolve_llm_provider()
        client = OpenAI(api_key=_api_key, base_url=_base_url, max_retries=0, timeout=240)
        model = _model
        langfuse_context.update_current_observation(
            metadata={"provider": _provider, "base_url": _base_url, "model": model},
        )

        # Workspace comes from the sources: the adaptive suffix is gated on the
        # Fachsprachentrainer being on there, exactly like the chat.
        _first_source = db.get_aia_source(source_uuids[0]) if source_uuids else None
        adaptive_suffix = build_adaptive_tool_suffix(
            user_id, (_first_source or {}).get("workspace_id"),
        )
        messages = [
            {"role": "system", "content": AIA_MINDMAP_PROMPT.replace("{language}", language) + adaptive_suffix},
            {"role": "user", "content": f"/no_think\nCreate a mind map from the following sources. Write topic and labels in {language}:\n\n{context}"},
        ]

        # Retry once on malformed JSON - a re-roll almost always parses, so a
        # single flaky generation no longer fails the whole mind map.
        mindmap = None
        for attempt in range(2):
            response = create_with_shrink(
                client,
                model=model,
                messages=messages,
                temperature=0.2,
            )
            msg = response.choices[0].message
            raw = msg.content or getattr(msg, "reasoning_content", None)
            if not raw:
                continue

            answer = raw.strip()
            if answer.startswith("```"):
                answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            # Strip leading thinking tags if model wrapped output
            if answer.startswith("<think>"):
                think_end = answer.find("</think>")
                if think_end != -1:
                    answer = answer[think_end + 8:].strip()

            try:
                mindmap = _json.loads(answer)
                break
            except _json.JSONDecodeError as e:
                logger.warning("mindmap {} JSON parse failed (attempt {}/2): {}", mindmap_id, attempt + 1, e)

        if mindmap is None:
            db.update_aia_mindmap(mindmap_id, "failed", error="LLM returned unparseable JSON")
            return
        if not isinstance(mindmap, dict) or "topic" not in mindmap:
            db.update_aia_mindmap(mindmap_id, "failed", error="Invalid mindmap format")
            return

        # Fix media citations only. For audio/video nodes the model emits an integer page_number
        # (a guess that doesn't even match the real time), which the UI then renders as "S. 7".
        # Replace it with a REAL timestamp by finding the node's verbatim keyword in the transcript
        # (plain text match, no embeddings). No keyword match -> drop the bogus number so nothing
        # wrong is shown. PDF nodes are left exactly as the model produced them.
        def _fix_media_nodes(node):
            if isinstance(node, dict):
                label = node.get("source_label")
                chunks = media_chunks_by_label.get(label) if label else None
                if chunks is not None:  # node cites a media source
                    kw = (node.get("keyword") or "").strip().lower()
                    ts = None
                    if kw:
                        for c in chunks:
                            if c.get("start_time") is not None and kw in (c.get("content") or "").lower():
                                ts = _fmt_time(c["start_time"])
                                break
                    if ts is not None:
                        node["page_number"] = ts
                    else:
                        node.pop("page_number", None)
                for ch in (node.get("children") or []):
                    _fix_media_nodes(ch)

        _fix_media_nodes(mindmap)

        # Der Name kommt aus den Knoten der ersten Ebene, nicht aus dem Wurzelknoten.
        # Der Wurzelknoten ist der Dokumentname, und zwei Mindmaps derselben Quelle
        # hiessen damit gleich. Kosmetik: schlaegt der Aufruf fehl, bleibt es beim
        # Wurzelknoten, die Mindmap ist deshalb nicht weniger brauchbar.
        from src.features.ai_assistant.tasks._titles import resolve_title
        from src.features.ai_assistant.tasks.studio._result_title import (
            mindmap_entries, recent_titles,
        )

        titel = None
        try:
            _ws = (_first_source or {}).get("workspace_id")
            titel = resolve_title(
                client, model,
                recent_titles("aia_mindmaps", _ws),
                (mindmap.get("topic") or "").strip(),
                mindmap_entries(mindmap),
            ) or None
        except Exception as e:  # noqa: BLE001
            logger.warning("KI Tutor: mindmap {} behaelt ihren Wurzelknoten als Namen: {}", mindmap_id, e)

        db.update_aia_mindmap(mindmap_id, "success", mindmap=mindmap, title=titel)
        logger.info("KI Tutor: mindmap {} generated successfully", mindmap_id)

    except Exception as e:
        logger.error("KI Tutor: mindmap {} generation failed: {}", mindmap_id, e)
        db.update_aia_mindmap(mindmap_id, "failed", error=str(e))
    finally:
        if _aia_job_uuid:
            try:
                from src.features.ai_assistant.scheduling.service import on_complete
                on_complete(_aia_job_uuid)
            except Exception as e:
                logger.error("KI Tutor: mindmap dispatch on_complete failed: {}", e)





# -- Shared helpers for exercise / data table / glossary generation ----------

