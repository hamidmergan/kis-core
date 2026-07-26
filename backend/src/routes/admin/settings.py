"""Settings endpoints: read + update system-level admin settings.

Provider selection, model names, feature routes, and any LLM-related
configuration are managed by the dedicated "KI" admin tab (see
``routes/admin/providers.py``) and live in the ``providers`` +
``feature_routes`` tables. The settings tab now only covers system-wide
toggles (whitelist, mascot, workspace label/limits, schedule retention).
"""

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_admin_user
from src.i18n import get_locale, t
from src.limits import (
    AIA_CONTEXT_MAX_CHARS,
    AIA_CONTEXT_HARD_CAP,
    AIA_TOOL_CONTEXT_MAX_CHARS,
    AIA_TOOL_CONTEXT_HARD_CAP,
    AIA_PARALLEL_SLOTS,
    AIA_MAX_CONCURRENT_UPLOADS,
    AIA_SUMMARY_BATCH_MAX_CHARS,
    AIA_EMBEDDING_BATCH_SIZE,
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
)

import json

from src.routes.admin._models import UpdateSettingsRequest
from src.services.aia_diagnosis_chat import (
    ADAPTIVE_BEHAVIOR_SETTING,
    ANSWER_MAX_CHARS_SETTING,
    DEFAULT_ANSWER_MAX_CHARS,
    DEFAULT_DIAGNOSIS_PROMPT,
    DEFAULT_GERMAN_QUESTION_PLAN,
    DEFAULT_GRADING_RULES,
    DEFAULT_LEVEL_EXAMPLES,
    EXAMPLE_LEVELS,
    GRADING_RULES_SETTING,
    LEVEL_EXAMPLES_SETTING,
    MAX_MESSAGE_CHARS,
    MAX_PROMPT_CHARS,
    MIN_FREE_TEXT_QUESTIONS,
    QUESTION_PLAN_SETTING,
    question_plan_has_enough_free_text,
    question_plan_is_valid,
)
from src.services.aia_adaptive_chat import DEFAULT_ADAPTIVE_BEHAVIOR

router = APIRouter(tags=["admin: settings"])


