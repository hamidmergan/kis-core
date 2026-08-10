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
from src.features.ai_assistant.routes._helpers import _require_workspace_access
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
    # Assistant turns of an option question carry the shown option values; user
    # turns carry the values the learner clicked. Both are bounded so a crafted
    # request cannot grow without limit. Free text answers leave ``selected`` unset.
    options: list[str] | None = Field(default=None, max_length=MAX_OPTIONS)
    selected: list[str] | None = Field(default=None, max_length=MAX_OPTIONS)

    @field_validator("options", "selected")
    @classmethod
    def _cap_option_strings(cls, value: list[str] | None) -> list[str] | None:
        if value and any(len(s) > MAX_MESSAGE_CHARS for s in value):
            raise ValueError("option value too long")
        return value


class TurnBody(BaseModel):
    workspace_uuid: str
    history: list[TurnMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


# Der Test ist deutsch, deshalb steht der Sprachname im Prompt fest. Frueher kam er
# aus dem Kursraum-Feld ``diagnosis_language``; die Fragen sind aber immer deutsch,
# also haette ein anderer Sprachname nur bedeutet, dass deutsche Fragen nach einem
# fremden Massstab bewertet werden.
DIAGNOSIS_LANGUAGE_NAME = TRANSCRIPT_LANGUAGES[DEFAULT_DIAGNOSIS_LANGUAGE]["name"]


async def _ask(llm, messages: list[dict], user_id: int, locale: str) -> str:
    """Der eine Abschluss-Aufruf. Die Anbindung liegt in aia_json_llm, damit der
    Adminbereich beim Erzeugen dieselbe benutzt statt einer Kopie."""
    return await ask_json(llm, messages, locale=locale,
                          what=f"Language diagnosis (user {user_id})")


async def _run_turn(llm, messages: list[dict], user_id: int, locale: str) -> dict:
    """The final grading turn, with a single repair attempt.

    Measured against the production model, roughly one turn in twelve arrives as
    the bare text with no JSON around it. Without the repair that turn would fail
    the whole request and the learner would see a retry button after finishing.
    """
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
    workspace = _require_workspace_access(body.workspace_uuid, user_id, locale=locale)
    # Schaltet die Verwaltung den Trainer waehrend eines laufenden Tests ab, darf
    # das offene Fenster ihn nicht zu Ende bringen. Sonst stuende hinterher ein
    # Niveau in der Datenbank, das der Kurs gar nicht mehr benutzt.
    if not db.is_language_training_active(workspace["id"]):
        raise HTTPException(status_code=403, detail=t("ai.workspace.languageTrainingOff", locale))

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

    # Es sind noch Fragen offen: die naechste kommt direkt aus dem Plan, ohne
    # Modellaufruf. Jede Zeile im Plan ist ausgeschrieben, es gibt nichts mehr zu
    # erzeugen. Der Lernende wartet also zwischen zwei Fragen nie.
    if answered < total:
        return manual_question_payload(plan[answered])

    # Nothing given anywhere: there is nothing to grade. The level is fixed in
    # code rather than left to a model that would pick between the lower bands at
    # random and invent a strength to praise, and it saves the call as well.
    if is_empty_run(history):
        db.set_user_language_level(user_id, "A1")
        logger.info("Language diagnosis: empty run, level fixed to A1 for user={}", user_id)
        return {
            "done": True,
            "level": "A1",
            "message": t("ai.languageDiagnosis.allSkipped", locale),
        }

    # Every question answered: the ONE grading call. It reads the full record,
    # uses the code-graded results as they stand, judges the rest, and returns the
    # level. A model that forgets to finish is forced once more before we give up.
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
