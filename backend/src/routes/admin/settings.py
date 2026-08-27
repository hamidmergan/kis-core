"""Reads and writes the system-wide settings, providers live in the AI tab."""

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies_rbac import permissions_of, require_any_settings
from src.i18n import (
    DEFAULT_LEARNING_TOOLS_LANGUAGE,
    TRANSCRIPT_LANGUAGES,
    get_locale,
    t,
)
from src.permissions_registry import SETTING_FIELD_PERMISSIONS
from src.limits import (
    TTS_MAX_CHARS_PER_REQUEST,
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
    AIA_SPECIFIC_MAX_CHARS,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
    AIA_SUMMARY_BATCH_MAX_CHARS,
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
)

import json

from src.routes.admin._models import UpdateSettingsRequest
from src.services import tool_limits
from src.services.aia_diagnosis_chat import (
    ADAPTIVE_BEHAVIOR_SETTING,
    ANSWER_MAX_CHARS_SETTING,
    DEFAULT_ANSWER_MAX_CHARS,
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GERMAN_QUESTION_PLAN,
    DEFAULT_GRADING_RULES,
    DEFAULT_LEVEL_EXAMPLES,
    _LEGACY_GRADING_RULES,
    EXAMPLE_LEVELS,
    GRADING_RULES_SETTING,
    LEVEL_EXAMPLES_SETTING,
    MAX_MESSAGE_CHARS,
    MAX_PROMPT_CHARS,
    MIN_FREE_TEXT_QUESTIONS,
    QUESTION_PLAN_SETTING,
    first_incomplete_question,
    question_plan_has_enough_free_text,
    question_plan_is_valid,
)
from src.services.aia_adaptive_chat import (
    DEFAULT_ADAPTIVE_BEHAVIOR,
    _LEGACY_ADAPTIVE_BEHAVIOR,
)
from src.services.aia_level_ladder import (
    DEFAULT_LEVEL_DESCRIPTIONS,
    LEVEL_DESCRIPTIONS_SETTING,
    LEVELS,
    resolve_prompt_setting,
)

router = APIRouter(tags=["admin: settings"])


def _assert_fields_allowed(body: UpdateSettingsRequest, perms, locale: str) -> None:
    """Checks every submitted field against the right of its page."""
    for field_name, value in body.model_dump().items():
        if value is None:
            continue
        needed = SETTING_FIELD_PERMISSIONS.get(field_name)
        if needed is None or needed not in perms.keys:
            raise HTTPException(
                status_code=403,
                detail=t("auth.settingFieldForbidden", locale, field=field_name),
            )


