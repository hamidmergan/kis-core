# MVP Dokument-Übersetzung (DE -> EN)

MVP: DOCX/PPTX/MD rein -> übersetzte Datei raus.
http://127.0.0.1:8000/health -> {"status":"ok"}
Test über Swagger UI: http://127.0.0.1:8000/docs

POST /translate (Echo-MVP)
- Datei upload: .docx/.pptx/.md (sonst 400)
- Leere Datei -> 400
- Antwort: identische Datei als Download `name_echo.ext`, Content-Type gesetzt
- Max Upload: 10 MB (413 bei Überschreitung)