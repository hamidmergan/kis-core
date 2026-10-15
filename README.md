# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self hosted teaching platform with AI assisted tools for course material and study support.
Developed at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.

Runs entirely on your own infrastructure. No data leaves it unless you configure an external
provider.

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

For working on the code, the frontend runs from the Next.js dev server instead of the container.
In `.env`, swap the two `COMPOSE_` lines for the development lines below them, then:

```bash
docker compose up -d      # add --build after changing a Dockerfile or requirements
cd frontend && npm install && npm run dev
```

This leaves the frontend container out, so port 3000 stays free, reloads the backend on every
change and adds Adminer and Langfuse. The API docs are on `http://localhost:8000/docs`.

If the stack ran in the normal setup before, remove its frontend container once, so port 3000 is free:

```bash
docker compose rm -sf frontend
```

## AI providers

The repository ships no API keys. Providers are added at runtime under **Admin → AI**, and every
feature is routed to a model there. Any OpenAI compatible endpoint works, plus DeepL.

Speech and local models run outside the stack and are reached by base URL, for example Ollama at
`http://host.docker.internal:11434/v1`.

The study assistant works best with a large context window, we run it with 128k tokens. A smaller
model works too, KIS measures its window and sizes the context to fit.

### Study assistant with Ollama

The study assistant also runs on local models. Tested only on a MacBook Pro M5 Max with 64 GB,
using `gemma4:31b-mlx` for chat and `qwen3-embedding:4b` for embedding. Smaller chat models often
claimed the answer was not in the sources. A chat answer took 9 to 34 seconds.

## License

Apache 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS) and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
