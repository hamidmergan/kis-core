# AIA Transcript Translation Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `"deepl"/"llm"` string dispatch for AIA transcript translation with a dynamic `transcript_translate` feature route configurable in the admin KI panel.

**Architecture:** Add `transcript_translate` as a new feature to the feature-routes system (backend `FEATURES` tuple + frontend `Feature` type + `FeatureRoutingCard`). The `regenerate_en_transcript` endpoint and the auto-dispatch during ingestion both resolve the provider via `feature_router.resolve("transcript_translate")`. The `_run_translate_transcript_en_inner` task switches from a `provider: str` string to `provider_id: int | None` and delegates dispatch to the existing `get_translate_client_for_provider()` helper.

**Tech Stack:** Python (FastAPI, Celery), TypeScript (Next.js/next-intl), PostgreSQL (feature_routes table)

---

### Task 1: Register `transcript_translate` in the backend feature registry

**Files:**
- Modify: `backend/src/features/ai_providers/repository/feature_routes.py:19-30`

- [ ] **Step 1: Add `transcript_translate` to the `FEATURES` tuple**

  In `feature_routes.py`, find the `FEATURES` tuple (line 19) and add `"transcript_translate"` after `"screencast_translate"`:

  ```python
  FEATURES: tuple[str, ...] = (
      "chat",
      "embedding",
      "vision",
      "ocr",
      "stt",
      "tts",
      "image_gen",
      "image_edit",
      "doc_translate",
      "screencast_translate",
      "transcript_translate",
  )
  ```

  Do NOT add it to `USER_CHOICE_FEATURES` — this is a single admin-configured provider.

- [ ] **Step 2: Verify the backend API returns it**

  Run:
  ```bash
  cd backend && python -c "from src.features.ai_providers.repository.feature_routes import FEATURES; print(FEATURES)"
  ```
  Expected: tuple contains `'transcript_translate'`.

- [ ] **Step 3: Commit**

  ```bash
  git add backend/src/features/ai_providers/repository/feature_routes.py
  git commit -m "feat(providers): register transcript_translate feature route"
  ```

---

