# Translation Provider Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admin configure translation providers (like TTS) and users pick a provider in both the document-translate and screencast-translate tools at runtime.

**Architecture:** A new `get_translation_providers()` + `get_translate_client_for_provider()` pair in `dependencies.py` mirrors the existing TTS helpers. The admin panel's `FeatureRoutingCard` extends its TTS-style stacked row branch to also cover `doc_translate`; `screencast_translate` is removed from the admin view (both tools share one config). Both tool UIs call `GET /translate/config` (updated to return dynamic providers) and send `provider_id: int` instead of the legacy `translation_provider` string.

**Tech Stack:** FastAPI (Python), Celery, React/Next.js, TypeScript, next-intl

---

## File Map

**Create:**
- `backend/tests/test_translate_provider.py`

**Modify:**
- `backend/src/dependencies.py` — add `get_translation_providers()`, `get_translate_client_for_provider()`
- `backend/src/routes/translate.py` — update `GET /translate/config`, `POST /translate`
- `backend/src/tasks/general_tasks.py` — update `run_translate` signature + provider resolution
- `backend/src/routes/screencast/translate.py` — add `provider_id` Form field
- `backend/src/tasks/screencast_tasks/_queue.py` — pass `provider_id` to translate task
- `backend/src/tasks/screencast_tasks/_translate.py` — accept + use `provider_id`
- `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx` — extend TTS branch, remove screencast_translate
- `frontend/src/app/[locale]/tools/translate/page.tsx` — use numeric provider_id
- `frontend/src/app/[locale]/tools/screencast/_steps/UploadStep.tsx` — add provider dropdown
- `frontend/src/app/[locale]/tools/screencast/_hooks/useScreencastTranslateFlow.ts` — pass provider_id
- `frontend/src/app/[locale]/tools/screencast/page.tsx` — fetch + manage translation providers
- `frontend/messages/en.json` — add screencast upload provider label
- `frontend/messages/de.json` — add screencast upload provider label

---

## Task 1: Backend — Add translation provider helpers to dependencies.py

**Files:**
- Modify: `backend/src/dependencies.py`
- Test: `backend/tests/test_translate_provider.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_translate_provider.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def _make_provider(id, name, protocol="openai_compat", api_key=None, base_url="http://example.com"):
    return {"id": id, "name": name, "protocol": protocol, "api_key": api_key,
            "base_url": base_url, "enabled": True, "voices": [], "capabilities": []}


def test_get_translation_providers_merges_translation_and_chat(monkeypatch):
    from src.dependencies import get_translation_providers
    p1 = _make_provider(1, "DeepL", protocol="deepl")
    p2 = _make_provider(2, "KISSKI", protocol="openai_compat")
    p3 = _make_provider(2, "KISSKI", protocol="openai_compat")  # duplicate, different cap

    def fake_list(cap):
        if cap == "translation":
            return [p1]
        if cap == "chat":
            return [p2, p3]
        return []

    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability", fake_list)
    result = get_translation_providers()
    ids = [p["id"] for p in result]
    assert ids == [1, 2], "should deduplicate and preserve order"


def test_get_translate_client_for_provider_deepl(monkeypatch):
    from src.dependencies import get_translate_client_for_provider
    from src.services.glossary import GlossaryService

    provider = _make_provider(5, "DeepL", protocol="deepl", api_key="secret:fx",
                              base_url="https://api-free.deepl.com")
    route = {"provider_models": {"5": ""}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(5, glossary_entries={"Hello": "Hallo"})
    from src.services.deepl_client import DeepLClient
    assert isinstance(client, DeepLClient)
    assert isinstance(glossary, GlossaryService)


def test_get_translate_client_for_provider_llm(monkeypatch):
    from src.dependencies import get_translate_client_for_provider

    provider = _make_provider(7, "KISSKI", protocol="openai_compat", api_key="key",
                              base_url="https://llm.example.com/v1")
    route = {"provider_models": {"7": "mistral-small"}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(7, glossary_entries=None)
    from src.services.llm_translation_client import LLMTranslationClient
    assert isinstance(client, LLMTranslationClient)


def test_get_translate_client_returns_none_for_missing_provider(monkeypatch):
    from src.dependencies import get_translate_client_for_provider

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: None)

    client, glossary = get_translate_client_for_provider(99)
    assert client is None


def test_get_translate_client_fallback_when_provider_id_none(monkeypatch):
    from src.dependencies import get_translation_providers, get_translate_client_for_provider

    provider = _make_provider(3, "DeepL", protocol="deepl", api_key="key")
    route = {"provider_models": {}, "model_name": None}

    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability",
                        lambda cap: [provider] if cap == "translation" else [])
    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: route)

    client, glossary = get_translate_client_for_provider(None)
    from src.services.deepl_client import DeepLClient
    assert isinstance(client, DeepLClient)
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd backend && python -m pytest tests/test_translate_provider.py -v 2>&1 | tail -20
```

