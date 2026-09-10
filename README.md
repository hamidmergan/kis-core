# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A self hosted teaching platform with AI assisted tools for course material and study support.
Developed at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.

## Features

- Document translation (DOCX, PPTX, MD, TEX, PDF) with glossary
- Screencasts from PPTX: script, speech, video, subtitles
- Transcription, text to speech, summaries, image generation
- Study assistant: modules, sources (PDF, DOCX, PPTX, audio, video), chat with citations, mindmaps, schedules, notes
- Language training: flashcards, grammar and vocabulary exercises, quiz, placement test

## Stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind 4, next-intl (DE/EN)
- Backend: FastAPI, Python 3.11, Celery, Redis
- Data: PostgreSQL 16 with pgvector, S3 compatible storage
- System tools: FFmpeg, LibreOffice, poppler-utils

## Requirements

- Docker and Docker Compose v2
- Node.js 20+, only for the development setup below

## Run it locally

The same two commands on macOS, Linux and Windows:

```bash
cp .env.example .env
docker compose up -d
```

Then open `http://localhost:3000`. The defaults in `.env.example` already point at the containers in
this stack, so nothing has to be filled in for a local run. The first start builds the images, which
takes a few minutes.

Log in as `admin` with the password `adminpw`, both from `.env.example`. The login field takes
either that user name or the mail address next to it, told apart by the `@`. Everybody else gets in
through an invitation link or an access code, both made under **Admin → Nutzer**.

`ADMIN_USERNAME`, `ADMIN_EMAIL` and `ADMIN_PASSWORD` are written onto the admin account on every
start, so changing one of them and recreating the container is how you rename the admin or reset
its password. Note that `docker restart` is not enough, it keeps the environment the container was
built with. Change `ADMIN_PASSWORD` before any real use, a production install refuses to start
while it is still the example value.

`AUTH_DISABLED=true` drops the login screen entirely. Startup creates an account named `local` and
hands it every permission, so maintenance mode no longer applies. Useful for a quick look at the
app, unusable as a deployment: with `PRODUCTION=true` the backend refuses to start while this is
set.

Everything is published to `127.0.0.1` only, nothing is reachable from the network. A server
deployment is a different setup and uses `docker-compose.prod.yml`, which expects nginx, a domain and
TLS certificates.

## Development setup

For working on the code, the frontend runs from the Next.js dev server instead of the container:

```bash
./start-local.sh          # start-local.bat on Windows
cd frontend && npm install && npm run dev
```

The script leaves the frontend container out, so port 3000 stays free, and it adds Adminer
and Langfuse. The API docs are on `http://localhost:8000/docs`.

### Modules

`MODULES` in `.env` selects the halves: `aia,tools` (default), `aia`, or `tools`. A disabled half is
not hidden but gone, its routes answer 404 and its Celery worker does not start. Changing the value
needs a restart.

`MODULES=aia` drops the global glossary. `MODULES=tools` drops the language trainer, flashcards and
grammar exercises, and leaves the built in `user` role without permissions, so students need a custom
role.

## AI providers

The repository ships no API keys. Providers are added at runtime under **Admin → KI**, and every
feature is routed to a model there. Any OpenAI compatible endpoint works, plus DeepL and Docling.

Speech and local models run outside the stack and are reached by base URL, for example Ollama at
`http://host.docker.internal:11434/v1`.

The study assistant needs a model with a large context window. We run it with about 128k tokens.

## License

Apache 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS) and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

Regenerate the notices after dependency changes with `python generate-licenses.py`.
