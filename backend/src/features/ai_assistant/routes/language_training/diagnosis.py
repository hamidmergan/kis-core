"""Language level assessment as a short chat, per person, the history lives in the browser."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import (
    DEFAULT_DIAGNOSIS_LANGUAGE,
    TRANSCRIPT_LANGUAGES,
    get_locale,
    t,
)
from src.security.rate_limit import enforce_aia_burst
from src.services.aia_diagnosis_chat import (
    ANSWER_MAX_CHARS_SETTING,
    DEFAULT_ANSWER_MAX_CHARS,
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GRADING_RULES,
    FORCE_FINISH_MESSAGE,
    _LEGACY_GRADING_RULES,
    GRADING_RULES_SETTING,
    LEVEL_EXAMPLES_SETTING,
    MAX_HISTORY_MESSAGES,
    MAX_MESSAGE_CHARS,
    MAX_OPTIONS,
    QUESTION_PLAN_SETTING,
    REPAIR_MESSAGE,
    DiagnosisChatError,
    assemble_system_prompt,
    build_final_messages,
    is_empty_run,
    manual_question_payload,
    parse_level_examples,
    parse_question_plan,
    parse_turn_response,
)
from src.services.aia_json_llm import _rejects_json_mode, ask_json  # noqa: F401
from src.services.aia_level_ladder import (
    LEVEL_DESCRIPTIONS_SETTING,
    parse_level_descriptions,
    resolve_prompt_setting,
)

router = APIRouter(tags=["ki-assistent: language-diagnosis"])


class TurnMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)
    # Both sides carry the shown and clicked values, both are capped.
    options: list[str] | None = Field(default=None, max_length=MAX_OPTIONS)
    selected: list[str] | None = Field(default=None, max_length=MAX_OPTIONS)

    @field_validator("options", "selected")
    @classmethod
    def _cap_option_strings(cls, value: list[str] | None) -> list[str] | None:
        if value and any(len(s) > MAX_MESSAGE_CHARS for s in value):
            raise ValueError("option value too long")
        return value


class TurnBody(BaseModel):
    history: list[TurnMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


# The test is German, so the language name is fixed in the prompt.
DIAGNOSIS_LANGUAGE_NAME = TRANSCRIPT_LANGUAGES[DEFAULT_DIAGNOSIS_LANGUAGE]["name"]


async def _ask(llm, messages: list[dict], user_id: int, locale: str) -> str:
    """The one final call, the wiring lives in aia_json_llm."""
    return await ask_json(llm, messages, locale=locale,
                          what=f"Language diagnosis (user {user_id})")


async def _run_turn(llm, messages: list[dict], user_id: int, locale: str) -> dict:
    """The grading call, with exactly one repair attempt."""
    raw = await _ask(llm, messages, user_id, locale)
    try:
        return parse_turn_response(raw)
    except DiagnosisChatError as exc:
        logger.warning("Language diagnosis verdict unparseable for user {}: {} | raw: {!r}",
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
        logger.warning("Language diagnosis verdict repair failed for user {}: {} | raw: {!r}",
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
    # A trainer switched off midway must not let the test finish, the level is what it produces.
    if not db.is_language_training_offered(user_id):
        raise HTTPException(status_code=403, detail=t("ai.languageTraining.off", locale))

    plan = parse_question_plan(db.get_setting(QUESTION_PLAN_SETTING, ""))
    total = len(plan)
    history = [m.model_dump(exclude_none=True) for m in body.history]
    answered = sum(1 for m in history if m["role"] == "user")

    system_prompt = assemble_system_prompt(
        db.get_setting("language_diagnosis_prompt", DEFAULT_DIAGNOSIS_PROMPT),
        resolve_prompt_setting(
            db.get_setting(GRADING_RULES_SETTING, ""),
            _LEGACY_GRADING_RULES,
            DEFAULT_GRADING_RULES,
        ),
        parse_level_descriptions(db.get_setting(LEVEL_DESCRIPTIONS_SETTING, "")),
        parse_level_examples(db.get_setting(LEVEL_EXAMPLES_SETTING, "")),
        DIAGNOSIS_LANGUAGE_NAME,
    )

    # Open questions come straight from the plan, without a model call.
    if answered < total:
        return manual_question_payload(plan[answered])

    # Without a single answer there is nothing to grade, the level is set in code.
    if is_empty_run(history):
        db.set_user_language_level(user_id, "A1")
        logger.info("Language diagnosis: empty run, level fixed to A1 for user={}", user_id)
        return {
            "done": True,
            "level": "A1",
            "message": t("ai.languageDiagnosis.allSkipped", locale),
            "aiGraded": False,
        }

    # Once all questions are answered, the one grading call follows.
    enforce_aia_burst(user_id, locale)
    messages = build_final_messages(system_prompt, plan, history)
    result = await _run_turn(llm, messages, user_id, locale)
    if not result["done"]:
        logger.info("Language diagnosis: model did not finish, forcing once")
        messages = [*messages, {"role": "system", "content": FORCE_FINISH_MESSAGE}]
        result = await _run_turn(llm, messages, user_id, locale)
    if not result["done"]:
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.invalidResponse", locale))

    db.set_user_language_level(user_id, result["level"])
    logger.info("Language diagnosis complete: user={} level={}", user_id, result["level"])
    return {**result, "aiGraded": True}


@router.get("/ai-assistant/language-diagnosis/config")
async def config(current_user: dict = Depends(get_current_user)):
    """Question count and answer length for the interface, from the admin settings."""
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
