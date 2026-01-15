# MVP Dokument-Übersetzung (DE -> EN)

MVP: DOCX/PPTX/MD rein -> übersetzte Datei raus.
http://127.0.0.1:8000/health -> {"status":"ok"}
Test über Swagger UI: http://127.0.0.1:8000/docs
Neuer Endpoint: POST /translate-document (DeepL Document Translation für DOCX/PPTX/PDF)
Reload Server: python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000 
