# KIS — AI Platform for Teaching and Learning

KIS is an AI-powered platform for translation, media production and learning support at universities. GDPR-compliant and self-hostable.

Developed at the Institute for Interactive Systems (ISy), Lübeck University of Applied Sciences.

![Login screen](images/01-login-desktop.png)

---

## What can KIS do?

KIS bundles two areas under one interface:

1. **Media tools** for lecturers: translate documents, narrate lectures, generate automatic screencasts.
2. **AI learning assistant** for students: workspaces with their own sources, chat, mind maps, flashcards, quizzes, schedule, language training.

Everything runs on local or campus-internal LLMs. No US cloud in production.

### Home page

The home page shows upcoming events from all modules, plus a table of all your modules with status, source count and activation toggle.

![Home page with modules and upcoming events](images/02-home-modules.png)

The Tools sidebar on the left can be collapsed — one click on the sidebar icon and you get more space for the main content:

![Home page with collapsed Tools sidebar](images/02b-home-collapsed.png)

---

## Media tools

Accessible via the left Tools sidebar — they work without a module, for ad-hoc work.

### Document translation

KIS translates DOCX, PPTX, MD, TEX and PDF while preserving formatting, layout and images. Source and target language can be chosen; a custom glossary enforces consistent terminology. Engine optionally DeepL (fast) or LLM-based.

![Translation tool](images/10-translate.png)

### Text to speech (TTS)

Texts and entire documents are narrated with natural-sounding voices. Multiple providers (Kokoro, Thorsten), various voices, speed from 0.7x to 1.2x.

![TTS tool](images/11-tts.png)

### Speech to text (transcription)

Audio and video files are transcribed via Whisper. Output as plain text or as subtitles (.srt / .vtt) with timestamps.

![STT tool](images/12-stt.png)

### Image generation

Three modes: text-to-image, edit existing image, analyze image. Sizes 1024×1024 or 1280×720 for slides.

![Image generation](images/13-image.png)

### Summarization

Long documents, audio files, videos and subtitle files (.srt/.vtt) are reduced to the essentials.

![Summarization](images/14-summarize.png)

### Glossary

Create or import your own term lists. Used during translation and screencast generation to keep technical terms consistent.

![Glossary](images/16-glossary.png)

### My jobs

Every job (translation, TTS, image, screencast, …) lands in the job overview with status, processing time, download link and retention period.

![My jobs](images/18-jobs.png)

### Personal schedule

Events from all modules are bundled into a single timeline. The source is always the respective module; one click takes you straight to the workspace.

![Personal schedule](images/19-schedule.png)

---

## Screencast from PPTX (wizard)

A PowerPoint file is automatically converted into a narrated video. The wizard guides you through eight steps: Upload → Translate → Review → Instructions → Scripts → Settings → Render → Done.

### Entry point

![Screencast wizard entry](images/15-screencast.png)

### Demo mode without your own file

Without your own PPTX, anyone can start the demo mode — the wizard runs with a ready-made example presentation.

![Screencast demo home](images/60-demo-step1-start.png)

### Step 3 — Review translation

After automatic upload and translation, the wizard shows all translated slides as a preview grid. The translated PPTX can be downloaded, manually corrected and re-uploaded.

![Step 3: Review translation](images/61-demo-step3-review.png)

### Step 4 — Instructions for script generation

Three ways to get the speaker text: AI generates the scripts automatically from slide content, type them manually, or import as JSON.

![Step 4: Instructions](images/62-demo-step4-instructions.png)

### Step 5 — Review and adjust scripts

Per slide, the generated speaker text is shown — with word count and an estimate of the speaking time. Each script can be regenerated or edited directly in the editor.

![Step 5: Scripts](images/63-demo-step5-scripts.png)

### Step 6 — Settings

TTS provider, voice, speed, pause between slides and image quality. At the bottom, a live estimate of slide count, word count and TTS character quota.

![Step 6: Settings](images/64-demo-step6-settings.png)

### Step 8 — Finished video

The narrated video can be played directly in the browser, downloaded as MP4 or as a ZIP (incl. scripts and translated PPTX).

![Step 8: Finished video](images/65-demo-step8-done.png)

---

## AI learning assistant (workspaces)

One workspace per lecture, seminar or topic. Three-panel layout: sources on the left, chat with the AI "Hilde" in the middle, the studio with learning tools, glossary, notes, statistics and schedule on the right.

![Workspace overview](images/20-workspace-overview.png)

### Chat with your own sources (RAG)

PDFs, slides, audio, video and web pages are uploaded as sources. Hilde answers **only** based on these sources and links every statement with concrete evidence — for videos as a timestamp, for PDFs as a page number. One click on a citation opens the original viewer at exactly that location.