@router.get("/settings")
async def get_settings(_admin=Depends(require_any_settings)):
    def _enabled(key: str, default: str = "true") -> bool:
        return db.get_setting(key, default).lower() == "true"

    return {
        "whitelist_enabled": _enabled("whitelist_enabled"),
        # UI labels (per locale; legacy unsuffixed keys fall back as DE defaults)
        "workspace_label_singular_de": db.get_setting(
            "workspace_label_singular_de",
            db.get_setting("workspace_label_singular", "Modul"),
        ),
        "workspace_label_plural_de": db.get_setting(
            "workspace_label_plural_de",
            db.get_setting("workspace_label_plural", "Module"),
        ),
        "workspace_label_singular_en": db.get_setting("workspace_label_singular_en", "Module"),
        "workspace_label_plural_en": db.get_setting("workspace_label_plural_en", "Modules"),
        # The language trainer platform wide, without it no course can turn it on.
        "language_training_enabled": _enabled("language_training_enabled", "false"),
        # Home page notice banner, shown to all users above the next appointments.
        "home_notice_enabled": _enabled("home_notice_enabled", "false"),
        "home_notice_text": db.get_setting("home_notice_text", ""),
        # OCR on image-heavy pages during indexing (system-wide, default on)
        "ocr_enabled": _enabled("ocr_enabled"),
        # Workspace limits (admin-tunable)
        "aia_workspace_max_sources": int(
            db.get_setting("aia_workspace_max_sources", str(AIA_WORKSPACE_MAX_SOURCES))
        ),
        # KI-tutor chat context budget (chars). Default sized for 32k models.
        "aia_context_max_chars": int(
            db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS))
        ),
        # Context of a specific question, apart from the overview budget above.
        "aia_specific_max_chars": int(
            db.get_setting("aia_specific_max_chars", str(AIA_SPECIFIC_MAX_CHARS))
        ),
        # Context budget of the generating tools, apart from the chat.
        "aia_tool_context_max_chars": int(
            db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS))
        ),
        # Language of the four learning tools, the language trainer stays German.
        "aia_learning_tools_language": db.get_setting(
            "aia_learning_tools_language", DEFAULT_LEARNING_TOOLS_LANGUAGE
        ),
        # Ingest-side DOC SUMMARY per-batch char cap (bigger = fewer summary calls).
        "aia_summary_batch_max_chars": int(
            db.get_setting("aia_summary_batch_max_chars", str(AIA_SUMMARY_BATCH_MAX_CHARS))
        ),
        # Max pages per uploaded source (long scripts → upload chapter-wise).
        "aia_source_max_pages": int(
            db.get_setting("aia_source_max_pages", str(AIA_SOURCE_MAX_PAGES))
        ),
        # Pronunciation on the flashcard, empty means not set up yet.
        "aia_flashcard_voice_provider_id": db.get_setting("aia_flashcard_voice_provider_id", ""),
        "aia_flashcard_voice_id": db.get_setting("aia_flashcard_voice_id", ""),
        # Characters per speech request, stays configurable because it is a provider trait.
        "tts_max_chars_per_request": int(
            db.get_setting("tts_max_chars_per_request", str(TTS_MAX_CHARS_PER_REQUEST))
        ),
        # Limits of the global tools, in minutes and MB as on the card.
        "screencast_max_slides": tool_limits.max_screencast_slides(),
        "transcription_max_minutes": tool_limits.max_transcription_seconds() // 60,
        "upload_max_mb": tool_limits.max_upload_bytes() // (1024 * 1024),
        "results_kept_per_user": tool_limits.results_kept_per_user(),
        "screencast_max_open_jobs": tool_limits.max_open_screencast_jobs(),
        # The assessment prompt, a placeholder carries the language.
        "language_diagnosis_prompt": db.get_setting(
            "language_diagnosis_prompt", DEFAULT_DIAGNOSIS_PROMPT
        ),
        "language_diagnosis_prompt_default": DEFAULT_DIAGNOSIS_PROMPT,
        # The question plan, empty means the default is active.
        "language_diagnosis_question_plan_de": db.get_setting(QUESTION_PLAN_SETTING, ""),
        # The German tab fills it and resets to the shipped German set.
        "language_diagnosis_question_plan_default": DEFAULT_GERMAN_QUESTION_PLAN,
        "language_diagnosis_answer_max_chars": int(
            db.get_setting(ANSWER_MAX_CHARS_SETTING, str(DEFAULT_ANSWER_MAX_CHARS))
        ),
        # A stored old default counts as not set.
        "language_diagnosis_adaptive_behavior": resolve_prompt_setting(
            db.get_setting(ADAPTIVE_BEHAVIOR_SETTING, ""),
            _LEGACY_ADAPTIVE_BEHAVIOR,
            DEFAULT_ADAPTIVE_BEHAVIOR,
        ),
        "language_diagnosis_adaptive_behavior_default": DEFAULT_ADAPTIVE_BEHAVIOR,
        # Grading method plus the level ladder with description and examples.
        "language_diagnosis_grading_rules": resolve_prompt_setting(
            db.get_setting(GRADING_RULES_SETTING, ""),
            _LEGACY_GRADING_RULES,
            DEFAULT_GRADING_RULES,
        ),
        "language_diagnosis_grading_rules_default": DEFAULT_GRADING_RULES,
        "language_diagnosis_level_examples": db.get_setting(LEVEL_EXAMPLES_SETTING, ""),
        "language_diagnosis_level_examples_default": DEFAULT_LEVEL_EXAMPLES,
        "language_diagnosis_example_levels": EXAMPLE_LEVELS,
        "language_diagnosis_level_descriptions": db.get_setting(
            LEVEL_DESCRIPTIONS_SETTING, ""
        ),
        "language_diagnosis_level_descriptions_default": DEFAULT_LEVEL_DESCRIPTIONS,
    }


