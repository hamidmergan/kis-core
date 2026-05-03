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
- Chat with sources (RAG)
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
- DeepL, OpenAI-compatible LLM clients (KISSKI, myLab, Ollama)
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

## License

Apache License 2.0, Copyright 2026 Technische Hochschule Lübeck.
See [LICENSE](LICENSE), [NOTICE](NOTICE), [AUTHORS](AUTHORS), and [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

Regenerate third-party notices after dependency changes:

```bash
python generate-licenses.py
```
