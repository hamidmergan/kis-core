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

from src.features.ai_assistant.routes._text import _context_snippet, _term_appears_in_text
from src.features.ai_assistant import schemas
from src.services.aia_adaptive_tools import build_adaptive_tool_suffix

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


# ─── Glossary: extract from a selection ───────────────────────────────────────

_GLOSSARY_SINGLE_PROMPT = """You are a language expert for international students. Write the definitions at B1 level BY DEFAULT. If an adaptive block at the very end of this prompt names the learner's CEFR level, write the definitions at THAT level instead of B1. The user has manually selected ONE specific term/phrase to add to their glossary.

Respond ONLY with a JSON object describing this exact term. Do NOT split compounds, do NOT decompose, do NOT extract sub-words. Return exactly one entry for the term AS GIVEN.

{
  "term_en": "Translation (see rules)",
  "base_form": "Dictionary base form of the term (see rules), or empty string",
  "definition": "Short explanation in German (B1 level, 1-2 sentences)",
  "definition_en": "Short explanation in English (B1 level, 1-2 sentences)",
  "example_sentence": "Example sentence using the term in its source language",
  "example_sentence_en": "English translation of the example sentence"
}

Rules:
- term_en: if the input term is German, translate to English. If English, translate to German. Never the same language as the input.
- base_form: the dictionary base form (lemma) of the marked term, in the SAME language as the term (NOT a translation). Base form means: nouns in the singular nominative, verbs in the infinitive, adjectives uninflected. Return an EMPTY string when the term is already in its base form, is a multi-word phrase, or the language does not inflect it this way. Example: term "läuft" -> base_form "laufen"; term "Häusern" -> base_form "Haus"; term "Arbeitsmarkt" -> base_form "".
- definition: a simple but ACCURATE explanation in German at B1 level. First name what the term IS (its category), then add the one or two features that truly distinguish it. If a CONTEXT excerpt from the document is provided below, base the definition on how the term is actually used THERE and stay consistent with it. Do NOT invent specifics the context does not support, do NOT narrow a general term down to one special case, and do NOT pad it with vague filler sentences.
- definition_en: the same explanation in English at B1 level.
- Respond ONLY with the JSON object, no array, no markdown fences."""

_GLOSSARY_EXTRACT_PROMPT = """You are a language expert for international students. Write the definitions at B1 level BY DEFAULT. If an adaptive block at the very end of this prompt names the learner's CEFR level, write the definitions at THAT level instead of B1. Analyze the highlighted text and extract words/phrases that a B1 learner should learn for university study.

Respond ONLY with a JSON array:
[
  {
    "term_de": "Term in the source language",
    "term_en": "Translation (see rules)",
    "base_form": "Dictionary base form of term_de (see rules), or empty string",
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
- base_form: the dictionary base form (lemma) of term_de, in the SAME language as term_de (NOT a translation). Base form means: nouns in the singular nominative, verbs in the infinitive, adjectives uninflected. Return an EMPTY string when term_de is already in its base form, is a multi-word phrase, or the language does not inflect it this way. Example: term_de "läuft" -> base_form "laufen"; term_de "Arbeitsmarkt" -> base_form "".
- definition: a simple but ACCURATE explanation in German at B1 level. First name what the term IS (its category), then add the one or two features that truly distinguish it. Base it on how the term is used in the marked text. Do NOT invent specifics the text does not support, do NOT narrow a general term down to one special case, and do NOT pad it with vague filler sentences.
- definition_en: the same explanation in English at B1 level.
- example_sentence_en: English translation of the example sentence
- At most 5 terms per selection; prioritize the ones most difficult at B1
- If the text really only contains function words / trivial vocabulary, respond with: []
- Respond ONLY with the JSON array."""


def _base_form(raw: str | None, term: str) -> str:
    """The base form of a marked term, empty when it does not differ."""
    bf = (raw or "").strip()
    if not bf or bf.lower() == (term or "").strip().lower():
        return ""
    return bf


def _glossary_system_prompt(is_single_term: bool, adaptive_suffix: str = "") -> str:
    """The glossary prompt, extended by the learner's level block."""
    base = _GLOSSARY_SINGLE_PROMPT if is_single_term else _GLOSSARY_EXTRACT_PROMPT
    return base + adaptive_suffix


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

    # The source must belong to this course room, otherwise you reach into someone else's.
    source = db.get_aia_source(body.source_uuid)
    if not source or source["workspace_id"] != workspace["id"]:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    # Get existing terms to avoid duplicates
    existing = db.get_aia_glossary_by_workspace(workspace["id"], user_id)
    existing_terms = {e["term_de"].lower() for e in existing}

    # Take a short selection verbatim, otherwise the model splits compound words.
    tokens = [w for w in re.split(r"\s+", text) if w]
    is_single_term_selection = len(tokens) <= 3 and len(text) <= 60

    # Definition at the learner's level, gated on the course room like every adaptive path.
    adaptive_suffix = build_adaptive_tool_suffix(user_id, workspace["id"])

    try:
        if is_single_term_selection:
            # The definition is anchored in the page context instead of the bare word.
            context = _context_snippet(db.get_page_text(source["id"], body.page_number), text)
            user_content = f"Markierter Begriff: {text}"
            if context:
                user_content += (
                    "\n\nCONTEXT (so wird der Begriff im Dokument verwendet, "
                    f"nutze ihn für eine passende Definition):\n{context}"
                )
            messages = [
                {"role": "system", "content": _glossary_system_prompt(True, adaptive_suffix)},
                {"role": "user", "content": user_content},
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
                "base_form": _base_form(parsed.get("base_form"), text),
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
            {"role": "system", "content": _glossary_system_prompt(False, adaptive_suffix)},
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
                "base_form": _base_form(term_obj.get("base_form"), term_obj["term_de"]),
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