@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    def _enabled(key: str, default: str = "true") -> bool:
        return db.get_setting(key, default).lower() == "true"

    return {
        "whitelist_enabled": _enabled("whitelist_enabled"),
        # UI labels (per locale; legacy unsuffixed keys fall back as DE defaults)
        "workspace_label_singular_de": db.get_setting(
            "workspace_label_singular_de",
            db.get_setting("workspace_label_singular", "Workspace"),
        ),
        "workspace_label_plural_de": db.get_setting(
            "workspace_label_plural_de",
            db.get_setting("workspace_label_plural", "Workspaces"),
        ),
        "workspace_label_singular_en": db.get_setting("workspace_label_singular_en", "Workspace"),
        "workspace_label_plural_en": db.get_setting("workspace_label_plural_en", "Workspaces"),
        # Hilde mascot (system-wide)
        "mascot_enabled": _enabled("mascot_enabled"),
        # Home-page notice banner (all users, above "Nächste Termine").
        "home_notice_enabled": _enabled("home_notice_enabled", "false"),
        "home_notice_text": db.get_setting("home_notice_text", ""),
        # OCR on image-heavy pages during indexing (system-wide, default on)
        "ocr_enabled": _enabled("ocr_enabled"),
        # Workspace limits (admin-tunable)
        "aia_workspace_max_sources": int(
            db.get_setting("aia_workspace_max_sources", str(AIA_WORKSPACE_MAX_SOURCES))
        ),
        # Schedule retention (admin-tunable). -1 = never delete (UI: empty input)
        "aia_schedule_retention_days": int(
            db.get_setting("aia_schedule_retention_days", "-1")
        ),
        # KI-tutor chat context budget (chars). Default sized for 32k models.
        "aia_context_max_chars": int(
            db.get_setting("aia_context_max_chars", str(AIA_CONTEXT_MAX_CHARS))
        ),
        # Context budget (chars) for the generation tools (mindmap, data table, quiz, …).
        # Separate from the chat budget; divided by the number of sources at generation time.
        "aia_tool_context_max_chars": int(
            db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS))
        ),
        # Ingest-side DOC SUMMARY per-batch char cap (bigger = fewer summary calls).
        "aia_summary_batch_max_chars": int(
            db.get_setting("aia_summary_batch_max_chars", str(AIA_SUMMARY_BATCH_MAX_CHARS))
        ),
        # Chunks per embedding request at ingest (higher = fewer embedding calls).
        "aia_embedding_batch_size": int(
            db.get_setting("aia_embedding_batch_size", str(AIA_EMBEDDING_BATCH_SIZE))
        ),
        # Max pages per uploaded source (long scripts → upload chapter-wise).
        "aia_source_max_pages": int(
            db.get_setting("aia_source_max_pages", str(AIA_SOURCE_MAX_PAGES))
        ),
        # Background dispatcher: master switch (default off) + shared parallel-slot
        # pool size (0 = unlimited, for when we run on our own GPU).
        "aia_scheduler_enabled": _enabled("aia_scheduler_enabled", "false"),
        "aia_parallel_slots": int(
            db.get_setting("aia_parallel_slots", str(AIA_PARALLEL_SLOTS))
        ),
        # Max simultaneous uploads in the HTTP layer (0 = unlimited). Protects the
        # small box from RAM/CPU spikes when many people upload large media at once.
        "aia_max_concurrent_uploads": int(
            db.get_setting("aia_max_concurrent_uploads", str(AIA_MAX_CONCURRENT_UPLOADS))
        ),
        # CEFR chat-diagnosis system prompt. One prompt for all languages; the
        # workspace language replaces the {language} placeholder at request time.
        "language_diagnosis_prompt": db.get_setting(
            "language_diagnosis_prompt", DEFAULT_DIAGNOSIS_PROMPT
        ),
        "language_diagnosis_prompt_default": DEFAULT_DIAGNOSIS_PROMPT,
        # Question plan. Empty stored string means "default active"; the frontend
        # falls back to the default plan for its table.
        "language_diagnosis_question_plan_de": db.get_setting(QUESTION_PLAN_SETTING, ""),
        # The German config tab prefills and resets to the shipped authored German
        # set (options, correct flags, examples), which is also what a German
        # diagnosis runs with when nothing is stored.
        "language_diagnosis_question_plan_default": DEFAULT_GERMAN_QUESTION_PLAN,
        "language_diagnosis_answer_max_chars": int(
            db.get_setting(ANSWER_MAX_CHARS_SETTING, str(DEFAULT_ANSWER_MAX_CHARS))
        ),
        "language_diagnosis_adaptive_behavior": db.get_setting(
            ADAPTIVE_BEHAVIOR_SETTING, DEFAULT_ADAPTIVE_BEHAVIOR
        ),
        "language_diagnosis_adaptive_behavior_default": DEFAULT_ADAPTIVE_BEHAVIOR,
        # LEVEL ASSIGNMENT: grading rules + per-level calibration examples.
        "language_diagnosis_grading_rules": db.get_setting(
            GRADING_RULES_SETTING, DEFAULT_GRADING_RULES
        ),
        "language_diagnosis_grading_rules_default": DEFAULT_GRADING_RULES,
        "language_diagnosis_level_examples": db.get_setting(LEVEL_EXAMPLES_SETTING, ""),
        "language_diagnosis_level_examples_default": DEFAULT_LEVEL_EXAMPLES,
        "language_diagnosis_example_levels": EXAMPLE_LEVELS,
        # Lernprofil: how many days a tracked weakness keeps decaying before it
        # drops out of the profile entirely.
        "learner_profile_window_days": int(
            db.get_setting("learner_profile_window_days", "30")
        ),
    }


