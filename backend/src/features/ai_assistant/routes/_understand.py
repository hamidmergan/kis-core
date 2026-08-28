"""The pre-call: route, reference, follow-up and answer language in one go."""

import re
from typing import Optional

from loguru import logger

from src.services import model_limits

from src.features.ai_assistant.prompts.query_understanding_prompts import (
    aia_query_understanding_system,
)

from . import _followup
from ._scope import _parse_scope_response


# Longer questions are almost always topical, the pre-call is skipped.
_INTENT_MAX_WORDS = 30


def _should_skip_intent_classification(source_text, source_ids, question: str) -> bool:
    """Cheap pre-check that saves the routing call when the route is obvious."""
    return (
        bool(source_text)
        or not source_ids
        or len(question.strip().split()) > _INTENT_MAX_WORDS
    )


def _parse_understanding(content: str) -> tuple[str, dict, list[str]]:
    """Reads route, reference and sub-questions from the pre-call answer."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return "SPECIFIC", {"unit": None, "intervals": []}, []
    try:
        obj = json.loads(m.group(0))
    except Exception:
        cleaned = re.sub(r"[^A-Za-z]+", " ", raw).upper().split()
        return ("GENERIC" if "GENERIC" in cleaned else "SPECIFIC"), {"unit": None, "intervals": []}, []
    _roh = str(obj.get("intent", "")).upper()
    intent = "GREETING" if "GREET" in _roh else ("GENERIC" if "GENERIC" in _roh else "SPECIFIC")
    scope_obj = obj.get("scope")
    scope = _parse_scope_response(json.dumps(scope_obj)) if scope_obj else {"unit": None, "intervals": []}
    subs_raw = obj.get("subqueries")
    subqueries = ([s.strip() for s in subs_raw if isinstance(s, str) and s.strip()][:3]
                  if isinstance(subs_raw, list) else [])
    return intent, scope, subqueries


# A language name and nothing more, the value goes unchecked into the next prompt.
_SPRACHNAME = re.compile(r"^[A-Za-z][A-Za-z \-]{1,29}$")


def _parse_answer_language(content: str) -> str:
    """The English name of the question language from the pre-call, empty when unusable."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    m = re.search(r"\{.*\}", raw.replace("```json", "").replace("```", ""), re.DOTALL)
    if not m:
        return ""
    try:
        name = str(json.loads(m.group(0)).get("lang", "")).strip()
    except Exception:
        return ""
    return name if _SPRACHNAME.match(name) else ""


async def _understand_query(
    llm, question: str, letzte_runde: Optional[dict] = None
) -> tuple[str, dict, list[str], str, str, str]:
    """One pre-call for everything: route, reference, sub-questions, follow-up and language."""
    import asyncio
    def _call():
        # 60s covers Ollama cold-start; warm calls return in ~500ms.
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system",
                 "content": aia_query_understanding_system(bool(letzte_runde))},
                {"role": "user", "content": _followup.vorcall_eingabe(question, letzte_runde)},
            ],
            temperature=0.0,
            # Forces valid JSON instead of merely asking for it.
            response_format={"type": "json_object"},
            # Room for sub-questions and for a model whose thinking cannot be turned off.
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )
    try:
        response = await asyncio.to_thread(_call)
        msg = response.choices[0].message
        raw = msg.content or getattr(msg, "reasoning_content", None) or ""
    except Exception as e:
        logger.warning("Query understanding failed, defaulting to SPECIFIC/no-scope: {}", e)
        return "SPECIFIC", {"unit": None, "intervals": []}, [], _followup.KEINE, question, ""
    intent, scope, subqueries = _parse_understanding(raw)
    sprache = _parse_answer_language(raw)
    art, frage = (_followup.nachfrage_lesen(raw, question) if letzte_runde
                  else (_followup.KEINE, question))
    logger.info("Query understanding: '{}' → intent={} scope={} subqueries={} nachfrage={} sprache={} frage='{}'",
                question[:50], intent, scope, subqueries, art, sprache or "-", frage[:60])
    return intent, scope, subqueries, art, frage, sprache
