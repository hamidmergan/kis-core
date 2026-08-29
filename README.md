# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

AI platform for teaching at TH Lübeck: document translation, screencasts, transcription and an AI study assistant.

> Built by **Hamid Mergan**, Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.
> Contact: hamid.mergan@th-luebeck.de

## Features

- Document translation (DOCX, PPTX, MD, TEX, PDF) with glossary
- Screencasts from PPTX (script, speech, video, subtitles)
- Transcription, text to speech, summaries, image generation
- Study assistant: modules, sources (PDF, audio, video, web), chat with citations, mindmaps, schedules, notes
- Language training: flashcards, grammar and vocabulary exercises, quiz, placement

## Stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind 4, next-intl (DE/EN)
- Backend: FastAPI, Python 3.11, Celery, Redis
- Data: PostgreSQL 16 with pgvector, S3 compatible storage
- Login: LDAP, plus invite links
- System tools: FFmpeg, LibreOffice, poppler-utils

## Requirements

- Docker and Docker Compose v2
- Node.js 20+ for the frontend dev server

## Quick start

```bash
cp .env.example .env      # fill in the values
./start-local.sh          # start-local.bat on Windows

cd frontend && npm install && npm run dev
```

Frontend: http://localhost:3000
API docs: http://localhost:8000/docs

### Modules

`MODULES` in `.env` decides which halves this installation has. `aia,tools` is the
default and keeps everything. `MODULES=aia` ships only the AI assistant, `MODULES=tools`
only the global tools. Disabled routes are not mounted at all, so they answer 404 rather
than 403, and the Celery worker of the disabled half does not start.

`MODULES=tools` also removes the language trainer, flashcards and grammar exercises,
because all of them belong to the assistant. `MODULES=aia` removes the global glossary,
the assistant keeps its own.

## AI providers

No API keys in `.env`. Log in as admin, add the providers under **Admin → KI** and route every feature to a model there. Any OpenAI compatible endpoint works, plus DeepL and Docling.

Speech and local models run outside the stack and are reached by base URL, for example Kokoro at `http://host.docker.internal:8880/v1` or Ollama at `http://host.docker.internal:11434/v1` (start Ollama with `OLLAMA_HOST=0.0.0.0:11434`).

For chat, models from about 25B upward work well. A thinking mode costs time without better answers.

## Tests

```bash
make test        # backend and frontend unit tests
make test-all    # plus E2E
```

## License

Apache 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS), [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

Regenerate notices after dependency changes: `python generate-licenses.py`
