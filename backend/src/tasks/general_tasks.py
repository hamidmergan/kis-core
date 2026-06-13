"""Celery tasks: translate, transcribe, image_generate, image_edit, image_analyze, summary."""

import base64
import json
import tempfile
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.i18n import t
from src.storage import delete_file, get_file, open_input_file, save_result_file, save_result_and_evict
from src.utils.heartbeat import job_heartbeat
from src.dependencies import get_translate_client_for_provider
from src.services.translation import TranslationService


# -- Helpers ------------------------------------------------------------------

def _resolve_user_id(job_uuid: str) -> int:
    """Look up the owning user_id for a job (raises if the row vanished)."""
    row = db.get_job(job_uuid)
    if not row:
        raise RuntimeError(f"Job {job_uuid} not found")
    return row["user_id"]


def _get_llm_client(provider_id: int | None = None):
    from src.services.openai_compat_llm import OpenAICompatLLMClient
    if provider_id is not None:
        from src.services import feature_provider_choices, feature_router
        binding = feature_provider_choices.resolve_binding("chat", provider_id)
        return feature_router.make_llm_client(binding)
    from src.dependencies import _resolve_llm_provider
    api_key, base_url, model, provider = _resolve_llm_provider()
    if not api_key:
        raise RuntimeError("Kein LLM-Provider konfiguriert")
    return OpenAICompatLLMClient(api_key=api_key, base_url=base_url, model=model, whisper_model=model, provider=provider)


