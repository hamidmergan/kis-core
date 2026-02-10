# Dokument-Übersetzung (DE -> EN)

DOCX/PPTX/MD rein -> übersetzte Datei raus.

## Installation & Start (Docker)

### 1. Vorbereitung

Erstelle eine `.env` Datei im Projektordner:
- Kopiere `env.example` zu `.env`
- Trage deinen **DeepL API Key** ein:
  ```
  TRANSLATION_PROVIDER=deepl
  DEEPL_API_KEY=dein_echter_key_hier
  SOURCE_LANG=DE
  TARGET_LANG=EN
  ```

### 2. Starten

```bash
docker-compose up -d --build
```

### 3. Logs prüfen

```bash
docker logs -f kis-thl
```

### 4. Zugriff

Öffne im Browser: **http://localhost:8000**

- **Swagger UI** (API Dokumentation & Tests): http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health → `{"status":"ok"}`

### 5. Stoppen

```bash
docker-compose down
```

## Verwendung

- **Endpoints**:
  - `POST /translate` - Übersetzt DOCX, PPTX, MD, TEX Dateien
  - `POST /translate-document` - DeepL Document Translation für DOCX/PPTX/PDF

### Unterstützte Formate

**POST /translate:**
- ✅ `.docx` - Word-Dokumente mit Layout-Erhalt
- ✅ `.pptx` - PowerPoint-Präsentationen mit Layout-Erhalt
- ✅ `.md` - Markdown-Dateien
- ✅ `.tex` - LaTeX-Dateien (Code-Blöcke bleiben unverändert)
- ❌ `.pdf` - **Nicht unterstützt** (siehe Begründung unten)

**POST /translate-document:**
- ✅ `.docx` - Word-Dokumente (via DeepL Document API)
- ✅ `.pptx` - PowerPoint-Präsentationen (via DeepL Document API)
- ⚠️ `.pdf` - PDF-Dateien (via DeepL Document API) - **mit Einschränkungen** (siehe unten)

### Warum PDF nicht in POST /translate?

PDF-Dateien sind **binäre Formate** ohne editierbare Textstruktur. Eine direkte Text-Ersetzung würde:
- Das Layout zerstören
- Bilder, Formen und Formatierungen verlieren
- Die Dokumentstruktur beschädigen

### PDF-Einschränkungen bei POST /translate-document

Auch die DeepL Document Translation API hat bei PDFs **Limitationen**:
- ⚠️ **Formeln/Mathematik**: Mathematische Formeln werden oft nicht korrekt erkannt oder übersetzt
- ⚠️ **Komplexe Layouts**: Bei mehrspaltigen Layouts oder komplexen Strukturen kann es zu Problemen kommen
- ⚠️ **Bilder mit Text**: Text in Bildern wird nicht übersetzt (OCR nicht verfügbar)

**Empfehlung:** Für PDFs mit vielen Formeln oder komplexen Layouts sollte die **Quelldatei** (DOCX/PPTX) verwendet werden, falls verfügbar.

## Features

- ✅ Markdown-Übersetzung (DE → EN) mit Code-Block-Erhalt
- ✅ LaTeX-Übersetzung (DE → EN) mit Code-Block-Erhalt
- ✅ DOCX-Übersetzung mit Layout-Erhalt
- ✅ PPTX-Übersetzung mit Layout-Erhalt (inkl. Footer, Notizen, Master)
- ✅ Zeilenumbrüche, Tabs und Formatierung bleiben erhalten
- ✅ Dateinamen werden übersetzt