### Task 2: Add `transcript_translate` to the frontend type and admin UI

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/_types.ts:12-22`
- Modify: `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx:29-60`
- Modify: `frontend/messages/en.json` (around line 923)
- Modify: `frontend/messages/de.json` (around line 923)

- [ ] **Step 1: Add `transcript_translate` to the `Feature` union type**

  In `_types.ts`, extend the `Feature` type:

  ```typescript
  export type Feature =
    | "chat"
    | "embedding"
    | "vision"
    | "ocr"
    | "stt"
    | "tts"
    | "image_gen"
    | "image_edit"
    | "doc_translate"
    | "screencast_translate"
    | "transcript_translate";
  ```

- [ ] **Step 2: Add capability mapping and display order in `FeatureRoutingCard.tsx`**

  **`FEATURE_CAPABILITY`** — add after `screencast_translate`:
  ```typescript
  const FEATURE_CAPABILITY: Record<Feature, Capability> = {
    chat: "chat",
    embedding: "embedding",
    vision: "vision",
    ocr: "ocr",
    stt: "stt",
    tts: "tts",
    image_gen: "image_gen",
    image_edit: "image_edit",
    doc_translate: "translation",
    screencast_translate: "translation",
    transcript_translate: "translation",
  };
  ```

  **`FEATURE_EXTRA_CAPABILITIES`** — add after `screencast_translate`:
  ```typescript
  const FEATURE_EXTRA_CAPABILITIES: Partial<Record<Feature, Capability[]>> = {
    doc_translate: ["chat"],
    screencast_translate: ["chat"],
    transcript_translate: ["chat"],
  };
  ```

  **`FEATURE_ORDER`** — add `"transcript_translate"` after `"doc_translate"`:
  ```typescript
  const FEATURE_ORDER: Feature[] = [
    "chat",
    "embedding",
    "vision",
    "image_gen",
    "image_edit",
    "ocr",
    "stt",
    "tts",
    "doc_translate",
    "transcript_translate",
  ];
  ```

  Note: `"screencast_translate"` is intentionally absent from `FEATURE_ORDER` (already the case in the current code — the admin panel doesn't show it as a standalone row).

- [ ] **Step 3: Add i18n strings to `en.json`**

  In `frontend/messages/en.json`, add to the `featureName` block (after `"screencast_translate"`):
  ```json
  "transcript_translate": "Transcript translation"
  ```

  Add to the `featureDesc` block (after `"screencast_translate"`):
  ```json
  "transcript_translate": "AIA workspace: translate DE transcript to EN. Provider is admin-configured."
  ```

  There are two `featureName` blocks in the file (around line 923 and 2003) — add the entry to both.

- [ ] **Step 4: Add i18n strings to `de.json`**

  In `frontend/messages/de.json`, add to the `featureName` block (after `"screencast_translate"`):
  ```json
  "transcript_translate": "Transkript-Übersetzung"
  ```

  Add to the `featureDesc` block (after `"screencast_translate"`):
  ```json
  "transcript_translate": "AIA-Arbeitsbereich: DE-Transkript auf EN übersetzen. Anbieter wird vom Admin konfiguriert."
  ```

  There are two `featureName` blocks in the file — add to both.

- [ ] **Step 5: Verify TypeScript compiles**

  ```bash
  cd frontend && npx tsc --noEmit 2>&1 | head -20
  ```
  Expected: no errors relating to `Feature` or `FEATURE_CAPABILITY`.

- [ ] **Step 6: Commit**

  ```bash
  git add frontend/src/app/\[locale\]/admin/_components/providers/_types.ts \
          frontend/src/app/\[locale\]/admin/_components/providers/FeatureRoutingCard.tsx \
          frontend/messages/en.json \
          frontend/messages/de.json
  git commit -m "feat(admin): add transcript_translate to feature routing UI"
  ```

---

### Task 3: Migrate `_run_translate_transcript_en_inner` to use `provider_id`

**Files:**
- Modify: `backend/src/features/ai_assistant/tasks/ingestion.py:257-361`

- [ ] **Step 1: Replace the string dispatch in `_run_translate_transcript_en_inner`**

  Find the function starting at line 280. Replace the `if provider == "llm": ... else: ...` block (lines 322–351) with a single call to `get_translate_client_for_provider`.

  Change the function signature and body:

  ```python
  def _run_translate_transcript_en_inner(source_uuid: str, provider_id: int | None) -> None:
      from src.services.subtitle_converter import vtt_to_segments, segments_to_vtt
      from src.storage import file_exists, get_file
      from src.dependencies import get_translate_client_for_provider

      source = db.get_aia_source(source_uuid)
      if source is None:
          logger.warning("KI Tutor EN-translate: source {} not found, skipping", source_uuid)
          return

      base_key = source["file_path"].rsplit(".", 1)[0]
      en_key = f"{base_key}_transcript.en.vtt"
      if file_exists(en_key):
          logger.info("KI Tutor EN-translate: {} already exists, skipping", en_key)
          return

      source_vtt_key: str | None = None
      source_lang: str | None = None
      for candidate_lang in ("de",):
          candidate_key = f"{base_key}_transcript.{candidate_lang}.vtt"
          if file_exists(candidate_key):
              source_vtt_key = candidate_key
              source_lang = candidate_lang
              break
      if not source_vtt_key or not source_lang:
          logger.warning(
              "KI Tutor EN-translate: no source VTT for {}, skipping", source_uuid
          )
          return

      segments = vtt_to_segments(get_file(source_vtt_key).decode("utf-8"))
      if not segments:
          logger.warning(
              "KI Tutor EN-translate: could not parse {}, skipping", source_vtt_key
          )
          return

      texts = [s["text"] for s in segments]
      lang_name_map = {"de": "German"}
      source_lang_name = lang_name_map.get(source_lang, source_lang)

      client, _glossary = get_translate_client_for_provider(provider_id)
      if client is None:
          raise RuntimeError("transcript_translate: no translation provider configured — set one in the admin KI panel")

      translated = client.translate_batch(
          texts, source_lang=source_lang_name, target_lang="English",
      )

      en_segments = [
          {"start": s["start"], "end": s["end"], "text": t_text}
          for s, t_text in zip(segments, translated)
      ]
      _save_transcript_artifact(en_key, segments_to_vtt(en_segments))
      logger.info(
          "KI Tutor EN-translate: saved {} ({} segments via provider_id={})",
          en_key, len(en_segments), provider_id,
      )
  ```

  Note: `get_translate_client_for_provider(None)` falls back to the first available translation provider. The call from the new `run_translate_transcript_en` task always passes an explicit `provider_id` resolved from the feature route, so `None` only occurs if called from legacy code.

  Note: DeepL's `translate_batch` expects `source_lang="EN"` style codes (uppercase ISO), while LLM accepts full language names like `"German"`. The existing LLM path already passes `source_lang_name` (e.g., `"German"`). The DeepL path in `get_translate_client_for_provider` returns a `DeepLClient` — check if `DeepLClient.translate_batch` accepts a full name or needs `"DE"`.

- [ ] **Step 2: Check `DeepLClient.translate_batch` signature**

  Run:
  ```bash
  grep -n "def translate_batch" /Users/hamidmergan/Projects/kis-thl/backend/src/services/deepl_client.py
  ```

  If it expects an uppercase code like `"DE"` instead of `"German"`, change the call to:
  ```python
  translated = client.translate_batch(
      texts,
      source_lang=source_lang.upper() if hasattr(client, "api_key") else source_lang_name,
      target_lang="EN-US" if hasattr(client, "api_key") else "English",
  )
  ```

  A cleaner approach: check the protocol of the resolved provider and pass the right format. However, since `get_translate_client_for_provider` already has this knowledge internally, verify whether `DeepLClient` and `LLMTranslationClient` share a common `translate_batch(texts, source_lang, target_lang)` interface that accepts the same formats, or whether they differ.

  If they differ, check how the `TranslationService` in `backend/src/services/translation_service.py` handles this — it likely normalises the call.

- [ ] **Step 3: Update `run_translate_transcript_en` Celery task signature**

  Change the Celery task at line 257:

  ```python
  @celery_app.task(bind=True, name="aia.translate_transcript_en", queue="aia")
  def run_translate_transcript_en(self, source_uuid: str, provider_id: int | None = None):
      """Translate a media source's source-language VTT to English.

      Runs as a follow-up to indexing so chat is available before translation completes.
      ``provider_id`` is resolved from the ``transcript_translate`` feature route.
      """
      try:
          return _run_translate_transcript_en_inner(source_uuid, provider_id)
      except Exception as e:
          msg = str(e).lower()
          is_rate_limit = "429" in msg or "rate limit" in msg
          if is_rate_limit and self.request.retries < 5:
              countdown = 60 * (2 ** self.request.retries)
              logger.warning(
                  "KI Tutor EN-translate: source {} hit rate limit (attempt {}/{}), retrying in {}s",
                  source_uuid, self.request.retries + 1, 5, countdown,
              )
              raise self.retry(exc=e, countdown=countdown, max_retries=5)
          logger.error("KI Tutor EN-translate: source {} failed: {}", source_uuid, e)
          raise
  ```

- [ ] **Step 4: Verify Python import check**

  ```bash
  cd backend && python -c "from src.features.ai_assistant.tasks.ingestion import run_translate_transcript_en; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 5: Commit**

  ```bash
  git add backend/src/features/ai_assistant/tasks/ingestion.py
  git commit -m "feat(aia): migrate transcript translation task to provider_id"
  ```