def _image_http_client(
    feature: str,
    *,
    provider_id: int | None = None,
    extra_headers: dict | None = None,
    timeout: float = 120.0,
):
    """Build (base_url, model, httpx.Client) for an image-feature route.

    Resolves the provider for ``feature`` (``image_gen``, ``image_edit``,
    ``vision``). ``provider_id`` is the end-user's pick (capability-based,
    same as the TTS/STT pickers); when omitted the admin default route is used.
    Propagates ``FeatureNotConfigured`` unchanged so the task's outer handler
    can translate it into a localized job error_message.
    """
    import httpx
    from src.services import feature_router

    if provider_id is not None:
        from src.services import feature_provider_choices
        binding = feature_provider_choices.resolve_binding(feature, provider_id)
    else:
        binding = feature_router.resolve(feature)  # raises FeatureNotConfigured

    provider = binding.provider
    base = provider["base_url"].rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"

    headers: dict[str, str] = {}
    api_key = provider.get("api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)

    return base, (binding.model or ""), httpx.Client(headers=headers, timeout=timeout)


from src.tasks._errors import handle_task_exception as _handle_task_exception


# -- Translation --------------------------------------------------------------

@celery_app.task(bind=True, name="general.translate", queue="general")
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
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.services.glossary import GlossaryService

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
        translated_filename = service.translate_filename(filename, source_lang, target_lang)

        with job_heartbeat(job_uuid):
            if ext == ".txt":
                text = content.decode("utf-8")
                translated_text = service.translate_text(text, source_lang, target_lang)
                result_bytes = translated_text.encode("utf-8")
            elif ext == ".md":
                from src.translators.markdown import translate_markdown_preserve_code_blocks
                text = content.decode("utf-8")
                translated_text = translate_markdown_preserve_code_blocks(text, source_lang, target_lang, service)
                result_bytes = translated_text.encode("utf-8")
            elif ext == ".tex":
                from src.translators.latex import translate_latex_preserve_structure
                text = content.decode("utf-8")
                translated_text = translate_latex_preserve_structure(text, source_lang, target_lang, service)
                result_bytes = translated_text.encode("utf-8")
            elif ext == ".docx":
                from src.translators.docx import translate_docx
                result_bytes = translate_docx(content, source_lang, target_lang, service)
            elif ext == ".pptx":
                from src.translators.pptx import translate_pptx
                result_bytes = translate_pptx(content, source_lang, target_lang, service)
            else:
                raise ValueError(f"Unsupported format: {ext}")

        result_path = save_result_file(user_id, job_uuid, ext, result_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, translated_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Translate task {} completed: {}", job_uuid, translated_filename)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Translate")
        raise


# -- Transcription ------------------------------------------------------------

_FORMAT_EXT = {"text": ".txt", "srt": ".srt", "vtt": ".vtt"}


@celery_app.task(bind=True, name="general.transcribe", queue="general")
def run_transcribe(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    task: str,
    response_format: str,
    provider_id: int | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)

        from src.dependencies import resolve_whisper_client
        client = resolve_whisper_client(provider_id)
        ext_suffix = Path(filename).suffix.lower()

        with job_heartbeat(job_uuid), open_input_file(input_path, suffix=ext_suffix) as local_path:
            if task == "translate":
                result_text = client.transcribe_and_translate_chunked(
                    local_path, response_format=response_format, cache_key=job_uuid)
            else:
                result_text = client.transcribe_chunked(
                    local_path, response_format=response_format, cache_key=job_uuid)

        out_ext = _FORMAT_EXT[response_format]
        if task == "translate":
            from src.services.translation import translate_output_filename
            output_name = translate_output_filename(filename, output_ext=out_ext)
        else:
            output_name = f"{Path(filename).stem}{out_ext}"

        result_path = save_result_file(user_id, job_uuid, out_ext, result_text.encode("utf-8"))
        save_result_and_evict(user_id, job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Transcribe task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        # Rate-limit (429): keep the job alive and requeue with backoff instead of failing.
        # Chunks already transcribed are cached per job_uuid in Redis, so the retry resumes
        # rather than restarting from zero. Mirrors the AIA media-ingestion retry policy.
        msg = str(e).lower()
        if ("429" in msg or "rate limit" in msg) and self.request.retries < 5:
            countdown = min(30 * (2 ** self.request.retries), 120)  # 30s, 1m, 2m, 2m, 2m
            logger.warning(
                "Transcribe job {} hit rate limit (attempt {}/{}), retrying in {}s",
                job_uuid, self.request.retries + 1, 5, countdown,
            )
            raise self.retry(exc=e, countdown=countdown, max_retries=5)
        _handle_task_exception(job_uuid, e, task_label="Transcribe")
        raise


# -- Image: generate ----------------------------------------------------------

@celery_app.task(bind=True, name="general.image_generate", queue="general")
def run_image_generate(
    self,
    job_uuid: str,
    prompt: str,
    size: str,
    provider_id: int | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)

        base_url, model, client = _image_http_client("image_gen", provider_id=provider_id, timeout=120.0)
        if not model:
            from src.services.feature_router import FeatureNotConfigured
            raise FeatureNotConfigured("image_gen route has no model_name")
        body: dict = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }

        with job_heartbeat(job_uuid), client:
            response = client.post(f"{base_url}/images/generations", json=body)

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildgenerierung: {response.text[:200]}")

        data = response.json()
        images = data.get("data", [])
        if not images:
            raise RuntimeError("Keine Bilder generiert")

        label = prompt[:40].strip().replace(" ", "_")
        img_bytes = base64.b64decode(images[0]["b64_json"])
        result_filename = f"image_{label}.png"
        result_path = save_result_file(user_id, job_uuid, ".png", img_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        logger.info("Image generate task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image generate")
        raise


# -- Image: edit --------------------------------------------------------------

@celery_app.task(bind=True, name="general.image_edit", queue="general")
def run_image_edit(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
    provider_id: int | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"

        # Standard OpenAI-compat transport: model in body, no provider quirks.
        # If a future provider requires a different convention, it gets its own
        # protocol adapter — not a transport-detection if/else here.
        base_url, edit_model, client = _image_http_client("image_edit", provider_id=provider_id, timeout=120.0)
        if not edit_model:
            from src.services.feature_router import FeatureNotConfigured
            raise FeatureNotConfigured("image_edit route has no model_name")

        # myLab/THL's image-edit pipeline crashes with "unsupported operand
        # type(s) for /: 'int' and 'NoneType'" when these numerics aren't
        # supplied — its internal defaults are absent. Vanilla OpenAI ignores
        # unknown fields; KISSKI's image-edit isn't reached via this path
        # anyway. Values match the "standard" quality preset documented in
        # the myLab wiki (guidance_scale=3.5, num_inference_steps=25).
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/images/edits",
                files={"image": (filename, content, mime)},
                data={
                    "model": edit_model,
                    "prompt": prompt,
                    "response_format": "b64_json",
                    "n": "1",
                    "size": "1024x1024",
                    "quality": "standard",
                    "guidance_scale": "3.5",
                    "num_inference_steps": "25",
                },
            )

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildbearbeitung (Status {response.status_code}): {response.text[:300]}")

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            img_bytes = response.content
        else:
            try:
                resp_data = response.json()
            except Exception:
                raise RuntimeError(f"Unerwartetes Antwortformat (Content-Type: {content_type}): {response.text[:300]}")
            b64 = (
                (resp_data.get("data") or [{}])[0].get("b64_json")
                or (resp_data.get("data") or [{}])[0].get("b64")
                or resp_data.get("b64_json")
                or resp_data.get("b64")
            )
            if not b64:
                keys = list(resp_data.keys()) if isinstance(resp_data, dict) else type(resp_data).__name__
                raise RuntimeError(f"Unerwartetes Antwortformat (keys: {keys}): {str(resp_data)[:300]}")
            img_bytes = base64.b64decode(b64)

        result_filename = f"{Path(filename).stem}.png"
        result_path = save_result_file(user_id, job_uuid, ".png", img_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image edit task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image edit")
        raise


# -- Image: analyze -----------------------------------------------------------

from src.tool_prompts import IMAGE_ANALYZE_DEFAULT as _IMAGE_ANALYZE_SYSTEM_PROMPT


@celery_app.task(bind=True, name="general.image_analyze", queue="general")
def run_image_analyze(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
    provider_id: int | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        b64_image = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64_image}"

        user_text = prompt.strip() if prompt and prompt.strip() else "Analyze this image."

        # qwen3-omni does not support a separate system role with vision content;
        # embed the system instructions as the first text block in the user message.
        # Same pattern works for qwen3-vl on the fallback slot.
        system_prompt = db.get_setting("prompt_image_analyze", _IMAGE_ANALYZE_SYSTEM_PROMPT)
        # Force the response language to the job creator's UI locale so the
        # user gets German output when they were running KIS in German etc.
        from src.tasks._errors import job_locale
        locale = job_locale(job_uuid)
        target_language = "German" if locale == "de" else "English"
        user_content = (
            f"{system_prompt}\n\n"
            f"Respond in {target_language}.\n\n"
            f"{user_text}"
        )

        base_url, model, client = _image_http_client("vision", provider_id=provider_id, timeout=60.0)
        if not model:
            # Vision has no defacto-default model name across providers
            # (qwen3-omni / qwen3-vl / gpt-4-vision / claude-3 are all valid
            # depending on the configured provider), so we fail loudly here.
            from src.services.feature_router import FeatureNotConfigured
            raise FeatureNotConfigured("vision route has no model_name")
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_content},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        },
                    ],
                },
            )

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildanalyse: {response.text[:200]}")

        resp_data = response.json()
        text: str = resp_data["choices"][0]["message"]["content"]

        result_filename = f"{Path(filename).stem}.txt"
        result_path = save_result_file(user_id, job_uuid, ".txt", text.encode("utf-8"))
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image analyze task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image analyze")
        raise