Expected: `ImportError` or `AttributeError` — functions don't exist yet.

- [ ] **Step 3: Add the two helper functions to dependencies.py**

Open `backend/src/dependencies.py`. After the TTS resolvers section (after `_voice_language_for`, around line 210), add:

```python
# ─── Translation resolvers ──────────────────────────────────────────────────

def get_translation_providers() -> list[dict]:
    """All enabled providers that can serve translation (translation or chat capability).

    DeepL providers have 'translation' capability; OpenAI-compat LLM providers
    have 'chat' and can translate via prompt. Returns a deduplicated list.
    """
    from src import database as db
    seen_ids: set[int] = set()
    result: list[dict] = []
    for cap in ("translation", "chat"):
        for p in db.list_providers_with_capability(cap):
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                result.append(p)
    return result


def get_translate_client_for_provider(provider_id: Optional[int], *, glossary_entries: dict | None = None):
    """Return (translation_client, GlossaryService) for use with TranslationService.

    When provider_id is None, falls back to the first available translation provider.
    Returns (None, GlossaryService()) if no provider can be found.

    Protocol dispatch:
      deepl         -> DeepLClient + GlossaryService with entries
      openai_compat -> LLMTranslationClient (glossary passed in constructor)
    """
    from src import database as db
    from src.services.glossary import GlossaryService

    if provider_id is None:
        providers = get_translation_providers()
        if not providers:
            return None, GlossaryService()
        provider_id = providers[0]["id"]

    provider = db.get_provider(provider_id)
    if not provider or not provider.get("enabled"):
        return None, GlossaryService()

    route = db.get_route("doc_translate")
    provider_models = (route.get("provider_models") if route else None) or {}
    model = provider_models.get(str(provider_id)) or (route.get("model_name") if route else None) or ""

    glossary = GlossaryService()
    if provider.get("protocol") == "deepl":
        from src.services.deepl_client import DeepLClient
        if glossary_entries:
            glossary.set_entries(glossary_entries)
        return DeepLClient(provider.get("api_key") or ""), glossary
    else:
        from src.services.llm_translation_client import LLMTranslationClient
        base_url = provider["base_url"].rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        client = LLMTranslationClient(
            api_key=provider.get("api_key") or "not-needed",
            base_url=base_url,
            model=model,
            provider=provider["name"],
            glossary=glossary_entries or None,
        )
        return client, glossary
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
cd backend && python -m pytest tests/test_translate_provider.py -v 2>&1 | tail -20
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/dependencies.py backend/tests/test_translate_provider.py
git commit -m "feat(translate): add get_translation_providers and get_translate_client_for_provider helpers"
```

---

## Task 2: Backend — Dynamic providers in GET /translate/config

**Files:**
- Modify: `backend/src/routes/translate.py`

- [ ] **Step 1: Replace the hardcoded providers list in `get_translate_config`**

In `backend/src/routes/translate.py`, replace the entire `get_translate_config` function (lines 33-51) with:

