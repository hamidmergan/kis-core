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

The study assistant works best with a large context window, we run it with 256k tokens. A smaller
model works too, KIS measures its window and sizes the context to fit.

### Fully local with Ollama

KIS also runs without any cloud provider, with every model on your own machine. It is slower
than a server GPU and needs a strong computer:

| | Recommended |
|---|---|
| Mac | Apple Silicon Pro/Max with 64 GB memory |
| Windows / Linux | NVIDIA GPU with 24–32 GB (RTX 4090/5090) and 32 GB memory |

Measured on an M5 Max with 64 GB: a chat answer takes 10 to 70 seconds, a mind map several
minutes. Smaller models answer faster but do not yet follow the study assistant's answer format
reliably.

1. Start Ollama so the containers can reach it, and fetch the models:

   ```bash
   ./start-ollama.sh
   ```

   On a Mac use the Ollama download from ollama.com, not Homebrew. The Homebrew build lacks
   structured output, which KIS needs.

   The script lets Ollama listen on every network interface, otherwise the containers cannot
   reach it. Ollama has no login, so anyone on the same network can use your models. Run it
   only on a trusted network with the firewall on.

2. Under **Admin → AI** add a provider with the base URL `http://host.docker.internal:11434/v1`
   and no API key.
3. Route chat, transcript translation and document translation to `gemma4:31b-mlx` (Mac) or
   `gemma4:31b` (NVIDIA), and embedding to `qwen3-embedding:4b`.
KIS reads the context window from Ollama when the route is saved, then sizes its context and
splits large mind maps into smaller steps to fit the model. After changing `OLLAMA_CONTEXT_LENGTH`,
clear the window field of the model under **Admin → AI** so KIS measures again.

Changing the embedding model later means the sources have to be indexed again.

## License

Apache 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS) and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
