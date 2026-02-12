# KIS-THL

Webbasierter Übersetzungsservice für Dokumente der TH Lübeck. Übersetzt DOCX, PPTX, MD, TEX und PDF automatisch von Deutsch nach Englisch – mit Glossar für konsistente Fachbegriffe.

## Architektur

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS (Port 3000)
- **Backend**: FastAPI, DeepL API, python-docx, python-pptx (Port 8000)

## Quick Start

```bash
cp env.example .env   # .env anpassen (DEEPL_API_KEY, APP_PASSWORD, SESSION_SECRET)
docker-compose up -d --build
```

- Frontend: `http://localhost:3000`
- API-Docs: `http://localhost:8000/docs`

Stoppen: `docker-compose down`

## Unterstützte Formate

| Format | Methode | Hinweis |
|--------|---------|---------|
| `.docx` | Eigener Parser | Layout-Erhalt |
| `.pptx` | Eigener Parser | inkl. Footer, Notizen, Master |
| `.md` | Eigener Parser | Code-Blöcke bleiben unverändert |
| `.tex` | Eigener Parser | Mathematik/Verbatim bleiben unverändert |
| `.pdf` | DeepL Document API | Einschränkungen bei Formeln/komplexen Layouts |

## Glossar

- Verwaltung über den Glossar-Tab im Frontend
- Einträge leben nur im Browser-Tab (kein Server-Speicher)
- Wird bei jeder Übersetzung automatisch mitgesendet

## Konfiguration

| Variable | Beschreibung | Standard |
|----------|-------------|----------|
| `DEEPL_API_KEY` | DeepL API Key | – |
| `SOURCE_LANG` | Quellsprache | `DE` |
| `TARGET_LANG` | Zielsprache | `EN-US` |
| `APP_PASSWORD` | Login-Passwort | `admin` |
| `SESSION_SECRET` | Secret für Session-Tokens | – |
| `SESSION_MAX_AGE_SECONDS` | Session-Dauer | `86400` |
| `PRODUCTION` | Produktionsmodus | `false` |