---

### Task 4: Replace `db.get_setting` in the ingestion auto-dispatch path

**Files:**
- Modify: `backend/src/features/ai_assistant/tasks/ingestion.py:171-182`

- [ ] **Step 1: Replace auto-dispatch at ingest time**

  Find the block at line 171–182 that reads:
  ```python
  if translation_mode == "auto":
      translation_provider = db.get_setting(
          "transcript_translation_provider", "llm"
      )
      run_translate_transcript_en.delay(source_uuid, translation_provider)
      logger.info(
          "KI Tutor: dispatched EN translation for {} (provider={})",
          source_uuid, translation_provider,
      )
  ```

  Replace with:
  ```python
  if translation_mode == "auto":
      from src.services import feature_router
      try:
          binding = feature_router.resolve("transcript_translate")
          run_translate_transcript_en.delay(source_uuid, binding["provider_id"])
          logger.info(
              "KI Tutor: dispatched EN translation for {} (provider_id={})",
              source_uuid, binding["provider_id"],
          )
      except feature_router.FeatureNotConfigured:
          logger.warning(
              "KI Tutor: transcript_translate not configured, skipping auto EN translation for {}",
              source_uuid,
          )
  ```

  Rationale: at ingest time, skipping silently when unconfigured is better than raising — the source is already indexed and functional; translation is an optional enhancement. The user can trigger it manually from the workspace once the feature is configured.

- [ ] **Step 2: Verify Python import check**

  ```bash
  cd backend && python -c "from src.features.ai_assistant.tasks.ingestion import run_index_source; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 3: Commit**

  ```bash
  git add backend/src/features/ai_assistant/tasks/ingestion.py
  git commit -m "feat(aia): resolve transcript_translate provider via feature_router at ingest"
  ```

---

### Task 5: Update the `regenerate_en_transcript` API endpoint

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/sources/_streaming.py:83-121`

