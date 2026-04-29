"""KI-Assistent routes — glossary + extraction."""

import io
import json
import re
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from langfuse.decorators import langfuse_context, observe

from src import database as db
from src.dependencies import get_current_user, get_kisski_client, is_admin_user
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst
from src.limits import (
    GLOSSARY_LIMIT,
    KIA_SOURCE_MAX_PAGES,
    KIA_WORKSPACE_MAX_SOURCES,
    KIA_WORKSPACE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
)

from src.features.ai_assistant.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_workspace,
    _save_source_file,
    _delete_source_files_for_workspace,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: glossary"])

@router.get("/ai-assistant/workspaces/{workspace_uuid}/glossary")
async def get_glossary(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    entries = db.get_aia_glossary_by_workspace(workspace["id"])
    return {"entries": entries}

@router.post("/ai-assistant/workspaces/{workspace_uuid}/glossary/generate")
async def generate_glossary(
    workspace_uuid: str,
    body: schemas.GlossaryGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    enforce_aia_burst(user_id)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user))

    source_ids = _resolve_source_ids(workspace, body.active_source_ids)

    from src.tasks.aia_tasks import run_generate_glossary
    run_generate_glossary.delay(workspace["id"], source_ids)
    return {"status": "generating"}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/glossary/{entry_id}")
async def delete_glossary_entry_endpoint(
    workspace_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.delete_glossary_entry(entry_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"ok": True}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/glossary")
async def delete_all_glossary_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    count = db.delete_all_glossary_entries(workspace["id"])
    return {"ok": True, "deleted": count}


# ─── Glossary: Aus Markierung extrahieren ─────────────────────────────────────

_GLOSSARY_EXTRACT_PROMPT = """You are a language expert for international students at B1 level. Analyze the highlighted text and extract words/phrases that a B1 learner should learn for university study.

Respond ONLY with a JSON array:
[
  {
    "term_de": "Term in the source language",
    "term_en": "Translation (see rules)",
    "definition": "Short explanation in German (B1 level, 1-2 sentences)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "Example sentence using the term (source language)",
    "example_sentence_en": "English translation of the example sentence"
  }
]

Two categories are allowed (both important for B1 students):
1. Technical terms: domain-specific terminology (e.g. "Arbeitsmarkt", "Integralrechnung", "Curriculum")
2. Academic/educational language: academic nouns, verbs, adjectives, or collocations that go beyond A2/B1 everyday vocabulary (e.g. "Studium", "Voraussetzung", "erhöhen", "entwickeln", "berücksichtigen", "Erkenntnis")

Rules:
- DO NOT extract: pure function words (und, oder, aber, ist, der, die, das, ein, eine, er, sie, es, im, zu, mit, von, für, auf, etc.), trivial A1/A2 everyday words (Haus, Tag, gehen, machen, gut, schön)
- CRITICAL for term_de: the term must appear VERBATIM as a contiguous word or phrase in the text. If the text says "in den deutschen Arbeitsmarkt zu integrieren", you may NOT turn that into "Arbeitsmarktintegration". Take "Arbeitsmarkt" or "integrieren" instead. Do NOT invent compounds or nominalizations that are not exactly in the text.
- For inflected verbs/adjectives: the base form as term_de is allowed when the form in the text is clearly recognizable (e.g. text "zu erhöhen" -> term_de "erhöhen" is fine).
- term_en: if the source text is NOT English, translate to English. If the source text is English, translate to German. Never the same language as term_de.
- definition: simple explanation in German, understandable at B1 level
- definition_en: simple explanation in English, understandable at B1 level
- example_sentence_en: English translation of the example sentence
- At most 5 terms per selection; prioritize the ones most difficult at B1
- If the text really only contains function words / trivial vocabulary, respond with: []
- Respond ONLY with the JSON array."""

@router.post("/ai-assistant/workspaces/{workspace_uuid}/glossary/extract")
async def extract_glossary_from_selection(
    workspace_uuid: str,
    body: schemas.GlossaryExtractBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    """Extract glossary terms from a PDF text selection."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    enforce_aia_burst(user_id)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user))

    # Check glossary limit
    current_count = db.get_glossary_count(workspace["id"])
    if current_count >= GLOSSARY_LIMIT:
        return {"added": 0, "message": "Glossary voll (150 / 150) — entferne Begriffe um neue hinzuzufügen."}

    # Truncate to 300 chars
    text = body.text[:300].strip()
    if not text:
        return {"added": 0, "message": "Kein Text markiert."}

    # Find the source
    source = db.get_aia_source(body.source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    # Get existing terms to avoid duplicates
    existing = db.get_aia_glossary_by_workspace(workspace["id"])
    existing_terms = {e["term_de"].lower() for e in existing}

    # Ask LLM to extract terms
    try:
        messages = [
            {"role": "system", "content": _GLOSSARY_EXTRACT_PROMPT},
            {"role": "user", "content": f"Markierter Text:\n\n{text}"},
        ]
        response = kisski._client.chat.completions.create(
            model=kisski._model, messages=messages, temperature=0.2,
            **(kisski._extra_body and {"extra_body": kisski._extra_body} or {}),
        )
        answer = response.choices[0].message.content.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        terms = json.loads(answer)
        if not isinstance(terms, list):
            return {"added": 0, "message": "Keine lernenswerten Begriffe in der Markierung gefunden."}

        # Filter: must appear in source text, no duplicates
        text_lower = text.lower()
        remaining_slots = GLOSSARY_LIMIT - current_count
        new_entries = []
        for t in terms[:5]:
            if not t.get("term_de"):
                continue
            term = t["term_de"]
            if not _term_appears_in_text(term, text_lower):
                continue
            if term.lower() in existing_terms:
                continue
            new_entries.append({
                "term_de": t["term_de"],
                "term_en": t.get("term_en", ""),
                "definition": t.get("definition", ""),
                "definition_en": t.get("definition_en", ""),
                "example_sentence": t.get("example_sentence", ""),
                "example_sentence_en": t.get("example_sentence_en", ""),
                "page_number": body.page_number,
            })
            existing_terms.add(t["term_de"].lower())
            if len(new_entries) >= remaining_slots:
                break

        if not new_entries:
            if existing_terms and any(t.get("term_de", "").lower() in existing_terms for t in terms):
                return {"added": 0, "message": "Die erkannten Begriffe sind bereits im Glossary."}
            return {"added": 0, "message": "Keine neuen lernenswerten Begriffe in der Markierung gefunden."}

        db.bulk_create_glossary_entries(source["id"], new_entries)
        count = len(new_entries)
        return {
            "added": count,
            "message": f"{count} Begriff{'e' if count > 1 else ''} zum Glossary hinzugefügt.",
            "entries": new_entries,
        }
    except (json.JSONDecodeError, ValueError):
        return {"added": 0, "message": "Keine lernenswerten Begriffe in der Markierung gefunden."}
    except Exception as e:
        logger.error("Glossary extract error: {}", e)
        raise HTTPException(status_code=500, detail="Extraktion fehlgeschlagen")


# ─── Mindmap generieren ──────────────────────────────────────────────────────

