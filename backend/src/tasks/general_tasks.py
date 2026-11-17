"""Celery tasks: translate, transcribe, image_generate, image_edit, image_analyze."""

import base64
import json
from io import BytesIO
from pathlib import Path

from loguru import logger
from PIL import Image as PILImage

from src.celery_app import celery_app
from src import database as db
from src.limits import IMAGE_ANALYZE_MAX_TOKENS
from src.storage import (delete_file, get_file, open_input_file, save_job_file, save_result_file,
                         save_result_and_evict, save_result_meta)
from src.utils.heartbeat import job_heartbeat
from src.dependencies import get_translate_client_for_provider
from src.services.ai_hinweis import png_info_with_notice, vtt_with_notice
from src.services.translation import TranslationService
from src.services.job_statistik import angaben_merken, wer_antwortete
from src.services import provider_transport
from src.services.provider_transport import INFERENCE_SERVICE_HEADER
from src.tasks._clients import _get_llm_client, _image_http_client  # noqa: F401 - imported from here by other modules
from src.tasks._errors import handle_task_exception as _handle_task_exception
from src.tasks._errors import job_locale
from src.tool_prompts import IMAGE_ANALYZE_DEFAULT as _IMAGE_ANALYZE_SYSTEM_PROMPT

# A busy provider re-queues the job this often, waiting 30 s, 1 min, then 2 min each time.
_MAX_REQUEUES = 5


# -- Helpers ------------------------------------------------------------------

def _resolve_user_id(job_uuid: str) -> int:
    """Look up the owning user_id for a job (raises if the row vanished)."""
    row = db.get_job(job_uuid)
    if not row:
        raise RuntimeError(f"Job {job_uuid} not found")
    return row["user_id"]


def _png_with_notice(img_bytes: bytes) -> bytes:
    """Re-saves the PNG with the AI notice stamped in as a text chunk."""
    with PILImage.open(BytesIO(img_bytes)) as img:
        buf = BytesIO()
        img.save(buf, format="PNG", pnginfo=png_info_with_notice())
        return buf.getvalue()


def _image_route(feature: str, provider_id: int | None, timeout: float):
    """Address, model and client of an image route, a route without a model closes its client and fails."""
    base_url, model, client = _image_http_client(feature, provider_id=provider_id, timeout=timeout)
    if not model:
        from src.services.feature_router import FeatureNotConfigured
        client.close()
        raise FeatureNotConfigured(f"{feature} route has no model_name")
    return base_url, model, client


def _image_mime(ext: str) -> str:
    return "image/png" if ext == ".png" else "image/jpeg"


