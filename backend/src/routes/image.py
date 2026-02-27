import base64
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user
from src.storage import save_result_file

router = APIRouter(tags=["image"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _get_kisski_http_client(
    timeout: float = 120.0,
    extra_headers: dict | None = None,
) -> httpx.AsyncClient:
    api_key = db.get_api_config_value("kisski_api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key nicht konfiguriert")
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.AsyncClient(headers=headers, timeout=timeout)


def _kisski_base_url() -> str:
    return (db.get_api_config_value("kisski_base_url") or "https://chat-ai.academiccloud.de/v1").rstrip("/")


@router.post("/image/generate")
async def generate_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    n: int = Form(1),
    current_user: dict = Depends(get_current_user),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt darf nicht leer sein")
    if n < 1 or n > 4:
        raise HTTPException(status_code=400, detail="Anzahl muss zwischen 1 und 4 liegen")
    if size not in {"1024x1024", "1280x720", "720x1280"}:
        raise HTTPException(status_code=400, detail="Ungültige Bildgröße")

    async with _get_kisski_http_client(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{_kisski_base_url()}/images/generations",
                json={
                    "model": "flux",
                    "prompt": prompt,
                    "size": size,
                    "n": n,
                    "response_format": "b64_json",
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout bei der Bildgenerierung")
        except httpx.RequestError as e:
            logger.exception("Image generation request error")
            raise HTTPException(status_code=502, detail=f"Verbindungsfehler: {str(e)}")

    if response.status_code != 200:
        logger.error(
            "KISSKI image/generate error: status={} body={}",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Fehler bei der Bildgenerierung: {response.text[:200]}",
        )

    data = response.json()
    images = [
        {"b64": item["b64_json"], "index": i}
        for i, item in enumerate(data.get("data", []))
    ]
    logger.info("Image generation completed: {} images", len(images))

    # Save first generated image to job history (non-fatal)
    if images:
        try:
            job_uuid = uuid.uuid4().hex
            user_id = current_user.get("user_id", 0)
            img_bytes = base64.b64decode(images[0]["b64"])
            label = prompt[:40].strip().replace(" ", "_")
            result_filename = f"bild_{label}.png"
            result_path = save_result_file(job_uuid, ".png", img_bytes)
            db.create_job(job_uuid, user_id, "image_generate", prompt[:100])
            db.update_job_result(job_uuid, result_path, result_filename)
            db.update_job_status(job_uuid, "success")
        except Exception:
            logger.exception("Job tracking failed for image generation")

    return {"images": images}


@router.post("/image/edit")
async def edit_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt darf nicht leer sein")
    if not image.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur PNG oder JPG erlaubt")

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Bild ist leer")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Bild zu groß (max 10 MB)")

    mime = "image/png" if ext == ".png" else "image/jpeg"

    async with _get_kisski_http_client(
        timeout=120.0,
        extra_headers={"inference-service": "image-edit-2511"},
    ) as client:
        try:
            response = await client.post(
                f"{_kisski_base_url()}/images/edits/",
                files={"image": (image.filename, content, mime)},
                data={"prompt": prompt},
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout bei der Bildbearbeitung")
        except httpx.RequestError as e:
            logger.exception("Image edit request error")
            raise HTTPException(status_code=502, detail=f"Verbindungsfehler: {str(e)}")

    if response.status_code != 200:
        logger.error(
            "KISSKI image/edit error: status={} body={}",
            response.status_code,
            response.content[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Fehler bei der Bildbearbeitung (Status {response.status_code})",
        )

    content_type = response.headers.get("content-type", "")
    if content_type.startswith("image/"):
        # API returns raw binary image bytes
        b64 = base64.b64encode(response.content).decode("utf-8")
    else:
        # API returns JSON with b64_json field
        try:
            data = response.json()
        except Exception:
            logger.error("KISSKI image/edit non-JSON response: {}", response.content[:200])
            raise HTTPException(status_code=502, detail="Unerwartetes Antwortformat vom Bildservice")
        b64 = (
            (data.get("data") or [{}])[0].get("b64_json")
            or (data.get("data") or [{}])[0].get("b64")
            or data.get("b64_json")
            or data.get("b64")
        )
        if not b64:
            logger.error("KISSKI image/edit missing b64 in response: {}", str(data)[:500])
            raise HTTPException(status_code=502, detail="Unerwartetes Antwortformat vom Bildservice")

    logger.info("Image edit completed for file '{}'", image.filename)

    # Save edited image to job history (non-fatal)
    try:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        img_bytes = base64.b64decode(b64)
        stem = Path(image.filename).stem
        result_filename = f"{stem}_bearbeitet.png"
        result_path = save_result_file(job_uuid, ".png", img_bytes)
        db.create_job(job_uuid, user_id, "image_edit", image.filename)
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
    except Exception:
        logger.exception("Job tracking failed for image edit of '{}'", image.filename)

    return {"b64": b64}


@router.post("/image/analyze")
async def analyze_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt darf nicht leer sein")
    if not image.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur PNG oder JPG erlaubt")

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="Bild ist leer")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Bild zu groß (max 10 MB)")

    mime = "image/png" if ext == ".png" else "image/jpeg"
    b64_image = base64.b64encode(content).decode("utf-8")
    data_url = f"data:{mime};base64,{b64_image}"

    async with _get_kisski_http_client(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{_kisski_base_url()}/chat/completions",
                json={
                    "model": "qwen3-vl-30b-a3b-instruct",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": data_url}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout bei der Bildanalyse")
        except httpx.RequestError as e:
            logger.exception("Image analyze request error")
            raise HTTPException(status_code=502, detail=f"Verbindungsfehler: {str(e)}")

    if response.status_code != 200:
        logger.error(
            "KISSKI image/analyze error: status={} body={}",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Fehler bei der Bildanalyse: {response.text[:200]}",
        )

    data = response.json()
    text: str = data["choices"][0]["message"]["content"]
    logger.info("Image analyze completed for file '{}'", image.filename)

    # Save analysis text to job history (non-fatal)
    try:
        job_uuid = uuid.uuid4().hex
        user_id = current_user.get("user_id", 0)
        stem = Path(image.filename).stem
        result_filename = f"{stem}_analyse.txt"
        result_path = save_result_file(job_uuid, ".txt", text.encode("utf-8"))
        db.create_job(job_uuid, user_id, "image_analyze", image.filename)
        db.update_job_result(job_uuid, result_path, result_filename)
        db.update_job_status(job_uuid, "success")
    except Exception:
        logger.exception("Job tracking failed for image analyze of '{}'", image.filename)

    return {"text": text}