```python
@router.get("/translate/config")
async def get_translate_config(
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    from src.dependencies import get_translation_providers
    raw_providers = get_translation_providers()
    providers = [{"id": p["id"], "label": p["name"]} for p in raw_providers]

    languages = [{"id": lang, "label": t(f"lang.{lang}", locale)} for lang in TRANSLATE_LANGUAGES]

    return {
        "providers": providers,
        "languages": languages,
        "default_source": DEFAULT_TRANSLATE_SOURCE,
        "default_target": DEFAULT_TRANSLATE_TARGET,
    }
```

Note: `default_provider` field is removed (frontend will use `providers[0]` as default).

- [ ] **Step 2: Verify the route still imports correctly**

```bash
cd backend && python -c "from src.routes.translate import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/routes/translate.py
git commit -m "feat(translate): GET /translate/config returns dynamic providers from DB"
```

---

## Task 3: Backend — POST /translate accepts provider_id

**Files:**
- Modify: `backend/src/routes/translate.py`

- [ ] **Step 1: Update the POST /translate route signature and task call**

In `backend/src/routes/translate.py`, replace the `translate` function signature (the `translation_provider` parameter and the `run_translate.delay` call at lines 99 and 150-158):

Change:
```python
    translation_provider: str = Form(""),
```
To:
```python
    provider_id: int | None = Form(None),
```

Change the `run_translate.delay(...)` call (currently lines 150-158):
```python
    run_translate.delay(
        job_uuid,
        input_path,
        file.filename,
        glossary,
        effective_source,
        effective_target,
        translation_provider,
    )
```
To:
```python
    run_translate.delay(
        job_uuid,
        input_path,
        file.filename,
        glossary,
        effective_source,
        effective_target,
        provider_id,
    )
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from src.routes.translate import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/routes/translate.py
git commit -m "feat(translate): POST /translate accepts provider_id instead of translation_provider string"
```

---

## Task 4: Backend — run_translate task uses feature-router-style provider resolution

**Files:**
- Modify: `backend/src/tasks/general_tasks.py`
- Test: `backend/tests/test_translate_provider.py`

- [ ] **Step 1: Add a test for the new task behaviour**

Append to `backend/tests/test_translate_provider.py`:

```python
def test_run_translate_uses_provider_id(monkeypatch, tmp_path):
    """run_translate resolves provider_id into the right translation client."""
    from src.tasks import general_tasks

    provider = _make_provider(5, "DeepL", protocol="deepl", api_key="key",
                              base_url="https://api-free.deepl.com")
    glossary_svc = MagicMock()
    fake_client = MagicMock()
    fake_client.translate_text.return_value = "translated"
    fake_client.translate_batch.return_value = ["translated"]

    monkeypatch.setattr("src.dependencies.db.get_provider", lambda pid: provider)
    monkeypatch.setattr("src.dependencies.db.get_route", lambda f: {"provider_models": {}, "model_name": None})
    monkeypatch.setattr("src.dependencies.db.list_providers_with_capability", lambda c: [provider])

    captured = {}

    def fake_get_translate_client(pid, *, glossary_entries=None):
        captured["provider_id"] = pid
        return fake_client, glossary_svc

    monkeypatch.setattr("src.tasks.general_tasks.get_translate_client_for_provider",
                        fake_get_translate_client)

    # Minimal stubs so the task body can run without DB/Celery
    monkeypatch.setattr("src.tasks.general_tasks.db.update_job_status", lambda *a, **kw: None)
    monkeypatch.setattr("src.tasks.general_tasks.db.update_job_expiry", lambda *a, **kw: None)
    monkeypatch.setattr("src.tasks.general_tasks._resolve_user_id", lambda uuid: 1)

    txt = tmp_path / "input.txt"
    txt.write_text("Hello world")

    from src.services.translation import TranslationService
    from src.services.glossary import GlossaryService
    monkeypatch.setattr("src.tasks.general_tasks.TranslationService",
                        lambda deepl_client, glossary: MagicMock(
                            translate_text=lambda t, s, tgt: "translated",
                            translate_filename=lambda f, s, tgt: "translated.txt",
                        ))

    result_path = tmp_path / "result.txt"
    monkeypatch.setattr("src.tasks.general_tasks.get_file", lambda p: b"Hello world")
    monkeypatch.setattr("src.tasks.general_tasks.save_result_file", lambda *a, **kw: str(result_path))
    monkeypatch.setattr("src.tasks.general_tasks.save_result_and_evict", lambda *a, **kw: None)
    monkeypatch.setattr("src.tasks.general_tasks.delete_file", lambda p: None)

    general_tasks.run_translate(
        None,  # self (Celery bind)
        "job-uuid-123",
        str(txt),
        "test.txt",
        "",   # glossary_json
        "DE",
        "EN",
        5,    # provider_id
    )

    assert captured["provider_id"] == 5
```

