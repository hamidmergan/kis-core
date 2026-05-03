# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)

AI-powered media and learning platform for TH Lübeck. Translates documents, generates lecture screencasts, transcribes audio/video, and provides an AI study assistant with workspaces, mindmaps, schedules, and language training.

> Built by **Hamid Mergan** at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.
> Contact: hamid.mergan@th-luebeck.de

---

## Table of Contents

- [Features](#features)
- [Stack](#stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Development](#development)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Internationalization](#internationalization)
- [Project Status](#project-status)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Features

**Media tools**
- Document translation (DOCX, PPTX, MD, TEX, PDF) with custom glossary
- Text-to-speech (Kokoro, TH Lübeck myLab/Coqui)
- Transcription (Whisper)
- Image generation
- AI summarization
- Automatic screencast creation from PPTX (translation → script → TTS → video)

**AI study assistant**
- Workspaces per course or topic
- Source ingestion (PDF, audio, video, web)
- Chat with sources (RAG)
- Mindmaps, exercises, flashcards, multiple-choice
- Schedule extraction from documents
- Language training cards
- Notes and data tables

**Admin**
- Provider management (LLM, embedding, TTS, OCR slots)
- Quota and rate limiting
- Usage statistics
- Maintenance mode

---

## Stack

**Frontend**
- Next.js 15, React 19, TypeScript
- Tailwind CSS 4
- next-intl (DE/EN)
- Phosphor icons, react-markdown, mind-elixir, embedpdf

**Backend**
- FastAPI, Python 3.11
- PostgreSQL 16 + pgvector (RAG embeddings)
- Redis (Celery broker)
- Celery (3 worker queues: `screencast`, `tts/general`, `aia`) + Celery Beat
- DeepL, OpenAI-compatible LLM clients (KISSKI, myLab, Ollama)
- Kokoro TTS
- Langfuse LLM observability (dev/local only)
- S3-compatible storage (MinIO local, Hetzner Object Storage prod)

**System dependencies (in container)**
- FFmpeg (audio/video)
- LibreOffice (PPTX → PDF)
- poppler-utils (PDF → PNG)

---

## Prerequisites

- Docker and Docker Compose v2
- Node.js 20+ (for frontend dev)
- ~10 GB free disk for Docker images and storage volume

---

## Quick Start

```bash
git clone <repo-url> kis
cd kis
cp .env.example .env       # fill in API keys, see Configuration
docker compose up -d --build
```

Frontend: http://localhost:3000
API docs: http://localhost:8000/docs

Stop everything: `docker compose down`

---

## Development

Backend runs in Docker with hot reload (Python source mounted read-only). Frontend runs locally with Next.js dev server for instant HMR.

```bash
# 1. Start backend stack (Postgres, Redis, Celery, LDAP, FastAPI)
docker compose up -d

# 2. Start frontend dev server
cd frontend
npm install
npm run dev    # http://localhost:3000
```

**Useful commands**

```bash
docker compose logs -f backend            # backend logs
docker compose logs -f celery-worker-aia  # worker logs
docker compose restart backend            # restart after dependency change
npm run check:i18n                        # verify DE/EN key parity
npm run lint
```

Optional profiles:

```bash
docker compose --profile kokoro up -d     # local Kokoro TTS server
docker compose --profile presenton up -d  # AI presentation generator
```

---

## Configuration

All config is in `.env` (copy from `.env.example`). Provider keys are managed in the admin panel after first login, not via env vars.

| Variable | Description |
|---|---|
| `ADMIN_EMAIL` | Auto-whitelisted admin on first start |
| `SESSION_SECRET` | Random string, required |
| `POSTGRES_PASSWORD` | Database password, change in production |
| `S3_*` | Object storage (MinIO local, S3-compatible in prod) |
| `DEEPL_API_KEY` | DeepL translation |
| `PRIMARY_PROVIDER_API_KEY` | Primary LLM provider (default: KISSKI/Academic Cloud) |
| `FALLBACK_PROVIDER_BASE_URL` | Fallback LLM/Whisper (default: TH Lübeck myLab) |
| `LOCAL_PROVIDER_BASE_URL` | Local LLM (Ollama) |
| `LDAP_*` | LDAP server config (TH Lübeck or local sim) |
| `LANGFUSE_*` | LLM observability (dev/local only, optional) |
| `TRANSLATION_LANGUAGES` | Comma-separated language codes |

See `.env.example` for the full list with defaults.

---

## Authentication

Login via LDAP. A local OpenLDAP container is bundled for development with seeded test users (`docker/ldap/seed.ldif`). Integration with the TH Lübeck LDAP server is planned once the project moves to TH infrastructure.

Sessions are cookie-based, signed with `SESSION_SECRET`. Maintenance mode keeps `/admin` and `/auth` reachable so the admin can toggle it off.

---

## Internationalization

Hybrid German/English with German as the default.

- **Frontend**: `next-intl`, messages in `frontend/messages/{de,en}.json`. Both files must stay in sync. Run `npm run check:i18n` before committing.
- **Backend**: `Accept-Language` header drives translated `HTTPException` details and tool labels via `backend/src/i18n.py`. LLM prompts are always English; output language is controlled by `target_language` ("German" / "English").

User-facing strings only. Internal identifiers, file paths, comments, and database columns are English.

---

## Project Status

Active development. Currently hosted on Hetzner; migration to TH Lübeck infrastructure planned. Used internally at TH Lübeck.

---

## License

Apache License 2.0, Copyright 2026 Technische Hochschule Lübeck.

- Full text: [LICENSE](LICENSE)
- Attribution: [NOTICE](NOTICE)
- Contributors: [AUTHORS](AUTHORS)
- Third-party licenses (Python + npm, aggregated): [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)

Regenerate third-party notices after dependency changes:

```bash
python generate-licenses.py
```

The generator fails on AGPL or strong-copyleft GPL dependencies. LGPL is allowed via dynamic linking through PyPI/npm.

---

## Acknowledgments

- **GWDG / KISSKI** (Academic Cloud) — primary LLM and embeddings
- **TH Lübeck myLab** — Whisper, OCR, image, embeddings via internal infrastructure
- **DeepL** — document translation
- **Langfuse** — LLM observability (dev/local only)
