# KIS-THL

Webbasierter Übersetzungs- und Medienservice für Dokumente der TH Lübeck. Übersetzt DOCX, PPTX, MD, TEX und PDF automatisch von Deutsch nach Englisch – mit Glossar für konsistente Fachbegriffe. Zusätzlich: Text-to-Speech, Skript-Generierung, Transkription, Video-Dubbing und automatische Screencast-Erstellung aus PPTX-Dateien.

## Architektur

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS (Port 3000)
- **Backend**: FastAPI, DeepL API, ElevenLabs API, KISSKI LLM, python-docx, python-pptx, FFmpeg (Port 8000)

## Quick Start

```bash
cp env.example .env   # .env anpassen (siehe Konfiguration)
docker-compose up -d --build
```

## Development Setup

Nach dem Klonen einmalig ausführen damit die IDE (VSCode, WebStorm, Cursor etc.) TypeScript-Typen kennt:

```bash
cd frontend && npm install
```

- Frontend: `http://localhost:3000`
- API-Docs: `http://localhost:8000/docs`

Stoppen: `docker-compose down`

## Funktionen

### Dokumentübersetzung

Übersetzt Dokumente von Deutsch nach Englisch mit Layout-Erhalt und optionalem Glossar.

| Format | Methode | Hinweis |
|--------|---------|---------|
| `.docx` | Eigener Parser | Layout-Erhalt |
| `.pptx` | Eigener Parser | inkl. Footer, Notizen, Master |
| `.md` | Eigener Parser | Code-Blöcke bleiben unverändert |
| `.tex` | Eigener Parser | Mathematik/Verbatim bleiben unverändert |
| `.pdf` | DeepL Document API | Einschränkungen bei Formeln/komplexen Layouts |

### Text-to-Speech (TTS)

Wandelt Dokumente in gesprochene MP3-Audiodateien um (via ElevenLabs API).

- Geschwindigkeitsregelung (0.5x – 1.2x)
- Pausen-Presets (kurz, mittel, lang, sehr lang)
- Erweiterte Spracheinstellungen (Stabilität, Ähnlichkeit, Stil, Speaker-Boost)

### Skript-Generierung

Erstellt per KI gesprochene Vortragstext-Skripte aus Dokumenten (via KISSKI LLM).

- Upload eines Dokuments, KI generiert passenden Sprechertext
- Download als Markdown

### Transkription

Transkribiert Audio- und Videodateien zu Text (via KISSKI Whisper).

- Aufgabenmodus: Transkription oder Übersetzung
- Ausgabeformate: Text, SRT, VTT
- Unterstützt diverse Audio-/Videoformate

### Video-Dubbing

Synchronisierte Videovertonung in andere Sprachen (via ElevenLabs API).

- 12 unterstützte Sprachen
- Option zur Entfernung von Hintergrundaudio
- MP4-Upload und -Download

### Screencast-Erstellung

Erstellt automatisch ein Screencast-Video aus einer PPTX-Präsentation: Übersetzung → Skript-Generierung → TTS → Video-Rendering.

**Auto-Modus**: Vollautomatischer Durchlauf mit einem Klick.

**Manueller Modus**: Schritt-für-Schritt mit Bearbeitungsmöglichkeit:

1. PPTX hochladen
2. Übersetzung (mit Glossar-Unterstützung)
3. Optionaler User-Prompt zur Skript-Anpassung
4. Übersetzung prüfen (Slide-Vorschau, korrigierte PPTX hochladen)
5. Skript-Generierung per KI
6. Skripte pro Folie bearbeiten
7. TTS-Einstellungen (Geschwindigkeit, Pausen)
8. Video-Rendering
9. MP4-Download

## Glossar

Das Glossar stellt sicher, dass Fachbegriffe bei der Übersetzung konsistent mit den gewünschten Zielsprachbegriffen ersetzt werden – unabhängig davon, was das jeweilige Übersetzungs-API zurückliefern würde.

### Verwaltung

- Pflege über den Glossar-Tab im Frontend (Deutsch → Englisch)
- Die Einträge leben nur im Browser (kein Server-Speicher, kein Datenbank-Speicher)
- Beim Absenden einer Übersetzungsanfrage werden die Einträge als JSON im Request-Body mitgesendet

### Technische Umsetzung: Token-Ersatz-Verfahren

Das Projekt nutzt **kein** natives Glossar-Feature von DeepL oder einem anderen API-Anbieter. Stattdessen kommt ein eigenes Token-Ersatz-Verfahren zum Einsatz, das API-unabhängig funktioniert:

1. **Vor** der Übersetzung: Glossar-Begriffe im Originaltext werden durch eindeutige Platzhalter ersetzt (`__GLOSSARY_0__`, `__GLOSSARY_1__`, …)
2. Der präparierte Text (mit Platzhaltern) wird an die Übersetzungs-API gesendet – die Platzhalter bleiben dabei unberührt
3. **Nach** der Übersetzung: Die Platzhalter werden durch die definierten Zielbegriffe ersetzt

**Beispiel:**

```
Eingabe:        "Die Lehrveranstaltung beginnt pünktlich."
Nach Schritt 1: "Die __GLOSSARY_0__ beginnt pünktlich."
Nach DeepL:     "The __GLOSSARY_0__ starts on time."
Ausgabe:        "The Course starts on time."
```

Längere Begriffe werden bevorzugt zuerst ersetzt, um Überschneidungen zu vermeiden.

### Wo wird das Glossar angewendet?

| Tool | Glossar aktiv | Hinweis |
|------|:---:|---------|
| Dokumentübersetzung (DOCX, PPTX, MD, TEX) | ✅ | Token-Ersatz via `GlossaryService` |
| Screencast-Übersetzung (PPTX-Schritt) | ✅ | Gleiche Logik wie Dokumentübersetzung |
| Transkription | ❌ | Direkter KISSKI-Whisper-Aufruf, kein Glossar |
| Text-to-Speech | ❌ | ElevenLabs-Aufruf, kein Glossar |
| Video-Dubbing | ❌ | ElevenLabs-Aufruf, kein Glossar |
| Skript-Generierung | ✅ | Glossar-Einträge werden als Terminologie-Anweisung in den LLM-System-Prompt eingefügt (kein Token-Ersatz) |

## API-Endpunkte

| Endpunkt | Methode | Beschreibung |
|----------|---------|-------------|
| `/auth/login` | POST | Login |
| `/auth/logout` | POST | Logout |
| `/auth/status` | GET | Auth-Status prüfen |
| `/health` | GET | Health-Check |
| `/translate` | POST | Dokument übersetzen (eigene Parser) |
| `/translate-document` | POST | Dokument übersetzen (DeepL Document API) |
| `/tts` | POST | Text-to-Speech (Dokument → MP3) |
| `/script` | POST | Skript-Generierung (Dokument → Sprechertext) |
| `/transcription` | POST | Audio/Video-Transkription |
| `/video-dubbing` | POST | Video-Dubbing |
| `/screencast` | POST | Screencast (Auto-Modus) |
| `/screencast/translate` | POST | Screencast: PPTX übersetzen + Texte/Bilder extrahieren |
| `/screencast/extract-texts` | POST | Screencast: Texte aus PPTX extrahieren |
| `/screencast/prepare` | POST | Screencast: PPTX → Slide-Bilder |
| `/screencast/generate-scripts` | POST | Screencast: Skripte generieren |
| `/screencast/render` | POST | Screencast: MP4 rendern |

## Konfiguration

| Variable | Beschreibung | Standard |
|----------|-------------|----------|
| `DEEPL_API_KEY` | DeepL API Key | – |
| `SOURCE_LANG` | Quellsprache | `DE` |
| `TARGET_LANG` | Zielsprache | `EN-US` |
| `ELEVENLABS_API_KEY` | ElevenLabs API Key (TTS, Dubbing) | – |
| `KISSKI_API_KEY` | KISSKI LLM API Key (Skripte, Transkription) | – |
| `KISSKI_BASE_URL` | KISSKI API Base-URL | `https://chat-ai.academiccloud.de/v1` |
| `KISSKI_MODEL` | KISSKI LLM-Modell | `qwen3-30b-a3b-instruct-2507` |
| `APP_PASSWORD` | Login-Passwort | `admin` |
| `SESSION_SECRET` | Secret für Session-Tokens | – |
| `SESSION_MAX_AGE_SECONDS` | Session-Dauer in Sekunden | `86400` |
| `PRODUCTION` | Produktionsmodus (Swagger UI aus, Secure Cookies) | `false` |

## Systemabhängigkeiten (Backend-Container)

- **FFmpeg** – Video-/Audio-Verarbeitung (Screencast, TTS-Pausen)
- **LibreOffice** – PPTX → PDF Konvertierung (Screencast)
- **poppler-utils** – PDF → PNG Konvertierung (Screencast)

Diese werden im Docker-Image automatisch installiert.
