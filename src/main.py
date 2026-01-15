from io import BytesIO
from pathlib import Path
import os
from urllib.parse import quote

import deepl
from docx import Document
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


def translate_docx(content: bytes, source_lang: str, target_lang: str) -> bytes:
    """
    Übersetzt Text in einer DOCX-Datei.
    Layout, Formatierung und Struktur bleiben erhalten.
    Strategie: Absätze in Blöcken sammeln und übersetzen (schneller als einzeln).
    """
    if not translator:
        raise ValueError("Translator nicht initialisiert")
    
    try:
        # DOCX aus Bytes öffnen
        doc = Document(BytesIO(content))
        
        # Alle Absätze sammeln (nur nicht-leere)
        paragraphs_with_text = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs_with_text.append((para, text))
        
        if not paragraphs_with_text:
            # Keine Text-Absätze gefunden, Datei unverändert zurückgeben
            output = BytesIO()
            doc.save(output)
            return output.getvalue()
        
        # Absätze in Blöcken von 5 übersetzen (weniger API-Calls = schneller)
        BLOCK_SIZE = 5
        for i in range(0, len(paragraphs_with_text), BLOCK_SIZE):
            block = paragraphs_with_text[i:i + BLOCK_SIZE]
            
            # Text aus Block sammeln
            block_texts = [text for _, text in block]
            combined_text = "\n\n".join(block_texts)
            
            try:
                # Block übersetzen
                translated = translator.translate_text(
                    combined_text,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                
                # Übersetzten Text wieder aufteilen (bei \n\n trennen)
                translated_parts = translated.text.split("\n\n")
                
                # Übersetzte Teile wieder zuordnen
                for j, (para, _) in enumerate(block):
                    if j < len(translated_parts):
                        para.text = translated_parts[j].strip()
                    # Falls weniger Teile zurückkommen, letzten Teil verwenden
                    elif translated_parts:
                        para.text = translated_parts[-1].strip()
                        
            except Exception as e:
                raise ValueError(f"Fehler beim Übersetzen von Block {i//BLOCK_SIZE + 1}: {str(e)}")
        
        # Zurück zu Bytes konvertieren
        output = BytesIO()
        doc.save(output)
        output.seek(0)
        return output.getvalue()
        
    except ValueError:
        raise
    except Exception as e:
        import traceback
        raise ValueError(f"Fehler beim Verarbeiten der DOCX-Datei: {str(e)}\n{traceback.format_exc()}")


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

    # TARGET_LANG sollte bereits beim Laden gemappt sein (EN -> EN-US)
    # Zur absoluten Sicherheit nochmal prüfen und mappen
    target_lang_final = TARGET_LANG.strip()
    if target_lang_final.upper() in ("EN", ""):
        target_lang_final = "EN-US"
    
    if not translator:
        raise HTTPException(
            status_code=500,
            detail="DeepL API Key fehlt oder Translator konnte nicht initialisiert werden",
        )
    
    # Markdown-Dateien übersetzen
    if ext == ".md":
        try:
            # Markdown als UTF-8 Text dekodieren
            text = content.decode("utf-8")
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
    # DOCX-Dateien übersetzen
    elif ext == ".docx":
        try:
            content = translate_docx(content, SOURCE_LANG, target_lang_final)
            download_name = f"{Path(file.filename).stem}_translated{ext}"
        except ValueError as e:
            raise HTTPException(
                status_code=500, detail=f"DOCX-Übersetzungsfehler: {str(e)}"
            )
        except Exception as e:
            # Detaillierte Fehlermeldung für Debugging
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            # Fehler auch in Console loggen
            print(f"DOCX-Fehler: {error_msg}")
            print(f"Traceback: {error_trace}")
            raise HTTPException(
                status_code=500, detail=f"DOCX-Verarbeitungsfehler: {error_msg}"
            )
    else:
        # PPTX: Echo (später hier Pipeline einbauen)
        download_name = f"{Path(file.filename).stem}_echo{ext}"

    # Dateiname für HTTP-Header encoden (RFC 2231 kompatibel)
    # Sonderzeichen müssen URL-encoded werden
    encoded_filename = quote(download_name, safe='')
    
    return StreamingResponse(
        iter([content]),
        media_type=ALLOWED_EXTENSIONS[ext],
        headers={
            "Content-Disposition": f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        },
    )
