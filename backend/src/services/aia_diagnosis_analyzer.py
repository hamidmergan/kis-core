"""Build the single-shot CEFR analysis prompt and parse the LLM JSON response.

Strategy: send all 12 answers in one call. The LLM sees the full picture
(MC correctness pattern + free-text writing samples) and returns a JSON object
with the overall level + per-skill scores.
"""

import json
from typing import Sequence


VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
REQUIRED_SKILLS = {"grammar", "vocabulary", "reading", "writing", "pragmatics"}


class DiagnosisAnalysisError(ValueError):
    """Raised when the LLM response is unparseable or fails validation."""


_PROMPT_TEMPLATE = """You are a CEFR language assessor for German as a foreign language.
Below are 12 diagnostic responses from a learner. The first 9 are auto-graded
multi-choice answers (correctness is given). The last 3 are free-text writing samples.

Your task: determine the learner's overall CEFR level (A1, A2, B1, B2, C1, C2)
and per-skill scores 0-100 for: grammar, vocabulary, reading, writing, pragmatics.

For free-text: judge sentence complexity, lexical range, grammar accuracy,
appropriateness to the task, and register. If a response is empty or
incoherent German, treat that as evidence of low writing skill (do not skip).

For multi-choice: error patterns matter (e.g. preposition errors -> A2 marker;
nebensatz word-order errors -> below B1).

Respond with ONLY a JSON object (no prose, no markdown), exactly this shape:
{{
  "level": "A1" | "A2" | "B1" | "B2" | "C1" | "C2",
  "feedback": "<2-3 sentences in {target_language}, encouraging tone, name 1 strength + 1 area to improve>",
  "skill_scores": {{
    "grammar": <integer 0-100>,
    "vocabulary": <integer 0-100>,
    "reading": <integer 0-100>,
    "writing": <integer 0-100>,
    "pragmatics": <integer 0-100>
  }}
}}

--- LEARNER RESPONSES ---

{auto_section}

--- FREE-TEXT WRITING ---

{free_section}
"""


def _grade_single(question: dict, answer: dict) -> str:
    selected = set(answer.get("selectedIndices") or [])
    correct = set(question.get("correct") or [])
    return "CORRECT" if selected == correct else "INCORRECT"


def _grade_multi(question: dict, answer: dict) -> str:
    selected = set(answer.get("selectedIndices") or [])
    correct = set(question.get("correct") or [])
    if not selected:
        return "INCORRECT (none selected)"
    hits = selected & correct
    extras = selected - correct
    if hits == correct and not extras:
        return "CORRECT (all selected, no extras)"
    if hits:
        return f"PARTIAL ({len(hits)} of {len(correct)} correct, {len(extras)} extras)"
    return "INCORRECT (none correct)"


def build_analysis_prompt(
    questions: Sequence[dict],
    answers: Sequence[dict],
    target_language: str,
) -> str:
    answers_by_id = {a["questionId"]: a for a in answers}

    auto_lines: list[str] = []
    free_lines: list[str] = []
    for q in questions:
        ans = answers_by_id.get(q["id"], {})
        if q["type"] == "single":
            auto_lines.append(f"Q{q['id']} [{q['skill']}, single]: {_grade_single(q, ans)}")
        elif q["type"] == "multi":
            auto_lines.append(f"Q{q['id']} [{q['skill']}, multi]: {_grade_multi(q, ans)}")
        elif q["type"] == "free_text":
            text = (ans.get("text") or "").strip() or "<empty>"
            free_lines.append(f"Q{q['id']} [{q['skill']}] prompt: {q['prompt']}\nLearner wrote: {text}")
        else:
            raise DiagnosisAnalysisError(f"Unknown question type: {q.get('type')}")

    return _PROMPT_TEMPLATE.format(
        target_language=target_language,
        auto_section="\n".join(auto_lines),
        free_section="\n\n".join(free_lines),
    )


def parse_analysis_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DiagnosisAnalysisError(f"Response is not valid JSON: {exc}") from exc

    level = parsed.get("level")
    if level not in VALID_LEVELS:
        raise DiagnosisAnalysisError(f"Invalid level: {level!r}")

    feedback = parsed.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise DiagnosisAnalysisError("Missing or empty feedback")

    scores = parsed.get("skill_scores") or {}
    if not isinstance(scores, dict):
        raise DiagnosisAnalysisError("skill_scores must be an object")
    missing = REQUIRED_SKILLS - scores.keys()
    if missing:
        raise DiagnosisAnalysisError(f"Missing skill scores: {missing}")
    for skill in REQUIRED_SKILLS:
        val = scores[skill]
        if not isinstance(val, (int, float)) or not 0 <= val <= 100:
            raise DiagnosisAnalysisError(f"skill_scores.{skill} must be 0-100, got {val!r}")

    return {
        "level": level,
        "feedback": feedback.strip(),
        "skill_scores": {s: int(scores[s]) for s in REQUIRED_SKILLS},
    }
