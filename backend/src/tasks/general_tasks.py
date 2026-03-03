"""Celery tasks: translate, transcribe, image_generate, image_edit, image_analyze, script, summary."""

import base64
import json
import tempfile
from pathlib import Path

from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import delete_file, get_file, open_input_file, save_queue_file, save_result_file  # noqa: F401
from src.utils.heartbeat import job_heartbeat


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_kisski_client():
    from src.services.kisski_client import KisskiClient
    from src.config import Settings
    s = Settings()
    if not s.kisski_api_key:
        raise RuntimeError("KISSKI API Key nicht konfiguriert")
    return KisskiClient(api_key=s.kisski_api_key, base_url=s.kisski_base_url, model=s.kisski_model)


def _kisski_http_client(extra_headers: dict | None = None, timeout: float = 120.0):
    import httpx
    from src.config import Settings
    s = Settings()
    if not s.kisski_api_key:
        raise RuntimeError("KISSKI API Key nicht konfiguriert")
    base_url = s.kisski_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {s.kisski_api_key}"}
    if extra_headers:
        headers.update(extra_headers)
    return base_url, httpx.Client(headers=headers, timeout=timeout)


# ── Translation ───────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="general.translate", queue="general")
def run_translate(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    source_lang: str,
    target_lang: str,
):
    try:
        db.update_job_status(job_uuid, "running")

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.services.deepl_client import DeepLClient
        from src.services.glossary import GlossaryService
        from src.services.translation import TranslationService

        from src.config import Settings
        api_key = Settings().deepl_api_key
        if not api_key:
            raise RuntimeError("DeepL API Key nicht konfiguriert")

        deepl_client = DeepLClient(api_key)
        glossary = GlossaryService()
        if glossary_json:
            try:
                entries = json.loads(glossary_json)
                if isinstance(entries, dict):
                    glossary.set_entries(entries)
            except (json.JSONDecodeError, TypeError):
                pass

        service = TranslationService(deepl_client=deepl_client, glossary=glossary)
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

        result_path = save_result_file(job_uuid, ext, result_bytes)
        db.update_job_result(job_uuid, result_path, translated_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Translate task {} completed: {}", job_uuid, translated_filename)

    except Exception as e:
        logger.error("Translate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Transcription ─────────────────────────────────────────────────────────────

_FORMAT_EXT = {"text": ".txt", "srt": ".srt", "vtt": ".vtt"}


@celery_app.task(bind=True, name="general.transcribe", queue="general")
def run_transcribe(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    task: str,
    response_format: str,
):
    try:
        db.update_job_status(job_uuid, "running")

        client = _get_kisski_client()
        ext_suffix = Path(filename).suffix.lower()

        with job_heartbeat(job_uuid), open_input_file(input_path, suffix=ext_suffix) as local_path:
            if task == "translate":
                result_text = client.transcribe_and_translate(local_path, response_format=response_format)
            else:
                result_text = client.transcribe(local_path, response_format=response_format)

        out_ext = _FORMAT_EXT[response_format]
        if task == "translate":
            from src.services.translation import translate_output_filename
            output_name = translate_output_filename(filename, output_ext=out_ext)
        else:
            output_name = f"{Path(filename).stem}{out_ext}"

        result_path = save_result_file(job_uuid, out_ext, result_text.encode("utf-8"))
        db.update_job_result(job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Transcribe task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        logger.error("Transcribe task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Image: Generate ───────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="general.image_generate", queue="general")
def run_image_generate(
    self,
    job_uuid: str,
    prompt: str,
    size: str,
    n: int,
):
    try:
        db.update_job_status(job_uuid, "running")

        base_url, client = _kisski_http_client(timeout=120.0)
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/images/generations",
                json={"model": "flux", "prompt": prompt, "size": size, "n": n, "response_format": "b64_json"},
            )

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildgenerierung: {response.text[:200]}")

        data = response.json()
        images = data.get("data", [])
        if not images:
            raise RuntimeError("Keine Bilder generiert")

        label = prompt[:40].strip().replace(" ", "_")
        if len(images) == 1:
            img_bytes = base64.b64decode(images[0]["b64_json"])
            result_filename = f"image_{label}.png"
            result_path = save_result_file(job_uuid, ".png", img_bytes)
        else:
            images_data = [
                {"b64_json": img["b64_json"], "filename": f"image_{label}_{i + 1}.png"}
                for i, img in enumerate(images)
            ]
            result_json = json.dumps({"images": images_data})
            result_filename = f"images_{label}.json"
            result_path = save_result_file(job_uuid, ".json", result_json.encode("utf-8"))
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        logger.info("Image generate task {} completed ({} images)", job_uuid, len(images))

    except Exception as e:
        logger.error("Image generate task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Image: Edit ───────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="general.image_edit", queue="general")
def run_image_edit(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
):
    try:
        db.update_job_status(job_uuid, "running")

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"

        base_url, client = _kisski_http_client(
            extra_headers={"inference-service": "image-edit-2511"},
            timeout=120.0,
        )
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/images/edits/",
                files={"image": (filename, content, mime)},
                data={"prompt": prompt},
            )

        if response.status_code != 200:
            raise RuntimeError(f"Fehler bei der Bildbearbeitung (Status {response.status_code})")

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("image/"):
            img_bytes = response.content
        else:
            try:
                resp_data = response.json()
            except Exception:
                raise RuntimeError("Unerwartetes Antwortformat vom Bildservice")
            b64 = (
                (resp_data.get("data") or [{}])[0].get("b64_json")
                or (resp_data.get("data") or [{}])[0].get("b64")
                or resp_data.get("b64_json")
                or resp_data.get("b64")
            )
            if not b64:
                raise RuntimeError("Unerwartetes Antwortformat vom Bildservice")
            img_bytes = base64.b64decode(b64)

        from src.services.translation import translate_output_filename
        result_filename = translate_output_filename(filename, output_ext=".png")
        result_path = save_result_file(job_uuid, ".png", img_bytes)
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image edit task {} completed", job_uuid)

    except Exception as e:
        logger.error("Image edit task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Image: Analyze ────────────────────────────────────────────────────────────

_IMAGE_ANALYZE_SYSTEM_PROMPT = (
    "You are an assistant helping university lecturers analyze visual content. "
    "Describe the image in detail: transcribe all visible text verbatim, explain "
    "diagrams, charts, tables, and other visual elements. Be precise and complete. "
    "Respond in the same language as the image content."
)


@celery_app.task(bind=True, name="general.image_analyze", queue="general")
def run_image_analyze(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    prompt: str,
):
    try:
        db.update_job_status(job_uuid, "running")

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        b64_image = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64_image}"

        user_text = prompt.strip() if prompt and prompt.strip() else "Analyze this image."

        # qwen3-vl does not support a separate system role with vision content;
        # embed the system instructions as the first text block in the user message.
        system_prompt = db.get_setting("prompt_image_analyze", _IMAGE_ANALYZE_SYSTEM_PROMPT)
        user_content = f"{system_prompt}\n\n{user_text}"

        base_url, client = _kisski_http_client(timeout=60.0)
        with job_heartbeat(job_uuid), client:
            response = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": "qwen3-vl-30b-a3b-instruct",
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

        from src.services.translation import translate_output_filename
        result_filename = translate_output_filename(filename, output_ext=".txt")
        result_path = save_result_file(job_uuid, ".txt", text.encode("utf-8"))
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Image analyze task {} completed", job_uuid)

    except Exception as e:
        logger.error("Image analyze task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Script ────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="general.script", queue="general")
def run_script(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    glossary_json: str,
    user_prompt: str = "",
):
    try:
        db.update_job_status(job_uuid, "running")

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()

        from src.utils.text_extraction import EXTRACTORS
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            raise ValueError(f"Unsupported file type: {ext}")
        text = extractor(content)
        if not text.strip():
            raise ValueError("Kein Text in der Datei gefunden")

        glossary_dict: dict | None = None
        if glossary_json:
            try:
                glossary_dict = json.loads(glossary_json)
            except (json.JSONDecodeError, TypeError):
                pass

        client = _get_kisski_client()
        with job_heartbeat(job_uuid):
            script = client.generate_script(text, glossary=glossary_dict, user_prompt=user_prompt or None)

        from src.services.translation import translate_output_filename
        output_name = translate_output_filename(filename, output_ext=".txt")
        result_path = save_result_file(job_uuid, ".txt", script.encode("utf-8"))
        db.update_job_result(job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Script task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        logger.error("Script task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise


# ── Summary ───────────────────────────────────────────────────────────────────

_SUMMARY_OUTPUT_EXT = {"txt": ".txt", "md": ".md", "html": ".html"}
_SUMMARY_MIN_WORDS = 20
_SUMMARY_CONTEXT_WARN_CHARS = 80_000


@celery_app.task(bind=True, name="general.summary", queue="general")
def run_summary(
    self,
    job_uuid: str,
    input_path: str,
    filename: str,
    user_prompt: str,
    output_format: str,
):
    try:
        db.update_job_status(job_uuid, "running")

        content = get_file(input_path)
        ext = Path(filename).suffix.lower()
        client = _get_kisski_client()

        with job_heartbeat(job_uuid):
            if ext == ".mp3":
                with tempfile.TemporaryDirectory() as tmpdir:
                    audio_file = Path(tmpdir) / f"input{ext}"
                    audio_file.write_bytes(content)
                    text = client.transcribe(str(audio_file), response_format="text")
            else:
                from src.utils.text_extraction import EXTRACTORS
                extractor = EXTRACTORS.get(ext)
                if extractor is None:
                    raise ValueError(f"Unsupported file type: {ext}")
                text = extractor(content)

            text = text.strip()
            word_count = len(text.split())
            if word_count < _SUMMARY_MIN_WORDS:
                raise ValueError(
                    f"Inhalt zu kurz ({word_count} Wörter). Mindestens {_SUMMARY_MIN_WORDS} Wörter erforderlich."
                )

            too_long = len(text) > _SUMMARY_CONTEXT_WARN_CHARS
            summary = client.generate_summary(
                text,
                user_prompt=user_prompt or None,
                output_format=output_format,
            )

        if too_long:
            summary += (
                "\n\n⚠️ Hinweis: Der Inhalt war sehr umfangreich. "
                "Die Zusammenfassung könnte unvollständig sein."
            )

        out_ext = _SUMMARY_OUTPUT_EXT[output_format]
        from src.services.translation import translate_output_filename
        output_name = translate_output_filename(filename, output_ext=out_ext)
        result_path = save_result_file(job_uuid, out_ext, summary.encode("utf-8"))
        db.update_job_result(job_uuid, result_path, output_name)
        db.update_job_status(job_uuid, "success")
        delete_file(input_path)
        logger.info("Summary task {} completed: {}", job_uuid, output_name)

    except Exception as e:
        logger.error("Summary task {} failed: {}", job_uuid, e)
        db.update_job_status(job_uuid, "failed", error_message=str(e))
        raise