### Video sources with citation jump

Clicking a timestamp chip in the chat opens the video on the left and automatically scrolls the transcript to that point. Transcript optionally German only, English only, or both languages in parallel.

![Video source with timestamp citation](images/32-video-citation.png)

### PDF viewer with text selection

Clicking a page chip opens the PDF in the integrated viewer. Text can be selected directly — an action bar appears with options like highlight, underline, comment, citation search and AI explanation.

![PDF text selected with action popup](images/51-pdf-selection.png)

### Mind maps

Mind maps are generated automatically from the selected sources. Each node is linked to its source citation (page or timestamp). In panel mode integrated into the studio:

![Mind map in the studio panel](images/21-mindmap-panel.png)

In **fullscreen mode** with "expand all", the entire hierarchy becomes visible — every node clickable, every citation linked:

![Mind map in fullscreen](images/22-mindmap-fullscreen.png)

### Flashcards

Question-answer cards with hint function and source citation per card. Each card shows at the bottom where the answer comes from — page, slide or timestamp.

![Flashcards](images/24-flashcards.png)

### Quiz

Multiple-choice questions from the source material. Four answers, hint, timestamp citation. Statistics (correct / wrong) are tracked in the studio.

![Quiz](images/25-quiz.png)

### Data table

Structured overview tables from multiple sources — for example requirements, dates, definitions — as a compact comparison matrix.

![Data table](images/26-datatable.png)

### Language training (technical vocabulary)

A dedicated area for foreign-language vocabulary training on technical terms. Three modes:

- **Flashcards:** technical term → definition with translation, correct/wrong rating, spaced repetition.

  ![Language training flashcards](images/23-language-flashcards.png)

- **Cloze test:** complete terms in context sentences.

  ![Cloze test](images/27-cloze.png)

- **Term quiz:** multiple choice on technical vocabulary.

### Notes

Your own notes directly in the workspace. Answers from the chat can be saved as a note with one click.

![Notes](images/28-notes.png)

### Workspace glossary

KIS automatically extracts technical terms including English translation and source citation. Can be extended manually.

![Workspace glossary](images/30-workspace-glossary.png)

### Learning statistics

Activity heatmap (GitHub style), active days, number of answers, correct rate — per workspace.

![Learning statistics](images/31-workspace-stats.png)

### Schedule & tasks

Lecture schedules are recognized automatically from PDF or DOCX: dates with day, time and source page land directly in the workspace schedule and in the central schedule view. Extracted dates can be edited afterwards, and your own dates can be added manually at any time — lectures, deadlines, exams or free notes.

This way the schedule also works as a personal todo list per module: every entry can be ticked off as done; checked-off entries disappear from the default view and can be shown again on demand.

![Workspace schedule](images/29-workspace-schedule.png)

---

## Responsive design

KIS works on smartphone, tablet and desktop — the three-panel layout adapts to the screen size. On a tablet all three panels stay side by side, on a smartphone the workspace collapses to tab navigation: Sources / Chat / Studio.

![Mobile workspace sources](images/42-mobile-workspace.png) ![Mobile workspace chat](images/43-mobile-chat.png)

### Dark mode

Complete light/dark theme via the sun/moon button in the header.

![Dark mode home page](images/46-darkmode-home.png)

![Dark mode workspace](images/47-darkmode-workspace.png)

---

## Hilde — the AI companion

Hilde is the owl mascot guiding you through the AI assistant. She has five moods (Idle, Thinking, Found it, Confused, Greeting), appears in various sizes from avatar (32 px) up to hero (320 px) and adapts to the chat context. In the admin area there is a playground where every mood, size and behavior in chat context can be tried out live.

![Hilde playground](images/70-hilde-playground.png)

---

## Technical specs

- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS 4
- **Backend:** FastAPI (Python 3.11), PostgreSQL 16 with pgvector, Redis, Celery
- **AI integration:** OpenAI-compatible LLM clients (KISSKI, THL myLab, local models via Ollama), DeepL, Whisper, Kokoro/Thorsten TTS
- **Languages:** German and English (UI and LLM output)
- **Auth:** LDAP, prepared for SSO

**Self-hostable:** complete setup via Docker Compose, all data stays on your own infrastructure.

**GDPR-compliant:** processing via GDPR-compliant LLM providers (KISSKI, THL myLab) or fully local.

---

## Status

KIS is in active use and is continuously being developed. Source code public under Apache 2.0.

---

## Contact

**Hamid Mergan**
Institute for Interactive Systems (ISy)
Lübeck University of Applied Sciences
hamid.mergan@th-luebeck.de
