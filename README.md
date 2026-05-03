# KIS

> Built by **Hamid Mergan** at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck
> hamid.mergan@th-luebeck.de · hamid.mergan@gmail.com

Web-based translation and media service for documents at TH Lübeck. Translates DOCX, PPTX, MD, TEX and PDF files automatically from German to English, with a glossary for consistent terminology. Also provides text-to-speech, script generation, transcription, and automatic screencast creation from PPTX files.

## Architecture

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS (port 3000)
- **Backend**: FastAPI, DeepL API, ElevenLabs API, KISSKI LLM, python-docx, python-pptx, FFmpeg (port 8000)

## Quick Start

```bash
cp .env.example .env   # adjust .env (see Configuration)
docker-compose up -d --build
```

## Local Development

Run the backend in Docker:
```bash
docker compose up backend
```

Run the frontend locally (hot reload, no rebuild needed):
```bash
cd frontend && npm run dev
```

The frontend is served on http://localhost:3001 (or 3000 if free).
Frontend changes are visible in the browser immediately.
Backend changes are auto-reloaded.


## Development Setup

After cloning, run this once so the IDE (VSCode, WebStorm, Cursor, etc.) picks up TypeScript types:

```bash
cd frontend && npm install
```

- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

Stop everything: `docker-compose down`

## Features

### Document translation

Translates documents from German to English while preserving layout. Supports an optional glossary.

| Format | Method | Notes |
|--------|--------|-------|
| `.docx` | Custom parser | Layout preserved |
| `.pptx` | Custom parser | Includes footer, notes, master |
| `.md` | Custom parser | Code blocks remain unchanged |
| `.tex` | Custom parser | Math/verbatim remain unchanged |
| `.pdf` | DeepL Document API | Limitations on formulas/complex layouts |

### Text-to-Speech (TTS)

Converts documents into spoken MP3 audio (via the ElevenLabs API).

- Speed control (0.5x to 1.2x)
- Pause presets (short, medium, long, very long)
- Advanced voice settings (stability, similarity, style, speaker boost)

### Script generation

Generates AI-spoken lecture scripts from documents (via the KISSKI LLM).

- Upload a document, the AI produces a matching speaker text
- Download as Markdown

### Transcription

Transcribes audio and video files to text (via KISSKI Whisper).

- Task modes: transcription or translation
- Output formats: text, SRT, VTT
- Supports a wide range of audio/video formats

### Screencast creation

Automatically creates a screencast video from a PPTX presentation: translation, script generation, TTS, video rendering.

**Auto mode**: fully automated one-click run.

**Manual mode**: step-by-step with editing options:

1. Upload PPTX
2. Translation (with glossary support)
3. Optional user prompt for script tweaks
4. Review the translation (slide preview, upload corrected PPTX)
5. AI script generation
6. Edit the per-slide scripts
7. TTS settings (speed, pauses)
8. Video rendering
9. MP4 download

## Glossary

The glossary ensures that domain terms are translated consistently with the desired target-language equivalents, regardless of what the underlying translation API would return.

### Management

- Edited via the glossary tab in the frontend (German to English)
- Entries live only in the browser (no server storage, no database storage)
- On submit, entries are sent as JSON in the request body

### Implementation: token-replacement approach

The project does **not** use the native glossary feature of DeepL or any other API. Instead, a custom token-replacement approach works independently of the API:

1. **Before** translation: glossary terms in the source text are replaced with unique placeholders (`__GLOSSARY_0__`, `__GLOSSARY_1__`, ...)
2. The prepared text (with placeholders) is sent to the translation API. Placeholders pass through untouched.
3. **After** translation: placeholders are replaced with the defined target terms.

**Example:**

```
Input:           "Die Lehrveranstaltung beginnt pünktlich."
After step 1:    "Die __GLOSSARY_0__ beginnt pünktlich."
After DeepL:     "The __GLOSSARY_0__ starts on time."
Output:          "The Course starts on time."
```

Longer terms are replaced first to avoid overlaps.

### Where is the glossary applied?

| Tool | Glossary active | Notes |
|------|:---:|-------|
| Document translation (DOCX, PPTX, MD, TEX) | Yes | Token replacement via `GlossaryService` |
| Screencast translation (PPTX step) | Yes | Same logic as document translation |
| Transcription | No | Direct KISSKI Whisper call, no glossary |
| Text-to-Speech | No | ElevenLabs call, no glossary |
| Script generation | Yes | Glossary entries are injected as a terminology instruction into the LLM system prompt (no token replacement) |

## API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Login |
| `/auth/logout` | POST | Logout |
| `/auth/status` | GET | Check auth status |
| `/health` | GET | Health check |
| `/translate` | POST | Translate document (custom parser) |
| `/translate-document` | POST | Translate document (DeepL Document API) |
| `/tts` | POST | Text-to-Speech (document to MP3) |
| `/script` | POST | Script generation (document to speaker text) |
| `/transcription` | POST | Audio/video transcription |
| `/screencast` | POST | Screencast (auto mode) |
| `/screencast/translate` | POST | Screencast: translate PPTX, extract texts/images |
| `/screencast/extract-texts` | POST | Screencast: extract texts from PPTX |
| `/screencast/prepare` | POST | Screencast: PPTX to slide images |
| `/screencast/generate-scripts` | POST | Screencast: generate scripts |
| `/screencast/render` | POST | Screencast: render MP4 |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPL_API_KEY` | DeepL API key | - |
| `SOURCE_LANG` | Source language | `DE` |
| `TARGET_LANG` | Target language | `EN-US` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key (TTS) | - |
| `KISSKI_API_KEY` | KISSKI LLM API key (scripts, transcription) | - |
| `KISSKI_BASE_URL` | KISSKI API base URL | `https://chat-ai.academiccloud.de/v1` |
| `KISSKI_MODEL` | KISSKI LLM model | `qwen3-30b-a3b-instruct-2507` |
| `APP_PASSWORD` | Login password | `admin` |
| `SESSION_SECRET` | Secret for session tokens | - |
| `SESSION_MAX_AGE_SECONDS` | Session lifetime in seconds | `86400` |

## System dependencies (backend container)

- **FFmpeg**: video/audio processing (screencast, TTS pauses)
- **LibreOffice**: PPTX to PDF conversion (screencast)
- **poppler-utils**: PDF to PNG conversion (screencast)

These are installed automatically inside the Docker image.

## License

Apache License 2.0, Copyright 2026 Technische Hochschule Lübeck

Full text: see [LICENSE](LICENSE). Attribution: see [NOTICE](NOTICE). Lead developer and contributors: see [AUTHORS](AUTHORS).

### Third-party licenses

All third-party dependencies (Backend Python + Frontend npm) are aggregated
with full license texts in [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

Regenerate after dependency changes (requires running `kis-backend` container
and frontend `node_modules` installed):

```bash
python generate-licenses.py
```

The generator fails on any AGPL or strong-copyleft GPL dependency. LGPL is
allowed (dynamic-linking via PyPI/npm). Drift check via `--check` flag.
