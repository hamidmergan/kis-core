"""KI-Assistent routes - glossary + extraction."""

import asyncio
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger


from src import database as db
from src.dependencies import get_current_user, get_llm_client, is_admin_user
from src.i18n import get_locale, t
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_aia_burst
from src.limits import (
    GLOSSARY_LIMIT,
)

from src.features.ai_assistant.routes._helpers import (
    _term_appears_in_text,
)
from src.features.ai_assistant import schemas

router = APIRouter(tags=["ki-assistent: glossary"])

@router.get("/ai-assistant/workspaces/{workspace_uuid}/glossary")
async def get_glossary(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    entries = db.get_aia_glossary_by_workspace(workspace["id"], user_id)
    return {"entries": entries}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/glossary/{entry_id}")
async def delete_glossary_entry_endpoint(
    workspace_uuid: str,
    entry_id: int,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    if not db.delete_glossary_entry(entry_id, user_id):
        raise HTTPException(status_code=404, detail=t("entry.notFound", locale))
    return {"ok": True}

@router.delete("/ai-assistant/workspaces/{workspace_uuid}/glossary")
async def delete_all_glossary_endpoint(
    workspace_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    count = db.delete_all_glossary_entries(workspace["id"], user_id)
    return {"ok": True, "deleted": count}


# ─── Glossary: Aus Markierung extrahieren ─────────────────────────────────────

_GLOSSARY_SINGLE_PROMPT = """You are a language expert for international students at B1 level. The user has manually selected ONE specific term/phrase to add to their glossary.

Respond ONLY with a JSON object describing this exact term. Do NOT split compounds, do NOT decompose, do NOT extract sub-words. Return exactly one entry for the term AS GIVEN.

{
  "term_en": "Translation (see rules)",
  "definition": "Short explanation in German (B1 level, 1-2 sentences)",
  "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
  "example_sentence": "Example sentence using the term in its source language",
  "example_sentence_en": "English translation of the example sentence"
}

Rules:
- term_en: if the input term is German, translate to English. If English, translate to German. Never the same language as the input.
- definition: simple explanation in German, understandable at B1 level
- definition_en: simple explanation in English, understandable at B1 level
- Respond ONLY with the JSON object, no array, no markdown fences."""

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
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    """Extract glossary terms from a PDF text selection."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    enforce_aia_burst(user_id, locale)
    enforce_quota(user_id, "aia_generate", is_admin_user(current_user), locale)

    # Check glossary limit
    current_count = db.get_glossary_count(workspace["id"], user_id)
    if current_count >= GLOSSARY_LIMIT:
        return {"added": 0, "message": t("ai.glossary.full", locale, current=current_count, max=GLOSSARY_LIMIT)}

    # Truncate to 300 chars
    text = body.text[:300].strip()
    if not text:
        return {"added": 0, "message": t("ai.glossary.noTextSelected", locale)}

    # Find the source. It must belong to this workspace, otherwise a foreign
    # source_uuid would let a user attach glossary entries (bulk_create_glossary_entries
    # keys on source["id"]) to another workspace's source.
    source = db.get_aia_source(body.source_uuid)
    if not source or source["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    # Get existing terms to avoid duplicates
    existing = db.get_aia_glossary_by_workspace(workspace["id"], user_id)
    existing_terms = {e["term_de"].lower() for e in existing}

    # Short selections (single term / short phrase) → take the marked text verbatim,
    # ask LLM only for translation/definition. Avoids the LLM splitting compounds
    # like "Prüfungsleistung" into "Prüfung" + "Leistung" + "Prüfungsleistung".
    tokens = [w for w in re.split(r"\s+", text) if w]
    is_single_term_selection = len(tokens) <= 3 and len(text) <= 60

    try:
        if is_single_term_selection:
            messages = [
                {"role": "system", "content": _GLOSSARY_SINGLE_PROMPT},
                {"role": "user", "content": f"Markierter Begriff: {text}"},
            ]
            response = await asyncio.to_thread(
                lambda: llm._client.chat.completions.create(
                    model=llm._model, messages=messages, temperature=0.2,
                    **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
                )
            )
            answer = response.choices[0].message.content.strip()
            if answer.startswith("```"):
                answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            parsed = json.loads(answer)
            if isinstance(parsed, list):
                parsed = parsed[0] if parsed else None
            if not isinstance(parsed, dict):
                return {"added": 0, "message": t("ai.glossary.noLearnableTerms", locale)}

            if text.lower() in existing_terms:
                return {"added": 0, "message": t("ai.glossary.alreadyKnown", locale)}

            entry = {
                "term_de": text,
                "term_en": parsed.get("term_en", ""),
                "definition": parsed.get("definition", ""),
                "definition_en": parsed.get("definition_en", ""),
                "example_sentence": parsed.get("example_sentence", ""),
                "example_sentence_en": parsed.get("example_sentence_en", ""),
                "page_number": body.page_number,
            }
            db.bulk_create_glossary_entries(source["id"], user_id, [entry])
            return {
                "added": 1,
                "message": t("ai.glossary.added", locale, count=1),
                "entries": [entry],
            }

        messages = [
            {"role": "system", "content": _GLOSSARY_EXTRACT_PROMPT},
            {"role": "user", "content": f"Markierter Text:\n\n{text}"},
        ]
        response = await asyncio.to_thread(
            lambda: llm._client.chat.completions.create(
                model=llm._model, messages=messages, temperature=0.2,
                **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
            )
        )
        answer = response.choices[0].message.content.strip()
        if answer.startswith("```"):
            answer = answer.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        terms = json.loads(answer)
        if not isinstance(terms, list):
            return {"added": 0, "message": t("ai.glossary.noLearnableTerms", locale)}

        # Filter: must appear in source text, no duplicates
        text_lower = text.lower()
        remaining_slots = GLOSSARY_LIMIT - current_count
        new_entries = []
        for term_obj in terms[:5]:
            if not term_obj.get("term_de"):
                continue
            term = term_obj["term_de"]
            if not _term_appears_in_text(term, text_lower):
                continue
            if term.lower() in existing_terms:
                continue
            new_entries.append({
                "term_de": term_obj["term_de"],
                "term_en": term_obj.get("term_en", ""),
                "definition": term_obj.get("definition", ""),
                "definition_en": term_obj.get("definition_en", ""),
                "example_sentence": term_obj.get("example_sentence", ""),
                "example_sentence_en": term_obj.get("example_sentence_en", ""),
                "page_number": body.page_number,
            })
            existing_terms.add(term_obj["term_de"].lower())
            if len(new_entries) >= remaining_slots:
                break

        if not new_entries:
            if existing_terms and any(term_obj.get("term_de", "").lower() in existing_terms for term_obj in terms):
                return {"added": 0, "message": t("ai.glossary.alreadyKnown", locale)}
            return {"added": 0, "message": t("ai.glossary.noNewTerms", locale)}

        db.bulk_create_glossary_entries(source["id"], user_id, new_entries)
        count = len(new_entries)
        return {
            "added": count,
            "message": t("ai.glossary.added", locale, count=count),
            "entries": new_entries,
        }
    except (json.JSONDecodeError, ValueError):
        return {"added": 0, "message": t("ai.glossary.noLearnableTerms", locale)}
    except Exception as e:
        logger.error("Glossary extract error: {}", e)
        raise HTTPException(status_code=500, detail=t("ai.glossary.extractionFailed", locale))


# ─── Mindmap generieren ──────────────────────────────────────────────────────