- [ ] **Step 2: Run new test — verify it FAILS**

```bash
cd backend && python -m pytest tests/test_translate_provider.py::test_run_translate_uses_provider_id -v 2>&1 | tail -20
```

Expected: FAIL — `get_translate_client_for_provider` not imported in `general_tasks`.

- [ ] **Step 3: Rewrite the translation section of run_translate**

In `backend/src/tasks/general_tasks.py`, replace the entire `run_translate` task function signature and provider-resolution block.

Old signature (line 70):
```python
def run_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    source_lang: str,
    target_lang: str,
    translation_provider: str = "",
):
```

New signature:
```python
def run_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    source_lang: str,
    target_lang: str,
    provider_id: int | None = None,
):
```

Old provider-resolution block (lines 87-127 — everything from `from src.config import Settings` down to `service = TranslationService(...)`):

```python
        from src.config import Settings
        from src.services.glossary import GlossaryService
        from src.services.translation import TranslationService

        settings = Settings()
        effective_provider = translation_provider or "deepl"

        # Parse glossary entries from JSON
        glossary_entries: dict = {}
        if glossary_json:
            try:
                entries = json.loads(glossary_json)
                if isinstance(entries, dict):
                    glossary_entries = entries
            except (json.JSONDecodeError, TypeError):
                pass

        if effective_provider == "llm":
            from src.services.llm_translation_client import LLMTranslationClient
            from src.dependencies import _resolve_translation_llm_provider
            _api_key, _base_url, _model, _provider = _resolve_translation_llm_provider()
            translation_client = LLMTranslationClient(
                api_key=_api_key,
                base_url=_base_url,
                model=_model,
                provider=_provider,
                glossary=glossary_entries or None,
            )
            glossary = GlossaryService()
        else:
            from src.services.deepl_client import DeepLClient
            from src.dependencies import resolve_deepl_api_key
            api_key = resolve_deepl_api_key()
            if not api_key:
                raise RuntimeError("DeepL API key not configured")
            translation_client = DeepLClient(api_key)
            glossary = GlossaryService()
            if glossary_entries:
                glossary.set_entries(glossary_entries)

        service = TranslationService(deepl_client=translation_client, glossary=glossary)
```

Replace with:

```python
        from src.services.glossary import GlossaryService
        from src.services.translation import TranslationService
        from src.dependencies import get_translate_client_for_provider

        glossary_entries: dict = {}
        if glossary_json:
            try:
                entries = json.loads(glossary_json)
                if isinstance(entries, dict):
                    glossary_entries = entries
            except (json.JSONDecodeError, TypeError):
                pass

        translation_client, glossary = get_translate_client_for_provider(
            provider_id, glossary_entries=glossary_entries or None
        )
        if translation_client is None:
            raise RuntimeError("No translation provider configured")

        service = TranslationService(deepl_client=translation_client, glossary=glossary)
```

Also remove the now-unused `from src.config import Settings` and `settings = Settings()` lines in this task.

- [ ] **Step 4: Run all translate-provider tests**

```bash
cd backend && python -m pytest tests/test_translate_provider.py -v 2>&1 | tail -30
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tasks/general_tasks.py backend/tests/test_translate_provider.py
git commit -m "feat(translate): run_translate resolves provider via get_translate_client_for_provider"
```

---

## Task 5: Frontend — translate/page.tsx uses numeric provider_id

**Files:**
- Modify: `frontend/src/app/[locale]/tools/translate/page.tsx`