# -- Summary ------------------------------------------------------------------

_SUMMARY_OUTPUT_EXT = {"txt": ".txt", "md": ".md", "html": ".html"}
_SUMMARY_MIN_WORDS = 20
_SUMMARY_CONTEXT_WARN_CHARS = 80_000


@celery_app.task(bind=True, name="general.summary", queue="general")
def run_summary(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    output_format: str,
    provider_id: int | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        user_id = _resolve_user_id(job_uuid)
        job = db.get_job(job_uuid)
        locale = (job and job.get("creator_locale")) or "de"

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        client = _get_llm_client(provider_id)

        with job_heartbeat(job_uuid):
            from src.utils.text_extraction import EXTRACTORS
            extractor = EXTRACTORS.get(ext)
            if extractor is None:
                raise ValueError(f"Unsupported file type: {ext}")
            text = extractor(content)

            text = text.strip()
            word_count = len(text.split())
            if word_count < _SUMMARY_MIN_WORDS:
                raise ValueError(
                    t("summary.contentTooShort", locale, words=word_count, min=_SUMMARY_MIN_WORDS)
                )

            too_long = len(text) > _SUMMARY_CONTEXT_WARN_CHARS
            summary = client.generate_summary(
                text,
                output_format=output_format,
            )

        if too_long:
            summary += t("summary.contentTooLongHint", locale)

        out_ext = _SUMMARY_OUTPUT_EXT[output_format]
        output_name = f"{Path(filename).stem}{out_ext}"
        result_path = save_result_file(user_id, job_uuid, out_ext, summary.encode("utf-8"))
        save_result_and_evict(user_id, job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Summary task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        logger.error("Summary task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
