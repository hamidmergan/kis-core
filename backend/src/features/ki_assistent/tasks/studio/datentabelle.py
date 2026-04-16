"""KI-Assistent Celery tasks — datentabelle generation."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    KIA_SUMMARY_MAX_RETRIES,
    KIA_SUMMARY_TIMEOUT_SMALL,
    KIA_SUMMARY_TIMEOUT_LARGE,
    KIA_SUMMARY_MAX_TOKENS_SMALL,
    KIA_SUMMARY_MAX_TOKENS_LARGE,
    KIA_SUMMARY_MAX_TOKENS_BATCH,
    KIA_SUMMARY_CONTENT_MAX_CHARS,
    KIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    KIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    KIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    KIA_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    KIA_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    KIA_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    KIA_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    KIA_MINDMAP_PROMPT,
)

from src.features.ki_assistent.tasks._helpers import (
    _format_ts,
    _save_kia_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
)

@celery_app.task(bind=True, name="kia.generate_datentabelle", queue="kia",
                 soft_time_limit=120, time_limit=180)
@observe(name="kia-datentabelle")
def run_generate_datentabelle(self, datentabelle_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict):
    """Generate a data table from source chunks as a background job."""
    import json as _json
    from src.tool_prompts import KIA_DATENTABELLE_PROMPT

    try:
        db.update_kia_datentabelle(datentabelle_id, "running")
        logger.info("KI Tutor: generating datentabelle {}", datentabelle_id)

        # Build context with source filenames for citations
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}
        context_parts: list[str] = []
        context_len = 0
        for sid, suuid in zip(source_ids, source_uuids):
            chunks = db.get_chunks_by_source(sid)
            src_info = source_map.get(str(sid), {})
            filename = src_info.get("filename", f"Quelle {src_info.get('number', '?')}")
            is_media = any(filename.lower().endswith(ext) for ext in _MEDIA_EXTS)
            for chunk in chunks:
                if is_media and chunk.get("start_time") is not None:
                    st = chunk["start_time"]
                    h, m, s = int(st // 3600), int((st % 3600) // 60), int(st % 60)
                    ts = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"
                    part = f"[{filename}, {ts}]\n{chunk['content']}"
                else:
                    part = f"[{filename}, S. {chunk['page_number']}]\n{chunk['content']}"
                if context_len + len(part) > 200000:
                    break
                context_parts.append(part)
                context_len += len(part)

        if not context_parts:
            db.update_kia_datentabelle(datentabelle_id, "failed", error="Keine Chunks vorhanden")
            return

        context = "\n\n---\n\n".join(context_parts)

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": KIA_DATENTABELLE_PROMPT},
            {"role": "user", "content": (
                f"Erstelle eine strukturierte Datentabelle aus folgendem Text:\n\n{context}"
            )},
        ]

        response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        raw = response.choices[0].message.content
        if not raw:
            db.update_kia_datentabelle(datentabelle_id, "failed", error="LLM returned empty content")
            return

        table_data = _json.loads(_clean_llm_json(raw))
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            db.update_kia_datentabelle(datentabelle_id, "failed", error="Invalid table format")
            return

        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]
        title = table_data.get("title", "Datentabelle")

        db.update_kia_datentabelle(datentabelle_id, "success",
                                        title=title, table_data=table_data, sources=sources_list)
        logger.info("KI Tutor: datentabelle {} generated successfully", datentabelle_id)

    except Exception as e:
        logger.error("KI Tutor: datentabelle {} generation failed: {}", datentabelle_id, e)
        db.update_kia_datentabelle(datentabelle_id, "failed", error=str(e))


# ── Glossary generation ──────────────────────────────────────────────────────

_GLOSSARY_PROMPT = """Du bist ein Fachsprachen-Experte. Extrahiere die wichtigsten Fachbegriffe aus dem folgenden Text.

Die Textausschnitte sind mit Quellenangaben markiert: [Q1, S. 5] = Quelle 1, Seite 5.

Für jeden Begriff gib EXAKT dieses JSON-Format zurück (als JSON-Array):
[
  {
    "term_de": "Fachbegriff in der Quellsprache",
    "term_en": "Übersetzung (siehe Regeln)",
    "definition": "Kurze Erklärung auf Deutsch (B1 Niveau, 1-2 Sätze)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "Ein Satz aus dem Text, der den Begriff verwendet",
    "example_sentence_en": "English translation of the example sentence",
    "source_label": "Q1",
    "page_number": 5
  }
]

Regeln:
- Extrahiere 10-20 Fachbegriffe (die wichtigsten und häufigsten)
- Nur echte Fachbegriffe, keine allgemeinen Wörter
- KRITISCH für term_de: Der Begriff muss WÖRTLICH als zusammenhängendes Wort oder Phrase im Text vorkommen. Wenn der Text "in den deutschen Arbeitsmarkt zu integrieren" sagt, darfst du NICHT "Arbeitsmarktintegration" daraus machen. Nimm stattdessen "Arbeitsmarkt" oder lass es weg. Erfinde KEINE Komposita oder Nominalisierungen die nicht exakt so im Text stehen.
- term_en: Wenn der Quelltext NICHT auf Englisch ist, übersetze den Begriff ins Englische. Wenn der Quelltext auf Englisch ist, übersetze den Begriff ins Deutsche. Niemals die gleiche Sprache wie term_de verwenden!
- definition: Einfache Erklärung auf Deutsch, verständlich auf B1-Sprachniveau
- definition_en: Einfache Erklärung auf Englisch, verständlich auf B1-Sprachniveau
- example_sentence: Ein Satz aus dem gegebenen Text, der den Begriff verwendet
- example_sentence_en: Englische Übersetzung dieses Satzes
- source_label: Die Quellenangabe (Q1, Q2, ...) aus der der Begriff stammt
- page_number ist die Seitenzahl, auf der der Begriff vorkommt
- Antworte NUR mit dem JSON-Array, kein anderer Text"""

