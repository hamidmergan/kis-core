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
    AIA_PARALLEL_SLOTS,
    AIA_SUMMARY_BATCH_MAX_CHARS,
    AIA_EMBEDDING_BATCH_SIZE,
    AIA_SOURCE_MAX_PAGES,
    AIA_WORKSPACE_MAX_SOURCES,
)

from src.routes.admin._models import UpdateSettingsRequest

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

    if body.ocr_enabled is not None:
        db.set_setting("ocr_enabled", "true" if body.ocr_enabled else "false")

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

    return {"ok": True}