@router.patch("/settings")
async def update_settings(
    body: UpdateSettingsRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    if body.whitelist_enabled is not None:
        db.set_setting("whitelist_enabled", "true" if body.whitelist_enabled else "false")

    if body.mascot_enabled is not None:
        db.set_setting("mascot_enabled", "true" if body.mascot_enabled else "false")

    # Home-page notice banner. Toggle is independent of the text so an admin can
    # keep a drafted message and flip it on/off. Text is length-capped so a paste
    # accident can't blow up the start page; empty text is allowed (banner stays
    # hidden until something is typed even when the toggle is on).
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

    # CEFR chat-diagnosis prompt. Empty input is the documented "reset" gesture:
    # it stores the shipped default rather than an empty prompt, so the diagnosis
    # can never end up without instructions.
    if body.language_diagnosis_prompt is not None:
        stripped = body.language_diagnosis_prompt.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting("language_diagnosis_prompt", stripped or DEFAULT_DIAGNOSIS_PROMPT)

    # Question plan (JSON). Empty string is the reset gesture (default plan). A
    # non-empty value must be a valid plan: a list of {type} with optional text
    # and, for option types, an option set with a correct flag. Muck is rejected
    # with a 400 so a typo cannot silently store something the diagnosis then
    # falls back away from.
    if body.language_diagnosis_question_plan_de is not None:
        stripped = body.language_diagnosis_question_plan_de.strip()
        if not stripped:
            db.set_setting(QUESTION_PLAN_SETTING, "")
        elif not question_plan_is_valid(stripped):
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanInvalid", locale),
            )
        elif not question_plan_has_enough_free_text(stripped):
            # A plan without enough free-text questions could only be graded on
            # recognition (multiple choice), so the level would rest on nothing
            # the learner actually produced. Reject it with a specific message.
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanTooFewFreeText", locale,
                         min=MIN_FREE_TEXT_QUESTIONS),
            )
        else:
            db.set_setting(QUESTION_PLAN_SETTING, stripped)

    # Soft answer-length cap (chars). Bounded 1..MAX_MESSAGE_CHARS: it only drives
    # the UI counter and maxlength; the request body stays hard-capped server-side.
    if body.language_diagnosis_answer_max_chars is not None:
        value = body.language_diagnosis_answer_max_chars
        if value < 1 or value > MAX_MESSAGE_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.answerMaxCharsOutOfRange", locale, min=1, max=MAX_MESSAGE_CHARS),
            )
        db.set_setting(ANSWER_MAX_CHARS_SETTING, str(value))

    # Adaptive answer behaviour. Empty input restores the shipped default, so the
    # chat is never left without behaviour text when the setting exists.
    if body.language_diagnosis_adaptive_behavior is not None:
        stripped = body.language_diagnosis_adaptive_behavior.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting(ADAPTIVE_BEHAVIOR_SETTING, stripped or DEFAULT_ADAPTIVE_BEHAVIOR)

    # Grading rules (LEVEL ASSIGNMENT). Empty input restores the shipped default,
    # so the diagnosis is never left without leveling logic.
    if body.language_diagnosis_grading_rules is not None:
        stripped = body.language_diagnosis_grading_rules.strip()
        if len(stripped) > MAX_PROMPT_CHARS:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPromptTooLong", locale, max=MAX_PROMPT_CHARS),
            )
        db.set_setting(GRADING_RULES_SETTING, stripped or DEFAULT_GRADING_RULES)

    # Per-level calibration examples (JSON object). Empty input = reset to
    # defaults. Otherwise it must be a JSON object whose keys are known bands and
    # whose values are strings, so a typo cannot store something unusable.
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

    # Lernprofil decay window (days). Bounded to at least 1 so the profile can
    # never be configured into decaying everything instantly.
    if body.learner_profile_window_days is not None:
        days = max(1, int(body.learner_profile_window_days))
        db.set_setting("learner_profile_window_days", str(days))

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

    # Workspace source upload cap. Bounded to a sane range so a typo can't
    # render the upload endpoint useless or unbounded.
    if body.aia_workspace_max_sources is not None:
        value = body.aia_workspace_max_sources
        if value < 1 or value > 1000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.maxSourcesOutOfRange", locale, min=1, max=1000),
            )
        db.set_setting("aia_workspace_max_sources", str(value))

    # Schedule retention in days. -1 disables pruning entirely (UI: empty
    # field). Otherwise must be 1..3650 so a typo cannot effectively disable
    # retention or trigger a zero-day prune.
    if body.aia_schedule_retention_days is not None:
        value = body.aia_schedule_retention_days
        if value != -1 and (value < 1 or value > 3650):
            raise HTTPException(
                status_code=400,
                detail=t(
                    "admin.settings.scheduleRetentionOutOfRange",
                    locale,
                    min=1,
                    max=3650,
                ),
            )
        db.set_setting("aia_schedule_retention_days", str(value))

    # KI-tutor context budget in characters. Bounded so a typo cannot starve the
    # context (too low) or blow past even large model windows (too high). Lower
    # bound ~ one small chunk; hard upper bound = AIA_CONTEXT_HARD_CAP (single
    # source of truth, ~228k tokens) so an admin typo (1M+) can't force a context
    # that stalls/overflows the model.
    if body.aia_context_max_chars is not None:
        value = body.aia_context_max_chars
        if value < 1000 or value > AIA_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.contextBudgetOutOfRange", locale, min=1000, max=AIA_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_context_max_chars", str(value))

    # Generation-tools context budget in characters. Same lower bound as the chat
    # budget; upper bound = AIA_TOOL_CONTEXT_HARD_CAP (higher than the chat cap, the
    # tools pack a whole document into one call and may run on a large/cloud model).
    if body.aia_tool_context_max_chars is not None:
        value = body.aia_tool_context_max_chars
        if value < 1000 or value > AIA_TOOL_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.toolContextBudgetOutOfRange", locale, min=1000, max=AIA_TOOL_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_tool_context_max_chars", str(value))

    # Summary per-batch char cap. Lower bound ~ one chunk; upper bound 500k chars
    # (~140k tokens) so an admin typo can't push a single summary batch past even
    # a large model window. Bigger = fewer (coarser) summary calls per upload.
    if body.aia_summary_batch_max_chars is not None:
        value = body.aia_summary_batch_max_chars
        if value < 10_000 or value > 500_000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.summaryBatchOutOfRange", locale, min=10_000, max=500_000),
            )
        db.set_setting("aia_summary_batch_max_chars", str(value))

    # Embedding chunks-per-request. Upper bound 1000 = measured server-safe ceiling
    # (2000 → 502 on the embedding endpoint); higher = fewer rate-limited requests.
    if body.aia_embedding_batch_size is not None:
        value = body.aia_embedding_batch_size
        if value < 1 or value > 1000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.embeddingBatchOutOfRange", locale, min=1, max=1000),
            )
        db.set_setting("aia_embedding_batch_size", str(value))

    # Max pages per uploaded source. Bounded 1..2000: keeps sources near the
    # fit-shortcut size (complete overview) and rejects monster docs (split into
    # chapters). Default 100; an admin can raise it for low-density slide decks.
    if body.aia_source_max_pages is not None:
        value = body.aia_source_max_pages
        if value < 1 or value > 2000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.maxPagesOutOfRange", locale, min=1, max=2000),
            )
        db.set_setting("aia_source_max_pages", str(value))

    # Background dispatcher master switch.
    if body.aia_scheduler_enabled is not None:
        db.set_setting("aia_scheduler_enabled", "true" if body.aia_scheduler_enabled else "false")

    # Shared parallel-slot pool size. 0 = unlimited (own-GPU future); upper bound
    # keeps a typo from spawning a runaway number of in-flight jobs.
    if body.aia_parallel_slots is not None:
        value = body.aia_parallel_slots
        if value < 0 or value > 100:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.parallelSlotsOutOfRange", locale, min=0, max=100),
            )
        db.set_setting("aia_parallel_slots", str(value))

    # Max simultaneous uploads. 0 = unlimited; upper bound keeps a typo from
    # letting the small box accept a runaway number of in-flight uploads.
    if body.aia_max_concurrent_uploads is not None:
        value = body.aia_max_concurrent_uploads
        if value < 0 or value > 100:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.maxConcurrentUploadsOutOfRange", locale, min=0, max=100),
            )
        db.set_setting("aia_max_concurrent_uploads", str(value))

    return {"ok": True}
