# KIS-THL

Webbasierter Übersetzungsservice für Dokumente der TH Lübeck. Übersetzt DOCX, PPTX, MD, TEX und PDF automatisch von Deutsch nach Englisch – mit Glossar für konsistente Fachbegriffe.

## Architektur

```
┌──────────────┐  Next.js Rewrites  ┌──────────────┐
│   Frontend   │ ─────────────────► │   Backend    │
│  (Next.js)   │  /auth, /translate │  (FastAPI)   │
│  Port 3000   │                    │  Port 8000   │
└──────────────┘                    └──────────────┘
                                          │
                                     DeepL API
```

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS – proxied API-Calls via Rewrites
- **Backend**: FastAPI, DeepL API, python-docx, python-pptx
- **Kein eigener Nginx** – auf dem Server übernimmt der bestehende Host-Nginx das Routing

## Installation & Start (Docker)

### 1. Vorbereitung

```bash
cp env.example .env
```

`.env` anpassen:

```env
DEEPL_API_KEY=dein_deepl_key
APP_PASSWORD=dein_passwort
SESSION_SECRET=zufaelliger_string
```

### 2. Starten

```bash
docker-compose up -d --build
```

### 3. Zugriff

| URL | Beschreibung |
|-----|-------------|
| `http://localhost:3000` | Frontend (Login → Upload → Download) |
| `http://localhost:8000/docs` | Swagger API-Dokumentation |
| `http://localhost:8000/health` | Health Check |

### 4. Stoppen

```bash
docker-compose down
```

## Deployment

Der bestehende Host-Nginx leitet alles an das Frontend weiter. Das Frontend proxied API-Calls intern per Docker Bridge-Networking an den Backend-Container.

```nginx
# /etc/nginx/sites-enabled/kis-thl.de
location / {
    proxy_pass http://localhost:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 200M;
    proxy_read_timeout 300s;
}
```

- Host-Nginx → Frontend (`:3000`) → Next.js Rewrites → Backend (`:8000` via Container-Name)
- Kein separater Nginx-Container nötig

## Features

- **Dokumentübersetzung** (DE → EN) mit Layout-Erhalt (DOCX, PPTX, MD, TEX, PDF)
- **Glossar** – Konsistente Übersetzung von Fachbegriffen (nur im Browser-Tab, kein Server-Speicher)
- **Dateinamen-Übersetzung** – Dateien werden mit übersetztem Namen heruntergeladen
- **Passwort-Login** mit Session-Cookies

## Unterstützte Formate

### POST /translate (eigene Parser)

| Format | Beschreibung |
|--------|-------------|
| `.docx` | Word-Dokumente mit Layout-Erhalt |
| `.pptx` | PowerPoint mit Layout-Erhalt (inkl. Footer, Notizen, Master) |
| `.md` | Markdown (Code-Blöcke bleiben unverändert) |
| `.tex` | LaTeX (Mathematik, Verbatim-Blöcke bleiben unverändert) |

### POST /translate-document (DeepL Document API)

| Format | Beschreibung |
|--------|-------------|
| `.docx` | Word via DeepL Document API |
| `.pptx` | PowerPoint via DeepL Document API |
| `.pdf` | PDF via DeepL Document API (mit Einschränkungen) |

### PDF-Einschränkungen

Die DeepL Document API hat bei PDFs Limitationen:
- Formeln/Mathematik werden oft nicht korrekt erkannt
- Komplexe Layouts können Probleme verursachen
- Text in Bildern wird nicht übersetzt

**Empfehlung:** Wenn möglich die Quelldatei (DOCX/PPTX) statt PDF verwenden.

## Glossar

Das Glossar stellt sicher, dass bestimmte Begriffe immer gleich übersetzt werden (z.B. "Technische Hochschule" → "University of Applied Sciences").

- Verwaltung über den **Glossar-Tab** im Frontend
- Einträge leben nur im Browser-Tab – beim Schließen sind sie weg
- Glossar-Einträge werden bei jeder Übersetzung automatisch mitgesendet
- Kein Server-Speicher, keine Datei, keine Datenbank

## Konfiguration (Umgebungsvariablen)

| Variable | Beschreibung | Standard |
|----------|-------------|----------|
| `DEEPL_API_KEY` | DeepL API Key | – |
| `SOURCE_LANG` | Quellsprache | `DE` |
| `TARGET_LANG` | Zielsprache | `EN-US` |
| `APP_PASSWORD` | Login-Passwort | `admin` |
| `SESSION_SECRET` | Secret für Session-Tokens | – |
| `SESSION_MAX_AGE_SECONDS` | Session-Dauer | `86400` (24h) |
| `PRODUCTION` | Produktionsmodus (Docs aus, Cookies secure) | `false` |

## Projektstruktur

```
kis-thl/
├── docker-compose.yml
├── env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── app.py              # FastAPI App
│       ├── config.py           # Umgebungsvariablen
│       ├── routes/
│       │   ├── auth.py         # Login/Logout/Status
│       │   ├── health.py       # Health Check
│       │   └── translate.py    # Übersetzungs-Endpoints
│       ├── services/
│       │   ├── deepl_client.py # DeepL Wrapper
│       │   ├── glossary.py     # Glossar-Logik (per-Request)
│       │   ├── session.py      # Session-Store (In-Memory)
│       │   └── translation.py  # Übersetzungs-Service
│       └── translators/
│           ├── docx.py         # DOCX Parser
│           ├── pptx.py         # PPTX Parser
│           ├── markdown.py     # Markdown Parser
│           ├── latex.py        # LaTeX Parser
│           └── document_api.py # DeepL Document API
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts          # API Rewrites → Backend
    └── src/
        ├── app/
        │   ├── page.tsx        # Hauptseite (Upload + Glossar)
        │   ├── login/          # Login-Seite
        │   ├── impressum/      # Impressum
        │   └── datenschutz/    # Datenschutzerklärung
        ├── components/
        │   ├── Header.tsx      # Header & Logout
        │   ├── FileUpload.tsx  # Drag & Drop Upload
        │   ├── GlossaryPanel.tsx # Glossar-Verwaltung
        │   └── TranslationStatus.tsx
        └── lib/
            ├── api.ts          # API Client
            └── auth.ts         # Auth Helpers
```