- [ ] **Step 1: Update state and form submission**

In `frontend/src/app/[locale]/tools/translate/page.tsx`:

Replace:
```tsx
  const [providers, setProviders] = useState<{ id: string; label: string }[]>([]);
  const [translationProvider, setTranslationProvider] = useState<string>("");
```
With:
```tsx
  const [providers, setProviders] = useState<{ id: number; label: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
```

Replace the `useEffect` config fetch:
```tsx
  useEffect(() => {
    api
      .fetch("/translate/config")
      .then((r) => r.json())
      .then((data) => {
        setProviders(data.providers ?? []);
        setLanguages(data.languages ?? []);
        setTranslationProvider(data.default_provider ?? "");
        setSourceLang(data.default_source ?? "DE");
        setTargetLang(data.default_target ?? "");
      })
      .catch(() => {});
  }, []);
```
With:
```tsx
  useEffect(() => {
    api
      .fetch("/translate/config")
      .then((r) => r.json())
      .then((data) => {
        const provs: { id: number; label: string }[] = data.providers ?? [];
        setProviders(provs);
        setLanguages(data.languages ?? []);
        if (provs.length > 0) setTranslationProviderId(provs[0].id);
        setSourceLang(data.default_source ?? "DE");
        setTargetLang(data.default_target ?? "");
      })
      .catch(() => {});
  }, []);
```

Replace in `handleSubmit`:
```tsx
      if (translationProvider) formData.append("translation_provider", translationProvider);
```
With:
```tsx
      if (translationProviderId != null) formData.append("provider_id", String(translationProviderId));
```

Replace the provider Select in the JSX:
```tsx
          {providers.length > 0 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                {t("engine")}
              </label>
              <Select
                value={translationProvider}
                onChange={setTranslationProvider}
                disabled={processing}
                options={providers.map((p) => ({ value: p.id, label: p.label }))}
              />
            </div>
          )}
```
With:
```tsx
          {providers.length > 1 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-foreground-soft mb-1">
                {t("engine")}
              </label>
              <Select
                value={translationProviderId != null ? String(translationProviderId) : ""}
                onChange={(v) => setTranslationProviderId(v ? Number(v) : null)}
                disabled={processing}
                options={providers.map((p) => ({ value: String(p.id), label: p.label }))}
              />
            </div>
          )}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "translate/page"
```