- [ ] **Step 1: Replace `db.get_setting` with `feature_router.resolve`**

  Replace the entire `regenerate_en_transcript` endpoint body (lines 83–121). The key changes:
  - Remove `provider: Optional[str] = None` parameter
  - Replace `db.get_setting(...)` + `if effective_provider not in (...)` with `feature_router.resolve("transcript_translate")`
  - Pass `binding["provider_id"]` to `.delay()`
  - Return `provider_id` instead of provider string in the response

  New endpoint:

  ```python
  @router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/regenerate-en-transcript")
  async def regenerate_en_transcript(
      workspace_uuid: str,
      source_uuid: str,
      current_user: dict = Depends(get_current_user),
      locale: str = Depends(get_locale),
  ):
      """Dispatch an async Celery task to translate the source-language VTT to English.

      The translation provider is resolved from the ``transcript_translate`` feature route
      configured in the admin KI panel.
      """
      from src.services import feature_router

      workspace = _require_own_workspace(workspace_uuid, current_user["user_id"], locale=locale)
      source = db.get_aia_source(source_uuid)
      if not source:
          raise HTTPException(status_code=404, detail=t("source.notFound", locale))

      if workspace.get("transcript_translation_mode", "manual") == "off":
          raise HTTPException(status_code=403, detail=t("ai.transcript.translationDisabled", locale))

      try:
          binding = feature_router.resolve("transcript_translate")
      except feature_router.FeatureNotConfigured:
          raise HTTPException(
              status_code=503,
              detail="transcript_translate not configured — set a translation provider in the admin KI panel",
          )

      base_key = source["file_path"].rsplit(".", 1)[0]
      if not any(file_exists(f"{base_key}_transcript.{lang}.vtt") for lang in ("de",)):
          raise HTTPException(
              status_code=404,
              detail=t("ai.transcript.sourceMissing", locale),
          )

      from src.tasks.aia_tasks import run_translate_transcript_en
      run_translate_transcript_en.delay(source_uuid, binding["provider_id"])
      logger.info(
          "KI Tutor: manual EN translation dispatched for {} (provider_id={})",
          source_uuid, binding["provider_id"],
      )
      return {"uuid": source_uuid, "status": "dispatched", "provider_id": binding["provider_id"]}
  ```

- [ ] **Step 2: Verify Python import check**

  ```bash
  cd backend && python -c "from src.features.ai_assistant.routes.sources._streaming import router; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 3: Commit**

  ```bash
  git add backend/src/features/ai_assistant/routes/sources/_streaming.py
  git commit -m "feat(aia): resolve transcript translation provider via feature_router"
  ```

---

### Task 6: Verify DeepL/LLM translate_batch interface compatibility

**Files:**
- Read: `backend/src/services/deepl_client.py`
- Read: `backend/src/services/llm_translation_client.py`

This task resolves the open question from Task 3, Step 2. Check whether `DeepLClient.translate_batch` and `LLMTranslationClient.translate_batch` share the same call signature.

- [ ] **Step 1: Check `DeepLClient.translate_batch` signature**

  ```bash
  grep -n "def translate_batch" backend/src/services/deepl_client.py
  ```

- [ ] **Step 2: Check `LLMTranslationClient.translate_batch` signature**

  ```bash
  grep -n "def translate_batch" backend/src/services/llm_translation_client.py
  ```

- [ ] **Step 3: If signatures differ, fix the call in `_run_translate_transcript_en_inner`**

  If `DeepLClient.translate_batch` requires `source_lang="DE"` (uppercase code) and `target_lang="EN-US"`, while `LLMTranslationClient` requires full names like `"German"` / `"English"`, add a thin normalisation based on the provider protocol:

  ```python
  from src.services.deepl_client import DeepLClient

  if isinstance(client, DeepLClient):
      translated = client.translate_batch(
          texts, source_lang=source_lang.upper(), target_lang="EN-US",
      )
  else:
      translated = client.translate_batch(
          texts, source_lang=source_lang_name, target_lang="English",
      )
  ```

  If the signatures already match (both accept the same format), no change needed — leave the single `client.translate_batch(...)` call from Task 3.

- [ ] **Step 4: If a change was needed, commit**

  ```bash
  git add backend/src/features/ai_assistant/tasks/ingestion.py
  git commit -m "fix(aia): normalise translate_batch call for DeepL vs LLM client"
  ```

---

### Task 7: Manual end-to-end smoke test

- [ ] **Step 1: Start the dev stack**

  ```bash
  docker compose up -d
  ```

- [ ] **Step 2: Verify `transcript_translate` appears in the admin KI panel**

  Open the admin KI panel (`/[locale]/admin`) → Providers → Feature Routing section. Confirm a "Transkript-Übersetzung" row is present. Assign a translation-capable provider to it.

- [ ] **Step 3: Test the manual regenerate button in AIA workspace**

  Upload a short DE audio file in the AIA workspace. After transcription completes, click "EN transcript regenerieren". Verify:
  - If `transcript_translate` is configured: EN VTT appears.
  - If `transcript_translate` is not configured: the button returns a 503 error visible in the UI.

- [ ] **Step 4: Commit any fixes found during smoke test**

  ```bash
  git add <affected files>
  git commit -m "fix(aia): <description of fix>"
  ```
