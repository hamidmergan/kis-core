import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from loguru import logger

from src.dependencies import get_kisski_client, get_settings
from src.utils.file_validation import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from src.utils.text_extraction import EXTRACTORS

router = APIRouter(tags=["script"])



@router.post("/script")
async def generate_script(
    request: Request,
    file: UploadFile = File(...),
    glossary_json: str = Form(""),
):
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Nur .docx, .pptx, .md oder .tex erlaubt"
        )

    # Validate file size
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 200 MB)")

    # Extract text
    extractor = EXTRACTORS.get(ext)
    if extractor is None:
        raise HTTPException(status_code=400, detail="Dateityp wird nicht unterstützt")

    try:
        text = extractor(content)
    except Exception as e:
        logger.exception("Text extraction error for file '{}'", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Fehler beim Lesen der Datei: {str(e)}"
        )

    if not text.strip():
        raise HTTPException(status_code=400, detail="Kein Text in der Datei gefunden")

    # Generate script via LLM
    glossary_dict: dict | None = None
    if glossary_json:
        try:
            glossary_dict = json.loads(glossary_json)
        except (json.JSONDecodeError, TypeError):
            pass
    client = get_kisski_client()
    try:
        script = client.generate_script(text, glossary=glossary_dict)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Script generation error for file '{}'", file.filename)
        raise HTTPException(
            status_code=500, detail=f"Fehler bei der Skripterstellung: {str(e)}"
        )

    logger.info("Script generation completed for file '{}'", file.filename)

    # Build output filename
    stem = Path(file.filename).stem
    output_name = f"{stem}_skript.md"
    encoded_name = quote(output_name, safe="")

    return Response(
        content=script.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{encoded_name}"; filename*=UTF-8\'\'{encoded_name}'
        },
    )
