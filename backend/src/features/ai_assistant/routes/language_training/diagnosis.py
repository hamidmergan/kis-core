"""KI-Assistent routes - language diagnosis (one-time CEFR assessment).

The diagnosis is a short adaptive chat. POST .../turn takes the transcript so
far and runs ONE LLM call, which either returns the next question or the final
verdict; on the verdict the level is persisted on the user.

The transcript lives on the client and is posted back each turn. There is no
server-side session to keep, and nothing to protect: it is the user's own
diagnosis and they may reset their level at any time anyway. It is length-capped
so a single request cannot grow without bound.

DELETE .../me clears the level so the user can take the diagnosis again.
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import (
    DEFAULT_DIAGNOSIS_LANGUAGE,
    TRANSCRIPT_LANGUAGES,
    get_locale,
    t,
)
from src.security.rate_limit import enforce_aia_burst
from src.features.ai_assistant.routes._helpers import _require_workspace_access
from src.services.aia_diagnosis_chat import (
    ANSWER_MAX_CHARS_SETTING,
    DEFAULT_ANSWER_MAX_CHARS,
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GRADING_RULES,
    FORCE_FINISH_MESSAGE,
    GRADING_RULES_SETTING,
    KICKOFF_MESSAGE,
    LEVEL_EXAMPLES_SETTING,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CHARS,
    QUESTION_PLAN,
    QUESTION_PLAN_SETTING,
    REPAIR_MESSAGE,
    DiagnosisChatError,
    assemble_system_prompt,
    keep_going_message,
    next_question_message,
    parse_level_examples,
    parse_question_plan,
    parse_turn_response,
)

router = APIRouter(tags=["ki-assistent: language-diagnosis"])


class TurnMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


class TurnBody(BaseModel):
    workspace_uuid: str
    history: list[TurnMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


# Providers are admin-configured OpenAI-compatible endpoints, and not all of them
# accept response_format. Probe once per process instead of paying a rejected call
# on every single turn.
_json_mode_supported = True


def _rejects_json_mode(exc: Exception) -> bool:
    """True when the provider turned down response_format itself.

    Deliberately narrow: only a 400 that actually names the field counts. A 429
    or a context-length 400 must not switch JSON mode off for the whole process.
    """
    if getattr(exc, "status_code", None) != 400:
        return False
    text = str(exc).lower()
    return "response_format" in text or "json" in text


def _create(llm, messages: list[dict], *, json_mode: bool):
    kwargs = {
        "model": llm._model,
        "messages": messages,
        "temperature": 0.4,
        **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    return llm._client.chat.completions.create(**kwargs)


def _call_llm(llm, messages: list[dict]):
    """One completion, in JSON mode where the provider supports it.

    JSON mode matters more here than elsewhere: the prompt asks the model to be
    conversational AND to answer in JSON, and without the constraint it drifts
    into plain prose often enough that the repair pass fires regularly, doubling
    the request volume against a shared rate limit.
    """
    global _json_mode_supported
    if _json_mode_supported:
        try:
            return _create(llm, messages, json_mode=True)
        except Exception as exc:
            if not _rejects_json_mode(exc):
                raise
            logger.warning("Language diagnosis: provider rejected JSON mode, "
                           "falling back to prompt-only for this process: {}", exc)
            _json_mode_supported = False
    return _create(llm, messages, json_mode=False)


def _diagnosis_language_name(workspace: dict) -> str:
    """English name of the workspace's diagnosis language, for the prompt."""
    code = workspace.get("diagnosis_language") or DEFAULT_DIAGNOSIS_LANGUAGE
    entry = TRANSCRIPT_LANGUAGES.get(code) or TRANSCRIPT_LANGUAGES[DEFAULT_DIAGNOSIS_LANGUAGE]
    return entry["name"]


def build_turn_messages(
    system_prompt: str, history: list[dict], plan: list[dict] | None = None
) -> list[dict]:
    """Assemble the message list for one diagnosis turn.

    The number of answers so far decides the turn. Once all questions in ``plan``
    are answered, a system turn forces the verdict. Otherwise a system turn
    dictates the next question's number and difficulty (or its verbatim text), so
    the fixed staircase does not depend on the model counting the transcript. An
    empty transcript still gets a kickoff user turn, so the model always sees a
    user role before it speaks. ``plan`` defaults to the shipped ``QUESTION_PLAN``.
    """
    steps = plan or QUESTION_PLAN
    total = len(steps)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    answered = sum(1 for m in history if m["role"] == "user")

    if answered >= total:
        messages.extend(history)
        messages.append({"role": "system", "content": FORCE_FINISH_MESSAGE})
        return messages

    if history:
        messages.extend(history)
    else:
        messages.append({"role": "user", "content": KICKOFF_MESSAGE})
    # The question we are about to ask is one past the answers we already have.
    messages.append({"role": "system", "content": next_question_message(answered + 1, steps)})
    return messages


