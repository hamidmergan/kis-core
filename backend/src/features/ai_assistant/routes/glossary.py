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
from src.dependencies import get_current_user, get_kisski_client
from src.limits import (
    GLOSSARY_LIMIT,
    KIA_SOURCE_MAX_PAGES,
    KIA_MODULE_MAX_SOURCES,
    KIA_MODULE_MAX_ACCESS_LINKS,
    KIA_NOTES_MAX_PER_USER,
)
from src.storage import USE_S3, delete_file, file_exists, get_file, save_file
from src.tool_prompts import (
    KIA_SYSTEM_DIRECT,
    KIA_SYSTEM_DIRECT_WITH_CONTEXT,
    KIA_SYSTEM_RAG,
    KIA_POPUP_ACTIONS,
)

from src.features.ki_assistent.routes._helpers import (
    _trace_kisski,
    _convert_office_to_pdf,
    _count_pages,
    _format_timestamp,
    _require_own_module,
    _save_source_file,
    _delete_source_files_for_module,
    _strip_image_text_layer,
    _markdown_fallback,
    _resolve_source_ids,
    _term_appears_in_text,
    _ALLOWED_EXTENSIONS,
    _MEDIA_EXTENSIONS,
    _MAX_UPLOAD_BYTES,
)
from src.features.ki_assistent import schemas

router = APIRouter(tags=["ki-assistent"])

@router.get("/ki-assistent/modules/{module_uuid}/glossary")
async def get_glossary(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    entries = db.get_kia_glossary_by_module(module["id"])
    return {"entries": entries}

@router.post("/ki-assistent/modules/{module_uuid}/glossary/generate")
async def generate_glossary(
    module_uuid: str,
    body: schemas.GlossaryGenerateBody,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source_ids = _resolve_source_ids(module, body.active_source_ids)

    from src.tasks.kia_tasks import run_generate_glossary
    run_generate_glossary.delay(module["id"], source_ids)
    return {"status": "generating"}

@router.delete("/ki-assistent/modules/{module_uuid}/glossary/{entry_id}")
async def delete_glossary_entry_endpoint(
    module_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
):
    if not db.delete_glossary_entry(entry_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"ok": True}

@router.delete("/ki-assistent/modules/{module_uuid}/glossary")
async def delete_all_glossary_endpoint(
    module_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    count = db.delete_all_glossary_entries(module["id"])
    return {"ok": True, "deleted": count}


# ─── Glossar: Aus Markierung extrahieren ─────────────────────────────────────

_GLOSSARY_EXTRACT_PROMPT = """Du bist ein Sprachexperte für internationale Studierende auf B1-Niveau. Analysiere den markierten Text und extrahiere daraus Wörter/Phrasen, die ein B1-Lerner für das Studium lernen sollte.

Antworte NUR mit einem JSON-Array:
[
  {
    "term_de": "Begriff in der Quellsprache",
    "term_en": "Übersetzung (siehe Regeln)",
    "definition": "Kurze Erklärung auf Deutsch (B1 Niveau, 1-2 Sätze)",
    "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
    "example_sentence": "Beispielsatz mit dem Begriff",
    "example_sentence_en": "English translation of the example sentence"
  }
]

Zwei Kategorien sind erlaubt (beide für B1-Studierende wichtig):
1. **Fachbegriffe**: Domänenspezifische Termini (z.B. "Arbeitsmarkt", "Integralrechnung", "Curriculum")
2. **Wissenschafts-/Bildungssprache**: Akademische Nomen, Verben, Adjektive oder Kollokationen, die über A2/B1-Alltagswortschatz hinausgehen (z.B. "Studium", "Voraussetzung", "erhöhen", "entwickeln", "berücksichtigen", "Erkenntnis")

Regeln:
- NICHT extrahieren: reine Funktionswörter (und, oder, aber, ist, der, die, das, ein, eine, er, sie, es, im, zu, mit, von, für, auf, etc.), triviale A1/A2-Alltagswörter (Haus, Tag, gehen, machen, gut, schön)
- KRITISCH für term_de: Der Begriff muss WÖRTLICH als zusammenhängendes Wort oder Phrase im Text vorkommen. Wenn der Text "in den deutschen Arbeitsmarkt zu integrieren" sagt, darfst du NICHT "Arbeitsmarktintegration" daraus machen. Nimm stattdessen "Arbeitsmarkt" oder "integrieren". Erfinde KEINE Komposita oder Nominalisierungen die nicht exakt so im Text stehen.
- Bei Verben/Adjektiven in Flexion: Grundform als term_de ist erlaubt, wenn die Wortform im Text klar erkennbar ist (z.B. Text "zu erhöhen" → term_de "erhöhen" ist OK).
- term_en: Wenn der Quelltext NICHT auf Englisch ist, übersetze ins Englische. Wenn der Quelltext auf Englisch ist, übersetze ins Deutsche. Niemals die gleiche Sprache wie term_de!
- definition: Einfache Erklärung auf Deutsch, verständlich auf B1-Sprachniveau
- definition_en: Einfache Erklärung auf Englisch, verständlich auf B1-Sprachniveau
- example_sentence_en: Englische Übersetzung des Beispielsatzes
- Maximal 5 Begriffe pro Markierung, priorisiere die für B1 schwierigsten
- Wenn der Text wirklich nur Funktionswörter/Trivialwortschatz enthält, antworte mit: []
- Antworte NUR mit dem JSON-Array"""

@router.post("/ki-assistent/modules/{module_uuid}/glossary/extract")
async def extract_glossary_from_selection(
    module_uuid: str,
    body: schemas.GlossaryExtractBody,
    current_user: dict = Depends(get_current_user),
    kisski=Depends(get_kisski_client),
):
    """Extract glossary terms from a PDF text selection."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    # Check glossary limit
    current_count = db.get_glossary_count(module["id"])
    if current_count >= GLOSSARY_LIMIT:
        return {"added": 0, "message": "Glossar voll (150 / 150) — entferne Begriffe um neue hinzuzufügen."}

    # Truncate to 300 chars
    text = body.text[:300].strip()
    if not text:
        return {"added": 0, "message": "Kein Text markiert."}

    # Find the source
    source = db.get_kia_source(body.source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Quelle nicht gefunden")

    # Get existing terms to avoid duplicates
    existing = db.get_kia_glossary_by_module(module["id"])
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
                return {"added": 0, "message": "Die erkannten Begriffe sind bereits im Glossar."}
            return {"added": 0, "message": "Keine neuen lernenswerten Begriffe in der Markierung gefunden."}

        db.bulk_create_glossary_entries(source["id"], new_entries)
        count = len(new_entries)
        return {
            "added": count,
            "message": f"{count} Begriff{'e' if count > 1 else ''} zum Glossar hinzugefügt.",
            "entries": new_entries,
        }
    except (json.JSONDecodeError, ValueError):
        return {"added": 0, "message": "Keine lernenswerten Begriffe in der Markierung gefunden."}
    except Exception as e:
        logger.error("Glossary extract error: {}", e)
        raise HTTPException(status_code=500, detail="Extraktion fehlgeschlagen")


# ─── Mindmap generieren ──────────────────────────────────────────────────────