@router.patch("/settings")
async def update_settings(
    body: UpdateSettingsRequest,
    admin=Depends(require_any_settings),
    locale: str = Depends(get_locale),
):
    _assert_fields_allowed(body, permissions_of(admin), locale)

    if body.whitelist_enabled is not None:
        db.set_setting("whitelist_enabled", "true" if body.whitelist_enabled else "false")

    # The language trainer off hides it everywhere, the per-course choice stays.
    if body.language_training_enabled is not None:
        db.set_setting(
            "language_training_enabled", "true" if body.language_training_enabled else "false"
        )

    # The notice banner switch is independent of the text, the text is length limited.
    if body.home_notice_enabled is not None:
        db.set_setting("home_notice_enabled", "true" if body.home_notice_enabled else "false")

    if body.home_notice_text is not None:
        stripped = body.home_notice_text.strip()
        if len(stripped) > 1000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.homeNoticeTooLong", locale, max=1000),
            )
        db.set_setting("home_notice_text", stripped)

    if body.ocr_enabled is not None:
        db.set_setting("ocr_enabled", "true" if body.ocr_enabled else "false")

    # An empty prompt saves the default, the assessment is never without instructions.
    if body.language_diagnosis_prompt is not None:
        stripped = body.language_diagnosis_prompt.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting("language_diagnosis_prompt", stripped or DEFAULT_DIAGNOSIS_PROMPT)

    # An empty plan resets it, a filled one must be valid.
    if body.language_diagnosis_question_plan_de is not None:
        stripped = body.language_diagnosis_question_plan_de.strip()
        if not stripped:
            db.set_setting(QUESTION_PLAN_SETTING, "")
        elif not question_plan_is_valid(stripped):
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanInvalid", locale),
            )
        elif (incomplete := first_incomplete_question(stripped)) is not None:
            # Half a line can no longer be saved, the message names the line number.
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanIncomplete", locale,
                         number=incomplete),
            )
        elif not question_plan_has_enough_free_text(stripped):
            # A plan without enough free text would rest the level on nothing written.
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanTooFewFreeText", locale,
                         min=MIN_FREE_TEXT_QUESTIONS),
            )
        else:
            db.set_setting(QUESTION_PLAN_SETTING, stripped)

    # Soft answer length, it only steers the display.
    if body.language_diagnosis_answer_max_chars is not None:
        value = body.language_diagnosis_answer_max_chars
        if value < 1 or value > MAX_MESSAGE_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.answerMaxCharsOutOfRange", locale, min=1, max=MAX_MESSAGE_CHARS),
            )
        db.set_setting(ANSWER_MAX_CHARS_SETTING, str(value))

    # Empty input resets to the default.
    if body.language_diagnosis_adaptive_behavior is not None:
        stripped = body.language_diagnosis_adaptive_behavior.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting(ADAPTIVE_BEHAVIOR_SETTING, stripped or DEFAULT_ADAPTIVE_BEHAVIOR)

    # Empty input resets to the default.
    if body.language_diagnosis_grading_rules is not None:
        stripped = body.language_diagnosis_grading_rules.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting(GRADING_RULES_SETTING, stripped or DEFAULT_GRADING_RULES)

    # Examples per level as JSON, empty resets, otherwise it is validated.
    if body.language_diagnosis_level_examples is not None:
        stripped = body.language_diagnosis_level_examples.strip()
        if not stripped:
            db.set_setting(LEVEL_EXAMPLES_SETTING, "")
        else:
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                data = None
            valid = (
                isinstance(data, dict)
                and bool(data)
                and all(
                    k in EXAMPLE_LEVELS and isinstance(v, str)
                    for k, v in data.items()
                )
            )
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.diagnosisExamplesInvalid", locale),
                )
            db.set_setting(LEVEL_EXAMPLES_SETTING, stripped)

    # Description per level as JSON, empty resets, otherwise it is validated.
    if body.language_diagnosis_level_descriptions is not None:
        stripped = body.language_diagnosis_level_descriptions.strip()
        if not stripped:
            db.set_setting(LEVEL_DESCRIPTIONS_SETTING, "")
        else:
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                data = None
            valid = (
                isinstance(data, dict)
                and bool(data)
                and all(
                    k in LEVELS and isinstance(v, str)
                    for k, v in data.items()
                )
            )
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.diagnosisExamplesInvalid", locale),
                )
            db.set_setting(LEVEL_DESCRIPTIONS_SETTING, stripped)

    # UI label overrides for "Workspace" (per UI locale)
    for label_key in (
        "workspace_label_singular_de",
        "workspace_label_plural_de",
        "workspace_label_singular_en",
        "workspace_label_plural_en",
    ):
        value = getattr(body, label_key)
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.labelEmpty", locale, label=label_key),
                )
            if len(stripped) > 40:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.labelTooLong", locale, label=label_key),
                )
            db.set_setting(label_key, stripped)

    # Limit of sources per course room, capped against typos.
    if body.aia_workspace_max_sources is not None:
        value = body.aia_workspace_max_sources
        if value < 1 or value > 1000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.maxSourcesOutOfRange", locale, min=1, max=1000),
            )
        db.set_setting("aia_workspace_max_sources", str(value))

    # Context budget of the chat, capped against too small and too large inputs.
    if body.aia_context_max_chars is not None:
        value = body.aia_context_max_chars
        if value < 1000 or value > AIA_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.contextBudgetOutOfRange", locale, min=1000, max=AIA_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_context_max_chars", str(value))

    # Context of a specific question, the same limits as for the overview.
    if body.aia_specific_max_chars is not None:
        value = body.aia_specific_max_chars
        if value < 1000 or value > AIA_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.contextBudgetOutOfRange", locale, min=1000, max=AIA_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_specific_max_chars", str(value))

    # Context budget of the tools, with its own higher ceiling.
    if body.aia_tool_context_max_chars is not None:
        value = body.aia_tool_context_max_chars
        if value < 1000 or value > AIA_TOOL_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.toolContextBudgetOutOfRange", locale, min=1000, max=AIA_TOOL_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_tool_context_max_chars", str(value))

    # Only a code from the one list, otherwise it would end up verbatim in the job.
    if body.aia_learning_tools_language is not None:
        value = (body.aia_learning_tools_language or "").strip().lower()
        if value not in TRANSCRIPT_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.learningToolsLanguageUnknown", locale),
            )
        db.set_setting("aia_learning_tools_language", value)

    # Characters per summary batch, capped against typos.
    if body.aia_summary_batch_max_chars is not None:
        value = body.aia_summary_batch_max_chars
        if value < 10_000 or value > 500_000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.summaryBatchOutOfRange", locale, min=10_000, max=500_000),
            )
        db.set_setting("aia_summary_batch_max_chars", str(value))

    # Chunks per embedding call no longer live here, the client measures itself.

    # Maximum pages per source, capped from 1 to 2000.
    if body.aia_source_max_pages is not None:
        value = body.aia_source_max_pages
        if value < 1 or value > 2000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.maxPagesOutOfRange", locale, min=1, max=2000),
            )
        db.set_setting("aia_source_max_pages", str(value))

    # Limits of the global tools, there is no unlimited here.
    for feld, schluessel, unten, oben, darf_unbegrenzt in (
        (body.screencast_max_slides, "screencast_max_slides", 1, 200, False),
        (body.transcription_max_minutes, "transcription_max_minutes", 5, 480, False),
        (body.upload_max_mb, "upload_max_mb", 10, 2000, False),
        (body.results_kept_per_user, "results_kept_per_user", 1, 10000, True),
        (body.screencast_max_open_jobs, "screencast_max_open_jobs", 1, 100, True),
    ):
        if feld is None:
            continue
        if not (unten <= feld <= oben) and not (darf_unbegrenzt and feld == -1):
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.toolLimitOutOfRange", locale, min=unten, max=oben),
            )
        db.set_setting(schluessel, str(feld))

    # Empty is valid and turns the speaker off.
    if body.aia_flashcard_voice_provider_id is not None:
        raw = body.aia_flashcard_voice_provider_id.strip()
        if raw and not raw.isdigit():
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.flashcardVoiceProviderInvalid", locale),
            )
        db.set_setting("aia_flashcard_voice_provider_id", raw)

    if body.aia_flashcard_voice_id is not None:
        db.set_setting("aia_flashcard_voice_id", body.aia_flashcard_voice_id.strip())

    # Too large runs into the timeout, too small fragments the recording.
    if body.tts_max_chars_per_request is not None:
        value = body.tts_max_chars_per_request
        if value < 50 or value > 10_000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.ttsMaxCharsOutOfRange", locale, min=50, max=10_000),
            )
        db.set_setting("tts_max_chars_per_request", str(value))

    return {"ok": True}