Expected: no errors for this file.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/[locale]/tools/translate/page.tsx"
git commit -m "feat(translate): translate tool uses numeric provider_id instead of string"
```

---

## Task 6: Frontend Admin — extend TTS branch in FeatureRoutingCard

**Files:**
- Modify: `frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx`

- [ ] **Step 1: Extend the TTS condition and remove screencast_translate from FEATURE_ORDER**

In `FeatureRoutingCard.tsx`:

Replace line 201:
```tsx
  if (isUserChoice && feature === "tts") {
```
With:
```tsx
  if (isUserChoice && (feature === "tts" || feature === "doc_translate")) {
```

Replace `FEATURE_ORDER` (lines 50-61):
```tsx
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
  "screencast_translate",
];
```
With:
```tsx
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
];
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "FeatureRoutingCard"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/[locale]/admin/_components/providers/FeatureRoutingCard.tsx"
git commit -m "feat(admin): doc_translate uses TTS-style stacked provider rows, remove screencast_translate row"
```

---

## Task 7: Backend — POST /screencast/translate accepts provider_id

**Files:**
- Modify: `backend/src/routes/screencast/translate.py`

- [ ] **Step 1: Add provider_id Form field and store in queue_params.json**

In `backend/src/routes/screencast/translate.py`, update the `screencast_translate` function.

Add `provider_id: int | None = Form(None)` parameter after `target_lang`:

```python
@router.post("/screencast/translate")
async def screencast_translate(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
    source_lang: str = Form("DE"),
    target_lang: str = Form("EN-US"),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
```

Update the `save_job_file` call to include `provider_id` in `queue_params.json`:

```python
    save_job_file(user_id, job_uuid, "queue_params.json", json.dumps({
        "dispatch_as": "translate",
        "input_path": input_path,
        "filename": filename,
        "glossary_json": glossary_json,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "provider_id": provider_id,
    }).encode())
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from src.routes.screencast.translate import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/routes/screencast/translate.py
git commit -m "feat(screencast): POST /screencast/translate accepts and stores provider_id"
```

---

## Task 8: Backend — _queue.py passes provider_id to run_screencast_translate

**Files:**
- Modify: `backend/src/tasks/screencast_tasks/_queue.py`

- [ ] **Step 1: Pass provider_id from queue_params to the translate task**

In `backend/src/tasks/screencast_tasks/_queue.py`, update the `dispatch_as == "translate"` branch:

```python
        if dispatch_as == "translate":
            task = run_screencast_translate.apply_async(args=[
                job_uuid, params["input_path"], params["filename"],
                params["glossary_json"],
                params["source_lang"], params["target_lang"],
                params.get("provider_id"),
            ])
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from src.tasks.screencast_tasks._queue import dispatch_next_screencast_job_for_user; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/tasks/screencast_tasks/_queue.py
git commit -m "feat(screencast): _queue passes provider_id to run_screencast_translate"
```

---

## Task 9: Backend — run_screencast_translate uses provider_id

**Files:**
- Modify: `backend/src/tasks/screencast_tasks/_translate.py`

- [ ] **Step 1: Update task signature and replace translate_pptx_content with direct provider resolution**

Replace the entire `run_screencast_translate` function in `backend/src/tasks/screencast_tasks/_translate.py`:

```python
@celery_app.task(bind=True, name="screencast.translate", queue="screencast")
def run_screencast_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
    provider_id: int | None = None,
):
    """Translate PPTX DE→EN, extract slide texts, save artifacts, set awaiting_user."""
    try:
        db.update_job_status(job_uuid, "running", progress={"step": "translate"})
        job_row = db.get_job(job_uuid)
        if not job_row:
            raise RuntimeError(f"Job {job_uuid} not found")
        user_id = job_row["user_id"]

        pptx_bytes = get_file(input_path)

        # Save original PPTX immediately
        save_job_file(user_id, job_uuid, "original.pptx", pptx_bytes)

        # Resolve translation provider
        import json as _json
        from src.dependencies import get_translate_client_for_provider
        from src.services.translation import TranslationService
        from src.translators.pptx import translate_pptx

        glossary_entries: dict = {}
        if glossary_json:
            try:
                entries = _json.loads(glossary_json)
                if isinstance(entries, dict):
                    glossary_entries = entries
            except (_json.JSONDecodeError, TypeError):
                pass

        translation_client, glossary = get_translate_client_for_provider(
            provider_id, glossary_entries=glossary_entries or None
        )
        if translation_client is None:
            locale = job_row.get("creator_locale") or "de"
            raise RuntimeError(t("translate.noProviderConfigured", locale))

        service = TranslationService(deepl_client=translation_client, glossary=glossary)
        translated_bytes = translate_pptx(pptx_bytes, source_lang, target_lang, service)

        (
            IMAGE_TMP_DIR,
            _pptx_to_images, _generate_all_tts, _convert_slides_to_images_async,
            _create_slide_video, _concatenate_videos, _apply_faststart,
            _extract_text_per_slide,
            _create_outro_image, _get_image_dimensions,
        ) = _get_screencast_helpers()

        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
        slide_texts = _extract_text_per_slide(translated_bytes)
        if not slide_texts:
            locale = job_row.get("creator_locale") or "de"
            raise ValueError(t("screencast.noSlides", locale))

        # Save translated PPTX + scripts to job folder immediately
        save_job_file(user_id, job_uuid, "translated.pptx", translated_bytes)
        save_job_file(user_id, job_uuid, "scripts.txt", json.dumps(slide_texts, ensure_ascii=False, indent=2).encode("utf-8"))

        db.update_job_status(job_uuid, "running", progress={"step": "images"})
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pptx_path = tmp / "translated.pptx"
            pptx_path.write_bytes(translated_bytes)
            img_dir = tmp / "images"
            img_dir.mkdir()
            slide_image_paths = asyncio.run(_convert_slides_to_images_async(pptx_path, img_dir))
            import base64
            slide_images_b64 = [base64.b64encode(p.read_bytes()).decode() for p in slide_image_paths]

        result = {
            "slide_count": len(slide_texts),
            "slide_texts": slide_texts,
            "slide_images": slide_images_b64,
        }

        result_path = save_result_json(user_id, job_uuid, result)
        save_result_and_evict(user_id, job_uuid, result_path, f"{Path(filename).stem}_translate.json")

        from src.services.screencast.naming import translate_stem
        translated = translate_stem(filename, source_lang, target_lang)
        save_result_meta(user_id, job_uuid, {"translated_stem": translated})

        db.update_job_status(job_uuid, "awaiting_user")
        db.update_job_expiry(job_uuid, 168)
        _maybe_dispatch_next(job_uuid)

        delete_file(input_path)

        logger.info("Screencast translate task {} completed: {} slides", job_uuid, len(slide_texts))

    except Exception as e:
        logger.error("Screencast translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
```

Note: the old `from src.routes.translate import translate_pptx_content` import is gone. The function now calls `translate_pptx` directly with a provider-resolved `service`.

Also add a missing i18n key used above — add `"translate.noProviderConfigured"` to the i18n files (Task 10 covers this).

For now, use a hardcoded fallback string: replace `t("translate.noProviderConfigured", locale)` with `"No translation provider configured"` if the key doesn't exist yet.

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from src.tasks.screencast_tasks._translate import run_screencast_translate; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/tasks/screencast_tasks/_translate.py
git commit -m "feat(screencast): run_screencast_translate resolves translation provider via get_translate_client_for_provider"
```

---

## Task 10: Frontend i18n — add screencast provider label

**Files:**
- Modify: `frontend/messages/en.json`
- Modify: `frontend/messages/de.json`

- [ ] **Step 1: Add key to en.json**

In `frontend/messages/en.json`, find the `tools.screencast.upload` object (it contains keys like `sourceLang`, `targetLang`, `skipTranslation`). Add:

```json
"translationProvider": "Translation provider"
```

- [ ] **Step 2: Add key to de.json**

In `frontend/messages/de.json`, in the same path, add:

```json
"translationProvider": "Übersetzungsanbieter"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/messages/en.json frontend/messages/de.json
git commit -m "i18n: add screencast upload translationProvider label"
```

---

## Task 11: Frontend — screencast UploadStep gets provider dropdown

**Files:**
- Modify: `frontend/src/app/[locale]/tools/screencast/_steps/UploadStep.tsx`

- [ ] **Step 1: Add provider props and dropdown to UploadStep**

In `frontend/src/app/[locale]/tools/screencast/_steps/UploadStep.tsx`:

Add to the `UploadStepProps` interface (after `onGlossaryIdsChange`):
```tsx
  translationProviders: { id: number; name: string }[];
  translationProviderId: number | null;
  onTranslationProviderChange: (id: number | null) => void;
```

Add to the destructured props at the top of the component:
```tsx
    translationProviders,
    translationProviderId,
    onTranslationProviderChange,
```

Add a provider select below the `<GlossarySelector>` block (still inside the `{sourceLang !== targetLang && (...)}` block), before the closing `</>`:

```tsx
          {translationProviders.length > 1 && (
            <div className="mb-4">
              <label className="block text-xs font-medium text-muted mb-1">
                {t("upload.translationProvider")}
              </label>
              <Select
                value={translationProviderId != null ? String(translationProviderId) : ""}
                onChange={(v) => onTranslationProviderChange(v ? Number(v) : null)}
                options={translationProviders.map((p) => ({ value: String(p.id), label: p.name }))}
              />
            </div>
          )}
```

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "UploadStep"
```

Expected: errors about missing props (they will be fixed in Task 13 when `page.tsx` passes them).

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/[locale]/tools/screencast/_steps/UploadStep.tsx"
git commit -m "feat(screencast): UploadStep accepts translation provider dropdown props"
```

---

## Task 12: Frontend — useScreencastTranslateFlow passes provider_id

**Files:**
- Modify: `frontend/src/app/[locale]/tools/screencast/_hooks/useScreencastTranslateFlow.ts`

- [ ] **Step 1: Add translationProviderId to opts and POST body**

In `useScreencastTranslateFlow.ts`:

Add to the `UseScreencastTranslateFlowOptions` interface (after `glossaryIds`):
```tsx
  translationProviderId: number | null;
```

Add to the destructured `opts` in the function body (after `glossaryIds`):
```tsx
    translationProviderId,
```

Add `translationProviderId` to the dependency array of `handleUploadNext`.

In `handleUploadNext`, in the **different-language path** (the `try` block that calls `POST /api/screencast/translate`), add `provider_id` to the form data:

```tsx
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
      formData.append("source_lang", sourceLang);
      formData.append("target_lang", targetLang);
      if (translationProviderId != null) formData.append("provider_id", String(translationProviderId));
```

Also add `translationProviderId` to the `useCallback` dependency array of `handleUploadNext`.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "useScreencastTranslateFlow"
```

Expected: errors about missing `translationProviderId` at call sites (fixed in next task).

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/[locale]/tools/screencast/_hooks/useScreencastTranslateFlow.ts"
git commit -m "feat(screencast): translate flow passes provider_id to POST /screencast/translate"
```

---

## Task 13: Frontend — screencast/page.tsx manages translation providers

**Files:**
- Modify: `frontend/src/app/[locale]/tools/screencast/page.tsx`

- [ ] **Step 1: Add translation provider state and fetch**

In `frontend/src/app/[locale]/tools/screencast/page.tsx`:

After the existing `const [speed, setSpeed] = useState(1.0);` line, add:

```tsx
  const [translationProviders, setTranslationProviders] = useState<{ id: number; name: string }[]>([]);
  const [translationProviderId, setTranslationProviderId] = useState<number | null>(null);
```

After the existing language/voices `useEffect` hooks, add a new effect to fetch translation providers:

```tsx
  useEffect(() => {
    fetch("/api/translate/config", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        const provs: { id: number; name: string }[] = (data.providers ?? []).map(
          (p: { id: number; label: string }) => ({ id: p.id, name: p.label })
        );
        setTranslationProviders(provs);
        if (provs.length > 0) setTranslationProviderId(provs[0].id);
      })
      .catch(() => {});
  }, []);
```

- [ ] **Step 2: Pass translationProviderId to useScreencastTranslateFlow**

In the `useScreencastTranslateFlow({...})` call, add:

```tsx
    translationProviderId,
```

- [ ] **Step 3: Pass props to UploadStep**

In the `<UploadStep ... />` JSX (around line 432), add the new props:

```tsx
            translationProviders={translationProviders}
            translationProviderId={translationProviderId}
            onTranslationProviderChange={setTranslationProviderId}
```

- [ ] **Step 4: TypeScript check — must be clean**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "screencast|UploadStep|TranslateFlow" | head -20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/app/[locale]/tools/screencast/page.tsx"
git commit -m "feat(screencast): page fetches translation providers and passes to upload step"
```

---

## Final Validation

- [ ] **Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Run frontend type check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Manual smoke test — Admin panel**

1. Open admin → Providers tab
2. Verify "Übersetzung" row shows stacked provider rows (like TTS) — label + model input + test button per provider
3. Verify "Screencast-Übersetzung" row is gone
4. Set a model name for one provider, test button shows ✓

- [ ] **Manual smoke test — Document translate tool**

1. Open `/tools/translate`
2. If >1 translation providers configured: provider dropdown visible
3. Select a provider, upload a file, submit — job queued and completes

- [ ] **Manual smoke test — Screencast translate upload step**

1. Open `/tools/screencast-translate` (screencast tool)
2. Upload a PPTX with DE→EN translation
3. If >1 translation providers: dropdown visible below glossary selector
4. Select provider, click Next — translation job queued with correct provider_id in queue_params.json