def parse_glossary(glossary_json: str) -> dict:
    """The glossary a route sent as JSON text, empty when it is missing or not an object."""
    if not glossary_json:
        return {}
    try:
        entries = json.loads(glossary_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    return entries if isinstance(entries, dict) else {}


def _requeue(task, job_uuid: str, e: Exception, label: str):
    """Puts the job back in the queue with a growing wait, finished parts stay remembered."""
    countdown = min(30 * (2 ** task.request.retries), 120)
    logger.warning(
        "{} job {} hit a temporary error (attempt {}/{}), retrying in {}s: {}",
        label, job_uuid, task.request.retries + 1, _MAX_REQUEUES, countdown, e,
    )
    raise task.retry(exc=e, countdown=countdown, max_retries=_MAX_REQUEUES)


# -- Translation --------------------------------------------------------------

def _translated_bytes(ext: str, content: bytes, source_lang: str, target_lang: str,
                      service: TranslationService) -> bytes:
    """The translated file in the format of the upload."""
    if ext == ".txt":
        return service.translate_text(content.decode("utf-8"), source_lang, target_lang).encode("utf-8")
    if ext == ".md":
        from src.translators.markdown import translate_markdown_preserve_code_blocks
        return translate_markdown_preserve_code_blocks(
            content.decode("utf-8"), source_lang, target_lang, service).encode("utf-8")
    if ext == ".tex":
        from src.translators.latex import translate_latex_preserve_structure
        from src.translators.latex_source import read_tex, write_tex
        # The result keeps the upload's encoding and line endings so it still fits the project files around it.
        source = read_tex(content)
        translated_text = translate_latex_preserve_structure(
            source.text, source_lang, target_lang, service, utf8_output=source.utf8_output
        )
        return write_tex(translated_text, source)
    if ext == ".docx":
        from src.translators.docx import translate_docx
        return translate_docx(content, source_lang, target_lang, service)
    if ext == ".pptx":
        from src.translators.pptx import translate_pptx
        return translate_pptx(content, source_lang, target_lang, service)
    raise ValueError(f"Unsupported format: {ext}")


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
        provider_transport.record_answering()
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        glossary_entries = parse_glossary(glossary_json)

        translation_client, glossary = get_translate_client_for_provider(
            provider_id, glossary_entries=glossary_entries or None
        )
        if translation_client is None:
            raise RuntimeError("No translation provider configured")

        service = TranslationService(deepl_client=translation_client, glossary=glossary)
        # A LaTeX file keeps its name because other files of the project load it by that name.
        translated_filename = filename if ext == ".tex" else service.translate_filename(filename, source_lang, target_lang)

        with job_heartbeat(job_uuid):
            result_bytes = _translated_bytes(ext, content, source_lang, target_lang, service)

        result_path = save_result_file(user_id, job_uuid, ext, result_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, translated_filename)
        angaben_merken(user_id, job_uuid, {
            "anbieter": wer_antwortete("doc_translate", provider_id),
            "ziel": target_lang, "glossar": bool(glossary_entries),
        })
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Translate task {} completed: {}", job_uuid, translated_filename)

    except Exception as e:
        # A full or unreachable provider re-queues like the transcription, a real error fails.
        from src.services.upstream_errors import is_upstream_busy

        if is_upstream_busy(e) and self.request.retries < _MAX_REQUEUES:
            _requeue(self, job_uuid, e, "Translate")
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
        provider_transport.record_answering()
        user_id = _resolve_user_id(job_uuid)

        from src.dependencies import resolve_whisper_client
        client = resolve_whisper_client(provider_id)
        ext_suffix = Path(filename).suffix.lower()

        # Reports every finished part so the display does not stall.
        def _on_chunk(done: int, total: int) -> None:
            db.update_job_status(
                job_uuid, "running",
                progress={"step": "transcribe", "current": done, "total": total},
            )

        with job_heartbeat(job_uuid), open_input_file(input_path, suffix=ext_suffix) as local_path:
            if task == "translate":
                result_text = client.transcribe_and_translate_chunked(
                    local_path, response_format=response_format, cache_key=job_uuid,
                    on_progress=_on_chunk)
            else:
                result_text = client.transcribe_chunked(
                    local_path, response_format=response_format, cache_key=job_uuid,
                    on_progress=_on_chunk)

        out_ext = _FORMAT_EXT[response_format]
        if task == "translate":
            from src.services.translation import translate_output_filename
            output_name = translate_output_filename(filename, output_ext=out_ext)
        else:
            output_name = f"{Path(filename).stem}{out_ext}"

        if response_format == "vtt":
            result_text = vtt_with_notice(result_text)

        result_path = save_result_file(user_id, job_uuid, out_ext, result_text.encode("utf-8"))
        save_result_and_evict(user_id, job_uuid, result_path, output_name)
        angaben_merken(user_id, job_uuid, {
            "anbieter": wer_antwortete("stt", provider_id), "format": response_format,
        })
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Transcribe task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        # Temporary disruptions re-queue, finished parts stay remembered.
        from src.services.openai_compat_llm.base import is_transient_error

        if is_transient_error(e) and self.request.retries < _MAX_REQUEUES:
            _requeue(self, job_uuid, e, "Transcribe")
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
    steps: int | None = None,
    titel: str = "",
    angaben: dict | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        provider_transport.record_answering()
        user_id = _resolve_user_id(job_uuid)

        # A large picture in high quality takes myLab about a minute, 300 s leave room for a busy provider.
        base_url, model, client = _image_route("image_gen", provider_id, 300.0)
        body: dict = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
        }
        if steps:
            body["num_inference_steps"] = steps

        with job_heartbeat(job_uuid), client:
            response = client.post(f"{base_url}/images/generations", json=body)
            from src.features.bild.optionen import kleiner
            # A provider with a size limit (GWDG: height up to 1080) gets the same picture shrunk into full HD.
            if response.status_code in (400, 422) and kleiner(size) != size:
                body = {**body, "size": kleiner(size)}
                response = client.post(f"{base_url}/images/generations", json=body)

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildgenerierung: {response.text[:200]}")

        data = response.json()
        images = data.get("data", [])
        if not images:
            raise RuntimeError("Keine Bilder generiert")

        # The person's own description names the file, the prompt starts with the style sentence.
        label = (titel or prompt)[:40].strip().replace(" ", "_")
        img_bytes = _png_with_notice(base64.b64decode(images[0]["b64_json"]))
        result_filename = f"image_{label}.png"
        result_path = save_result_file(user_id, job_uuid, ".png", img_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        # The picture's description stays with it, for the result card and the history.
        # The chosen style, format and quality go along, the picture shows what it was made with.
        save_result_meta(user_id, job_uuid, {**(angaben or {}), "beschreibung": titel or prompt,
                                             "modell_prompt": prompt, "groesse": body["size"],
                                             "anbieter": wer_antwortete("image_gen", provider_id)})
        db.update_job_status(job_uuid, "success")
        logger.info("Image generate task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image generate")
        raise


# -- Image: edit --------------------------------------------------------------

def _zuschneiden(inhalt: bytes, zuschnitt: dict) -> bytes:
    """The central band of a padded picture, the result and the kept source are cut the same way."""
    from src.features.bild.optionen import zuschneiden
    return zuschneiden(inhalt, zuschnitt)


def _edited_image(response) -> bytes:
    """The picture of an edit answer, sent either as the image itself or as base64 inside JSON."""
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("image/"):
        return response.content
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
    return base64.b64decode(b64)


@celery_app.task(bind=True, name="general.image_edit", queue="general")
def run_image_edit(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
    provider_id: int | None = None,
    size: str = "1024x1024",
    steps: int = 25,
    zuschnitt: dict | None = None,
    angaben: dict | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        provider_transport.record_answering()
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = _image_mime(ext)

        # The usual transfer, a deviating provider would get its own adapter.
        base_url, edit_model, client = _image_route("image_edit", provider_id, 300.0)

        # myLab explicitly needs these numbers, otherwise its image processing crashes.
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/images/edits",
                # GWDG picks its edit model only by this header, the others ignore it.
                headers={INFERENCE_SERVICE_HEADER: edit_model},
                files={"image": (filename, content, mime)},
                data={
                    "model": edit_model,
                    "prompt": prompt,
                    "response_format": "b64_json",
                    "n": "1",
                    "size": size,
                    "quality": "standard",
                    "guidance_scale": "3.5",
                    "num_inference_steps": str(steps),
                },
            )

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildbearbeitung (Status {response.status_code}): {response.text[:300]}")

        img_bytes = _edited_image(response)
        if zuschnitt:
            # A padded panorama comes back as the band that was the source.
            img_bytes = _zuschneiden(img_bytes, zuschnitt)
        img_bytes = _png_with_notice(img_bytes)
        result_filename = f"{Path(filename).stem}.png"
        result_path = save_result_file(user_id, job_uuid, ".png", img_bytes)
        save_result_and_evict(user_id, job_uuid, result_path, result_filename)
        # The source stays with the job for the before and after view, a padded one as the band it was.
        vorlage = f"vorlage{'.png' if zuschnitt else ext}"
        save_job_file(user_id, job_uuid, vorlage, _zuschneiden(content, zuschnitt) if zuschnitt else content)
        save_result_meta(user_id, job_uuid, {**(angaben or {}), "beschreibung": prompt, "groesse": size,
                                             "vorlage": vorlage, "anbieter": wer_antwortete("image_edit", provider_id)})
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image edit task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image edit")
        raise


# -- Image: analyze -----------------------------------------------------------

@celery_app.task(bind=True, name="general.image_analyze", queue="general")
def run_image_analyze(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
    provider_id: int | None = None,
    anweisung: str | None = None,
    angaben: dict | None = None,
):
    try:
        db.update_job_status(job_uuid, "running")
        provider_transport.record_answering()
        user_id = _resolve_user_id(job_uuid)

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = _image_mime(ext)
        b64_image = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64_image}"

        user_text = prompt.strip() if prompt and prompt.strip() else "Analyze this image."

        # The system instruction is the first text block, this model has no role of its own.
        system_prompt = db.get_setting("prompt_image_analyze", _IMAGE_ANALYZE_SYSTEM_PROMPT)
        # Forces the answer language of the requester.
        locale = job_locale(job_uuid)
        target_language = "German" if locale == "de" else "English"
        user_content = (
            f"{system_prompt}\n\n"
            f"Respond in {target_language}.\n\n"
            f"{user_text}"
        )
        # The tool page sends task, answer language and the lasting rules as one instruction, the general prompt
        # would override it with its call for detail and the language of the image.
        if anweisung:
            user_content = anweisung

        # There is no common model name for image description, so a route without one only fails.
        base_url, model, client = _image_route("vision", provider_id, 60.0)
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "max_tokens": IMAGE_ANALYZE_MAX_TOKENS,
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
        # The described picture stays with its answer, so the page can show both again later.
        vorlage = f"vorlage{ext}"
        save_job_file(user_id, job_uuid, vorlage, content)
        save_result_meta(user_id, job_uuid, {**(angaben or {}), "vorlage": vorlage, "dateiname": filename,
                                             "anbieter": wer_antwortete("vision", provider_id)})
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image analyze task {} completed", job_uuid)

    except Exception as e:
        _handle_task_exception(job_uuid, e, task_label="Image analyze")
        raise
