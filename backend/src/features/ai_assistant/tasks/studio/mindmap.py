"""AI assistant Celery tasks: mindmap generation."""

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.tool_prompts import AIA_MINDMAP_PROMPT

@celery_app.task(bind=True, name="aia.generate_mindmap", queue="aia",
                 soft_time_limit=300, time_limit=360)
@observe(name="aia-mindmap")
def run_generate_mindmap(self, mindmap_id: int, source_ids: list[int], source_uuids: list[str],
                          locale: str = "de", _aia_job_uuid: str | None = None):
    """Generate a mindmap from source chunks as a background job.

    `locale` controls the label language (topic/labels); 'keyword' stays verbatim
    in the source language for highlighting. Defaults to 'de' for older queued tasks.
    `_aia_job_uuid` is set by the shared-pool dispatcher; when present we report
    completion so the freed slot is filled.
    """
    import json as _json

    language = "English" if (locale or "").lower().startswith("en") else "German"

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

        messages = [
            {"role": "system", "content": AIA_MINDMAP_PROMPT.replace("{language}", language)},
            {"role": "user", "content": f"/no_think\nCreate a mind map from the following sources. Write topic and labels in {language}:\n\n{context}"},
        ]

        # Retry once on malformed JSON - a re-roll almost always parses, so a
        # single flaky generation no longer fails the whole mind map.
        mindmap = None
        for attempt in range(2):
            response = client.chat.completions.create(
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

        db.update_aia_mindmap(mindmap_id, "success", mindmap=mindmap)
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


# --- Presentation generation (NotebookLM-style + FLUX images) ---------------

# NotebookLM-inspired slide prompt: clean, statement-driven, icon-aware layouts
_PRES_PROMPT = (
    "Du erstellst eine professionelle Präsentation im Stil von Google NotebookLM: clean, modern, viel Whitespace, "
    "große fette Aussagesätze als Titel (KEINE generischen Titel wie 'Überblick' - stattdessen 'Warum dieses Projekt den Unterschied macht.').\n\n"
    "Antworte NUR mit JSON:\n"
    "{\n"
    '  "title": "Präsentationstitel",\n'
    '  "slides": [\n'
    '    {"layout": "deckblatt", "title": "Große Aussage als Titel", "subtitle": "Ergänzender Untertitel", "image_prompt": "..."},\n'
    '    {"layout": "kapitel", "number": "1", "title": "Abschnittstitel", "subtitle": "Kurzbeschreibung"},\n'
    '    {"layout": "statement", "title": "Eine starke Aussage als ganzer Satz.", "body": "2-3 Sätze Erklärung dazu."},\n'
    '    {"layout": "content", "title": "Aussage als Titel.", "bullets": ["Punkt 1", "Punkt 2", "Punkt 3"], "image_prompt": "..."},\n'
    '    {"layout": "icon_grid", "title": "Vier Vorteile auf einen Blick.", "items": [\n'
    '      {"title": "Punkt A", "body": "Kurze Erklärung in 1-2 Sätzen."},\n'
    '      {"title": "Punkt B", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt C", "body": "Kurze Erklärung."},\n'
    '      {"title": "Punkt D", "body": "Kurze Erklärung."}\n'
    '    ]},\n'
    '    {"layout": "vergleich", "title": "Vergleich als Aussage.", "left_title": "Option A", "left_bullets": ["..."], "right_title": "Option B", "right_bullets": ["..."]},\n'
    '    {"layout": "zitat", "title": "Kontextüberschrift", "quote": "Zitattext oder Kernaussage.", "body": "Erklärung dazu."},\n'
    '    {"layout": "zweispalten", "title": "Gegenüberstellung.", "left_bullets": ["Links 1", "Links 2"], "right_bullets": ["Rechts 1", "Rechts 2"]},\n'
    '    {"layout": "statistik", "title": "Die Zahlen sprechen für sich.", "stats": [{"value": "42%", "label": "Label", "description": "Beschreibung"}]},\n'
    '    {"layout": "zeitstrahl", "title": "In drei Schritten zum Ziel.", "steps": [{"label": "Schritt 1", "description": "Beschreibung"}]},\n'
    '    {"layout": "zusammenfassung", "title": "Kernbotschaft.", "bullets": ["Fazit 1", "Fazit 2", "Fazit 3"]},\n'
    '    {"layout": "abschluss", "title": "Vielen Dank.", "subtitle": "Kontaktinfo oder Schlusswort"}\n'
    "  ]\n"
    "}\n\n"
    "Layouts (12 verfügbar):\n"
    "- deckblatt: Titelfolie (1x am Anfang). image_prompt = englischer Prompt für Illustration.\n"
    "- kapitel: Abschnittstrenner mit großer Zahl (1, 2, 3...) + Titel + Beschreibung. Dunkler Hintergrund.\n"
    "- content: Aussage-Titel + 3-5 Bullet Points (max 12 Wörter/Punkt) + optional image_prompt.\n"
    "- statement: Große fette Aussage + Fließtext. Kein Bild, keine Bullets.\n"
    "- icon_grid: 2x2 Raster mit 4 Punkten (je title + body). Für Vorteile, Features, Übersichten.\n"
    "- vergleich: Zwei Boxen nebeneinander mit Titel + Bullets pro Seite.\n"
    "- zitat: Hervorgehobenes Zitat/Kernaussage in Box + erklärende Beschreibung.\n"
    "- zweispalten: Zwei Spalten nebeneinander mit left_bullets/right_bullets.\n"
    "- statistik: Große Zahlen/Statistiken (bis 3 stats mit value + label + description).\n"
    "- zeitstrahl: Nummerierte Schritte/Prozess (steps mit label + description, max 6).\n"
    "- zusammenfassung: Vorletzte Folie mit Kernaussagen als Bullets.\n"
    "- abschluss: Letzte Folie (1x am Ende) mit Schlussbotschaft (title + subtitle).\n\n"
    "Regeln:\n"
    "- {slide_count} Folien (inkl. Deckblatt + Abschluss)\n"
    "- Titel sind IMMER vollständige Aussagesätze mit Punkt am Ende.\n"
    "- Mische die Layouts - NICHT nur 'content' Folien!\n"
    "- STICHPUNKTE statt Fließtext - max 6-8 Wörter pro Bullet. Keine ganzen Sätze in Bullets.\n"
    "- Max 5-6 Bullets pro Content-Folie. Lieber eine Folie mehr als zu viele Punkte.\n"
    "- Verwende kapitel-Folien um größere Abschnitte zu markieren.\n"
    "- icon_grid für Übersichten mit 4 gleichwertigen Punkten.\n"
    "- statement für einzelne starke Aussagen.\n"
    "- zitat für wichtige Zitate oder Kernbotschaften.\n"
    "- statistik wenn es harte Zahlen/Daten gibt.\n"
    "- zeitstrahl für Prozesse, Abläufe, Schritte.\n"
    "- zweispalten für Gegenüberstellungen oder parallele Informationen.\n"
    "- Erste Folie IMMER 'deckblatt', letzte IMMER 'abschluss'.\n"
    "- image_prompt: Nur bei deckblatt und content. Englisch. Stil: 'flat vector illustration, people in modern setting, warm muted colors, white background, no text'. Max 3 Bilder total.\n"
    "- Texte EXAKT aus der Source - keine Umformulierungen, keine Rechtschreibfehler.\n"
    "- Sprache = Sprache der Source.\n"
    "- Antworte NUR mit JSON."
)



# -- Shared helpers for exercise / data table / glossary generation ----------