def running_turn_payload(result: dict) -> dict:
    """Client shape for a turn that continues the interview.

    Whitelisted rather than passed straight through, so a level the model leaked
    before the verdict cannot reach the client. The reaction keeps its own field
    instead of being glued onto the question: the client renders it as a separate
    chat bubble, the way a person sends the praise and the task as two messages.
    """
    payload = {"done": False, "message": result["message"]}
    if result.get("reaction"):
        payload["reaction"] = result["reaction"]
    return payload


async def _ask(llm, messages: list[dict], user_id: int, locale: str) -> str:
    try:
        response = await asyncio.to_thread(_call_llm, llm, messages)
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("Language diagnosis LLM call failed for user {}: {}", user_id, exc)
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.llmUnavailable", locale))


async def _run_turn(llm, messages: list[dict], user_id: int, locale: str) -> dict:
    """One diagnosis turn, with a single repair attempt.

    Measured against the production model, roughly one turn in twelve arrives as
    the bare question text with no JSON around it. Without the repair that turn
    would fail the whole request and the learner would see a retry button in the
    middle of the interview.
    """
    raw = await _ask(llm, messages, user_id, locale)
    try:
        return parse_turn_response(raw)
    except DiagnosisChatError as exc:
        logger.warning("Language diagnosis turn unparseable for user {}: {} | raw: {!r}",
                       user_id, exc, raw[:500])

    repaired = await _ask(
        llm,
        [*messages,
         {"role": "assistant", "content": raw},
         {"role": "system", "content": REPAIR_MESSAGE}],
        user_id,
        locale,
    )
    try:
        return parse_turn_response(repaired)
    except DiagnosisChatError as exc:
        logger.warning("Language diagnosis repair failed for user {}: {} | raw: {!r}",
                       user_id, exc, repaired[:500])
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.invalidResponse", locale))


@router.post("/ai-assistant/language-diagnosis/turn")
async def turn(
    body: TurnBody,
    current_user: dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_access(body.workspace_uuid, user_id, locale=locale)

    enforce_aia_burst(user_id, locale)

    system_prompt = assemble_system_prompt(
        db.get_setting("language_diagnosis_prompt", DEFAULT_DIAGNOSIS_PROMPT),
        db.get_setting(GRADING_RULES_SETTING, DEFAULT_GRADING_RULES),
        parse_level_examples(db.get_setting(LEVEL_EXAMPLES_SETTING, "")),
        _diagnosis_language_name(workspace),
    )
    plan = parse_question_plan(db.get_setting(QUESTION_PLAN_SETTING, ""))
    total = len(plan)
    history = [m.model_dump() for m in body.history]
    messages = build_turn_messages(system_prompt, history, plan)

    result = await _run_turn(llm, messages, user_id, locale)

    # The test has a fixed length, so a verdict before all answers are in is a
    # mistake: nudge once for the next question. One nudge is enough in practice;
    # whatever comes back second is accepted, so a stubborn model cannot stall.
    answered = sum(1 for m in history if m["role"] == "user")
    if result["done"] and answered < total:
        logger.info("Language diagnosis: verdict after {} of {} answers, asking for more",
                    answered, total)
        messages = [*messages, {"role": "system", "content": keep_going_message(answered, total)}]
        result = await _run_turn(llm, messages, user_id, locale)

    if not result["done"]:
        return running_turn_payload(result)

    db.set_user_language_level(
        user_id, level=result["level"], skill_scores=result["skill_scores"]
    )
    logger.info("Language diagnosis complete: user={} level={}", user_id, result["level"])
    return result


@router.get("/ai-assistant/language-diagnosis/config")
async def config(current_user: dict = Depends(get_current_user)):
    """Runtime knobs the diagnosis UI needs: how many questions, and the soft
    answer-length cap. Both come from admin settings, with code defaults.

    The answer cap is clamped to MAX_MESSAGE_CHARS: it is a UI hint (counter and
    maxlength), while the request body stays hard-capped server-side.
    """
    plan = parse_question_plan(db.get_setting(QUESTION_PLAN_SETTING, ""))
    raw = db.get_setting(ANSWER_MAX_CHARS_SETTING, str(DEFAULT_ANSWER_MAX_CHARS))
    try:
        answer_max = int(raw)
    except (TypeError, ValueError):
        answer_max = DEFAULT_ANSWER_MAX_CHARS
    return {
        "question_count": len(plan),
        "answer_max_chars": max(1, min(answer_max, MAX_MESSAGE_CHARS)),
    }


@router.delete("/ai-assistant/language-diagnosis/me")
async def reset(
    current_user: dict = Depends(get_current_user),
):
    db.clear_user_language_level(current_user["user_id"])
    return {"reset": True}
