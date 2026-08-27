"""Settings endpoints: read + update system-level admin settings.

Provider selection, model names, feature routes, and any LLM-related
configuration are managed by the dedicated "KI" admin tab (see
``routes/admin/providers.py``) and live in the ``providers`` +
``feature_routes`` tables. The settings tab now only covers system-wide
toggles (whitelist, workspace label/limits, schedule retention).
"""

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
    """Jedes mitgeschickte Feld einzeln gegen das Recht seiner Seite pruefen.

    Der Datensatz bedient mehrere Seiten des Bereichs auf einmal. Ohne diese
    Pruefung koennte jemand mit dem Recht fuer eine einzige Seite jedes Feld
    jeder anderen Seite mitschicken, etwa den Wartungsmodus.

    Ein Feld, das im Katalog fehlt, gilt als nicht speicherbar. Lieber eine
    Absage als ein Loch, das beim naechsten neuen Feld aufgeht.
    """
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
        # Sprachtrainer (system-wide, off by default). Owners can only switch the
        # trainer on in their workspace while this is on.
        "language_training_enabled": _enabled("language_training_enabled", "false"),
        # Home-page notice banner (all users, above "Nächste Termine").
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
        # Kontext einer gezielten Frage, getrennt vom Ueberblick-Budget darueber.
        "aia_specific_max_chars": int(
            db.get_setting("aia_specific_max_chars", str(AIA_SPECIFIC_MAX_CHARS))
        ),
        # Context budget (chars) for the generation tools (mindmap, data table, quiz, …).
        # Separate from the chat budget; divided by the number of sources at generation time.
        "aia_tool_context_max_chars": int(
            db.get_setting("aia_tool_context_max_chars", str(AIA_TOOL_CONTEXT_MAX_CHARS))
        ),
        # Sprache der vier Lern-Tools (Karteikarten, Quiz, Datentabelle, Mindmap).
        # Der Sprachtrainer folgt dem bewusst nicht, der bleibt deutsch.
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
        # Aussprache auf der Lernkarte. Leer heißt für die Oberfläche: noch nicht
        # eingerichtet, dann zeigt die Karte keinen Lautsprecher.
        "aia_flashcard_voice_provider_id": db.get_setting("aia_flashcard_voice_provider_id", ""),
        "aia_flashcard_voice_id": db.get_setting("aia_flashcard_voice_id", ""),
        # Zeichen je Sprachausgabe-Anfrage. Der Anbieter bricht nach einer festen
        # Zeit ab, nicht nach einer festen Länge, siehe Messung in limits.py.
        # Bleibt einstellbar, weil das eine ANBIETER-EIGENSCHAFT ist, die sich
        # nicht aus Absagen ablesen lässt: die Anfrage läuft in einen Timeout,
        # nicht in eine Absage. Alles, was sich messen oder erkennen lässt, ist
        # dagegen aus diesem Bereich verschwunden.
        "tts_max_chars_per_request": int(
            db.get_setting("tts_max_chars_per_request", str(TTS_MAX_CHARS_PER_REQUEST))
        ),
        # Grenzen der globalen Werkzeuge. Nicht aus limits.py gelesen, sondern
        # ueber tool_limits, damit hier genau der Wert steht, den die Routen
        # gerade benutzen. Minuten und MB, nicht Sekunden und Bytes: der Admin
        # tippt die Einheit, die auf der Karte steht.
        "screencast_max_slides": tool_limits.max_screencast_slides(),
        "transcription_max_minutes": tool_limits.max_transcription_seconds() // 60,
        "upload_max_mb": tool_limits.max_upload_bytes() // (1024 * 1024),
        "results_kept_per_user": tool_limits.results_kept_per_user(),
        "screencast_max_open_jobs": tool_limits.max_open_screencast_jobs(),
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
        # Die beiden Prompt-Texte laufen ueber resolve_prompt_setting: ein
        # gespeicherter ALTER Standard (mit eigener Stufen-Liste) zaehlt als "nicht
        # gesetzt", sonst zeigt die Karte weiter die Liste, die jetzt aus der
        # Stufen-Leiter kommt.
        "language_diagnosis_adaptive_behavior": resolve_prompt_setting(
            db.get_setting(ADAPTIVE_BEHAVIOR_SETTING, ""),
            _LEGACY_ADAPTIVE_BEHAVIOR,
            DEFAULT_ADAPTIVE_BEHAVIOR,
        ),
        "language_diagnosis_adaptive_behavior_default": DEFAULT_ADAPTIVE_BEHAVIOR,
        # LEVEL ASSIGNMENT: grading procedure + the Stufen-Leiter (descriptions and
        # calibration examples per level).
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

    # Switching the Sprachtrainer off hides it everywhere but keeps each workspace's
    # own choice, so switching it back on restores the previous state.
    if body.language_training_enabled is not None:
        db.set_setting(
            "language_training_enabled", "true" if body.language_training_enabled else "false"
        )

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
        elif (incomplete := first_incomplete_question(stripped)) is not None:
            # Eine halbe Zeile hat frueher bedeutet "das Modell schreibt die Frage
            # waehrend des Tests". Diesen Weg gibt es nicht mehr, also darf sie gar
            # nicht erst gespeichert werden. Die Meldung nennt die Zeilennummer.
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.diagnosisPlanIncomplete", locale,
                         number=incomplete),
            )
        elif not question_plan_has_enough_free_text(stripped):
            # A plan without enough AI-judged free texts could only be graded on
            # recognition (choice questions, and gaps with a solution key), so the
            # level would rest on nothing the learner actually produced. Reject it
            # with a specific message.
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

    # Beschreibung je Stufe (JSON-Objekt). Leer bedeutet zuruecksetzen. Sonst muss
    # es ein Objekt mit bekannten Stufen und String-Werten sein, damit ein Tippfehler
    # nichts Unbrauchbares speichert. Gleiche Regel wie bei den Beispielen.
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

    # Kontext einer gezielten Frage. Dieselben Grenzen wie beim Ueberblick-Budget:
    # die kleinere der beiden Zahlen gewinnt ohnehin an der Auswertung.
    if body.aia_specific_max_chars is not None:
        value = body.aia_specific_max_chars
        if value < 1000 or value > AIA_CONTEXT_HARD_CAP:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.contextBudgetOutOfRange", locale, min=1000, max=AIA_CONTEXT_HARD_CAP),
            )
        db.set_setting("aia_specific_max_chars", str(value))

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

    # Sprache der vier Lern-Tools. Nur ein Code aus der einen Liste, sonst stuende er
    # spaeter wortwoertlich im Auftrag an das Modell ("Write it in xx").
    if body.aia_learning_tools_language is not None:
        value = (body.aia_learning_tools_language or "").strip().lower()
        if value not in TRANSCRIPT_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.learningToolsLanguageUnknown", locale),
            )
        db.set_setting("aia_learning_tools_language", value)

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

    # Chunks pro Embedding-Aufruf steht hier bewusst nicht mehr: der Regler konnte
    # nur unter den Standard, und der Client misst die Grenze jetzt selbst
    # (aia_embeddings, Halbieren bei Absage). Siehe AIA_EMBEDDING_BATCH_SIZE.

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

    # Grenzen der globalen Werkzeuge. Die Obergrenzen sind keine Meinung: ein
    # Screencast bricht nach zwei Stunden ab (SCREENCAST_TIME_LIMIT), eine zu
    # lange Aufnahme wird beim Anbieter abgelehnt, und eine riesige Datei fuellt
    # die Platte. Deshalb gibt es dort auch kein Unbegrenzt.
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

    # Aussprache auf der Lernkarte. Leer ist ein gültiger Wert und schaltet den
    # Lautsprecher ab, deshalb wird die leere Zeichenkette durchgelassen.
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

    # Zeichen je Sprachausgabe-Anfrage. Zu groß gewählt läuft jede Anfrage in
    # den Timeout des Anbieters, zu klein gewählt wird die Aufnahme zerstückelt.
    if body.tts_max_chars_per_request is not None:
        value = body.tts_max_chars_per_request
        if value < 50 or value > 10_000:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.ttsMaxCharsOutOfRange", locale, min=50, max=10_000),
            )
        db.set_setting("tts_max_chars_per_request", str(value))

    return {"ok": True}
