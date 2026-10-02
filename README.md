# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self hosted teaching platform with AI assisted tools for course material and study support.
Developed at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.

## Features

- Document translation with glossary
- Slide decks from an outline: layouts, charts, images
- Screencasts from PPTX: script, speech, video, subtitles
- Podcasts from source material: script, voices, audio
- Live interpreter: two-way speech and text translation
- Transcription, text to speech, summaries, image generation
- Study assistant: modules, sources, chat with citations, flashcards, quiz, mindmaps, data tables, schedules, notes

## Stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind 4, next-intl (DE/EN)
- Backend: FastAPI, Python 3.11, Celery, Redis
- Data: PostgreSQL 16 with pgvector, S3 compatible storage
- System tools: FFmpeg, LibreOffice, poppler-utils

## Requirements

- Docker and Docker Compose v2
- Node.js 20+, only for the development setup below

## Run it locally

```bash
cp .env.example .env
docker compose up -d
```

Open `http://localhost:3000`.

- Login: `admin` / `adminpw` from `.env.example`, by user name or mail address.
- `AUTH_DISABLED=true` skips login, giving a `local` account every permission. Not a deployment
  mode, blocked by `PRODUCTION=true`.

## Development setup

For working on the code, the frontend runs from the Next.js dev server instead of the container:

```bash
./start-local.sh          # start-local.bat on Windows
cd frontend && npm install && npm run dev
```

The script leaves the frontend container out, so port 3000 stays free, and it adds Adminer
and Langfuse. The API docs are on `http://localhost:8000/docs`.

## AI providers

The repository ships no API keys. Providers are added at runtime under **Admin → AI**, and every
feature is routed to a model there. Any OpenAI compatible endpoint works, plus DeepL.

Speech and local models run outside the stack and are reached by base URL, for example Ollama at
`http://host.docker.internal:11434/v1`.

The study assistant needs a model with a large context window, at least 128k tokens. We run it
with 256k.

## License

Apache 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS) and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
