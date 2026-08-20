# KIS

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

AI-powered media and learning platform for TH Lübeck. Translates documents, generates lecture screencasts, transcribes audio/video, and provides an AI study assistant with workspaces, mindmaps, schedules, and language training.

> Built by **Hamid Mergan** at Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.
> Contact: hamid.mergan@th-luebeck.de

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
- Chat with sources (RAG) — answers carry **chunk-grounded citations**: the model cites the exact source chunk it used, verified, resolved to the real PDF page / media timestamp + in-text highlight
- Mindmaps, exercises, flashcards, multiple-choice
- Schedule extraction from documents
- Language training cards
- Notes and data tables

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
- Celery + Celery Beat
- DeepL, OpenAI-compatible LLM clients (myLab, Ollama)
- Kokoro TTS
- S3-compatible object storage

**System dependencies**
- FFmpeg (audio/video)
- LibreOffice (PPTX → PDF)
- poppler-utils (PDF → PNG)

---

## Prerequisites

- Docker and Docker Compose v2
- Node.js 20+ (for frontend dev)

---

## Quick Start

```bash
git clone <repo-url> kis
cd kis
cp .env.example .env       # fill in values — see comments in the file

# 1. Start full local dev stack
start-local.bat            # Windows
./start-local.sh           # Linux/macOS

# 2. Start frontend dev server (separate terminal)
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000
API docs: http://localhost:8000/docs

---

## Local models (Ollama)

KIS works with any OpenAI-compatible LLM endpoint, including a locally hosted
[Ollama](https://ollama.com). Ollama always runs **outside** the KIS stack — it
is never shipped as a container; you host it yourself and point KIS at it via
**Admin → AI Settings** (`openai_compat` protocol, no API key for local
endpoints).

> **One gotcha:** when KIS runs in Docker and Ollama runs natively on the same
> machine, start Ollama with `OLLAMA_HOST=0.0.0.0:11434` so the container can
> reach it, and use the base URL `http://host.docker.internal:11434/v1`.

Full walkthrough: [docs/ollama-setup.md](docs/ollama-setup.md).

### Citations & model tier

In RAG chat the model cites the **exact source chunk** it used (it copies the chunk's
`id` from the context). KIS then verifies that claim against the chunk's text and derives
the real PDF page / media timestamp + highlight — it never trusts a page the model merely
guesses. A claim that does not actually sit in the named chunk is dropped (a missing
source is preferred over a wrong one).

This needs a model that can reliably copy the chunk `id`:

- **Tested & working:** mid / large tiers (e.g. hosted myLab models).
- **Not yet validated:** the small tier (8B / 32k context) may emit chunk ids
  unreliably. When it does, KIS falls back to deterministic lexical grounding — still
  safe, just less complete. Per-tier validation is pending.

---

## License

Apache License 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS), and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

Regenerate third-party notices after dependency changes:

```bash
python generate-licenses.py
```
