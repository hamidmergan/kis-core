"""KI-Assistent routes - language diagnosis (one-time CEFR self-assessment).

POST /ai-assistant/language-diagnosis/analyze receives all 12 answers, runs one
LLM call, persists the result on the user, and returns level + feedback +
per-skill scores.

DELETE /ai-assistant/language-diagnosis/me clears the level so the user can
re-take the diagnosis.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_current_user, get_llm_client
from src.i18n import get_locale, t
from src.security.rate_limit import enforce_aia_burst
from src.services.aia_diagnosis_analyzer import (
    DiagnosisAnalysisError,
    build_analysis_prompt,
    parse_analysis_response,
)

router = APIRouter(tags=["ki-assistent: language-diagnosis"])

EXPECTED_QUESTION_COUNT = 12

# Static B1-anchored question set. IDs are stable; do NOT renumber.
DIAGNOSIS_QUESTIONS: list[dict] = [
    {"id": 1, "type": "single", "skill": "grammar",
     "prompt": "Ich weiß nicht, ___.",
     "options": ["wann der Zug kommt", "wann kommt der Zug", "kommt der Zug wann"], "correct": [0]},
    {"id": 2, "type": "multi", "skill": "grammar",
     "prompt": "Welche Sätze stehen im Perfekt? (Wähle alle richtigen aus)",
     "options": [
         "Er ist gestern nach Berlin gefahren.",
         "Sie liest ein Buch.",
         "Wir haben lange telefoniert.",
         "Ich werde morgen kochen.",
     ], "correct": [0, 2]},
    {"id": 3, "type": "single", "skill": "grammar",
     "prompt": "Wir warten ___ den Bus.",
     "options": ["auf", "an", "für"], "correct": [0]},
    {"id": 4, "type": "single", "skill": "grammar",
     "prompt": "Ich bleibe zu Hause, ___ ich krank bin.",
     "options": ["aber", "weil", "trotzdem"], "correct": [1]},
    {"id": 5, "type": "single", "skill": "vocabulary",
     "prompt": "Was ist das Gegenteil von „pünktlich“?",
     "options": ["sauber", "unpünktlich", "müde"], "correct": [1]},
    {"id": 6, "type": "multi", "skill": "grammar",
     "prompt": "Welche Wörter sind Adjektive (Wiewörter)?",
     "options": ["Haus", "schnell", "groß", "singen"], "correct": [1, 2]},
    {"id": 7, "type": "single", "skill": "vocabulary",
     "prompt": "Welches Wort passt auch für „höflich“?",
     "options": ["nett", "laut", "schwierig"], "correct": [0]},
    {"id": 8, "type": "single", "skill": "reading",
     "prompt": "Text: „Das Meeting wurde von 14 Uhr auf 16 Uhr verschoben.“ Wann findet das Treffen statt?",
     "options": ["Früher als geplant", "Später als geplant", "Gar nicht"], "correct": [1]},
    {"id": 9, "type": "single", "skill": "pragmatics",
     "prompt": "Du bist im Restaurant und möchtest bezahlen. Was sagst du?",
     "options": ["Die Rechnung bitte.", "Wo ist der Bahnhof?", "Guten Appetit."], "correct": [0]},
    {"id": 10, "type": "free_text", "skill": "writing",
     "prompt": "Beschreibe in 2 Sätzen: Was siehst du in deinem Zimmer?"},
    {"id": 11, "type": "free_text", "skill": "writing",
     "prompt": "Schreibe eine kurze Entschuldigung an deinen Lehrer, warum du heute nicht kommen kannst."},
    {"id": 12, "type": "free_text", "skill": "writing",
     "prompt": "Wie findest du das Wetter heute? Warum?"},
]


class AnswerIn(BaseModel):
    questionId: int = Field(ge=1, le=12)
    selectedIndices: Optional[list[int]] = None
    text: Optional[str] = None


class AnalyzeBody(BaseModel):
    answers: list[AnswerIn]


def _call_llm(llm, messages: list[dict]):
    return llm._client.chat.completions.create(
        model=llm._model,
        messages=messages,
        temperature=0.2,
        **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
    )


def _target_language_for(locale: str) -> str:
    return "English" if locale == "en" else "German"


@router.get("/ai-assistant/language-diagnosis/questions")
async def list_questions(
    current_user: dict = Depends(get_current_user),
):
    return {
        "questions": [
            {k: v for k, v in q.items() if k != "correct"}
            for q in DIAGNOSIS_QUESTIONS
        ],
    }


@router.post("/ai-assistant/language-diagnosis/analyze")
async def analyze(
    body: AnalyzeBody,
    current_user: dict = Depends(get_current_user),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]

    if len(body.answers) != EXPECTED_QUESTION_COUNT:
        raise HTTPException(
            status_code=400,
            detail=t("ai.languageDiagnosis.wrongAnswerCount", locale,
                     expected=EXPECTED_QUESTION_COUNT, got=len(body.answers)),
        )

    enforce_aia_burst(user_id, locale)

    answers_dict = [a.model_dump() for a in body.answers]
    prompt = build_analysis_prompt(
        DIAGNOSIS_QUESTIONS,
        answers_dict,
        target_language=_target_language_for(locale),
    )

    messages = [
        {"role": "system", "content": "You are a precise CEFR assessor. Output only JSON."},
        {"role": "user", "content": prompt},
    ]

    try:
        response = _call_llm(llm, messages)
        raw = response.choices[0].message.content
    except Exception as exc:
        logger.error("Language diagnosis LLM call failed for user {}: {}", user_id, exc)
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.llmUnavailable", locale))

    try:
        result = parse_analysis_response(raw)
    except DiagnosisAnalysisError as exc:
        logger.warning("Language diagnosis parse failed for user {}: {} | raw: {!r}",
                       user_id, exc, raw[:500])
        raise HTTPException(status_code=502,
                            detail=t("ai.languageDiagnosis.invalidResponse", locale))

    db.set_user_language_level(user_id, level=result["level"], skill_scores=result["skill_scores"])
    logger.info("Language diagnosis complete: user={} level={}", user_id, result["level"])

    return {
        "level": result["level"],
        "feedback": result["feedback"],
        "skill_scores": result["skill_scores"],
    }


@router.delete("/ai-assistant/language-diagnosis/me")
async def reset(
    current_user: dict = Depends(get_current_user),
):
    db.clear_user_language_level(current_user["user_id"])
    return {"reset": True}
