from pathlib import Path
import os

import deepl
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

app = FastAPI(title="Fachsprachen MVP - Dokumentübersetzung")


# Konfiguration aus .env laden (falls vorhanden)
load_dotenv()

TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "deepl")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
SOURCE_LANG = os.getenv("SOURCE_LANG", "DE")
TARGET_LANG_RAW = os.getenv("TARGET_LANG", "EN-US")
# DeepL benötigt "EN-US" oder "EN-GB", nicht "EN" - mappe "EN" zu "EN-US"
if TARGET_LANG_RAW.upper() == "EN":
    TARGET_LANG = "EN-US"
else:
    TARGET_LANG = TARGET_LANG_RAW

# DeepL Translator initialisieren (nur wenn Key vorhanden)
translator = None
if DEEPL_API_KEY:
    try:
        translator = deepl.Translator(DEEPL_API_KEY)
    except Exception as e:
        # Fehler beim Initialisieren wird später beim Übersetzen abgefangen
        pass


ALLOWED_EXTENSIONS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB für MVP


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/translate")
async def translate(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Nur .docx, .pptx oder .md erlaubt")

    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 10 MB)")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 10 MB)")

    # Markdown-Dateien übersetzen, DOCX/PPTX weiterhin Echo
    if ext == ".md":
        if not translator:
            raise HTTPException(
                status_code=500,
                detail="DeepL API Key fehlt oder Translator konnte nicht initialisiert werden",
            )
        try:
            # Markdown als UTF-8 Text dekodieren
            text = content.decode("utf-8")
            # TARGET_LANG sollte bereits beim Laden gemappt sein (EN -> EN-US)
            # Zur absoluten Sicherheit nochmal prüfen und mappen
            target_lang_final = TARGET_LANG.strip()
            if target_lang_final.upper() in ("EN", ""):
                target_lang_final = "EN-US"
            # Übersetzen
            translated_text = translator.translate_text(
                text, source_lang=SOURCE_LANG, target_lang=target_lang_final
            )
            # Zurück zu Bytes encoden
            content = translated_text.text.encode("utf-8")
            download_name = f"{Path(file.filename).stem}_translated{ext}"
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Übersetzungsfehler: {str(e)}"
            )
    else:
        # DOCX/PPTX: Echo (später hier Pipeline einbauen)
        download_name = f"{Path(file.filename).stem}_echo{ext}"

    return StreamingResponse(
        iter([content]),
        media_type=ALLOWED_EXTENSIONS[ext],
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )
