# KIS — KI-Plattform für Lehre und Studium

KIS ist eine KI-gestützte Plattform für Übersetzung, Medienproduktion und Lernunterstützung an Hochschulen. DSGVO-konform und self-hostable.

Entwickelt am Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.

---

## Was kann KIS?

KIS bündelt zwei Bereiche:

1. **Medien-Werkzeuge** für Dozierende: Dokumente übersetzen, Vorlesungen vertonen, automatische Screencasts erzeugen
2. **KI-Lernassistent** für Studierende: Arbeitsräume, Chat mit eigenen Quellen, Mindmaps, Karteikarten, Sprachtraining

Alles in einer Oberfläche, mit lokalen oder hochschulinternen LLMs.

---

## Medien-Werkzeuge

### Dokumentenübersetzung

Übersetzt DOCX, PPTX, MD, TEX und PDF unter Beibehaltung der Formatierung. Eigenes Glossar für fachspezifische Begriffe.

> *Screenshot: Übersetzungs-Oberfläche*

### Automatischer Screencast aus PPTX

Eine PowerPoint-Datei wird automatisch in ein vertontes Video umgewandelt: Übersetzung der Folien, Erzeugung des Sprechertexts, Text-to-Speech, Video-Rendering.

> *Screenshot: Screencast-Generator*

### Text-to-Speech und Transkription

Vertonung von Texten mit verschiedenen Stimmen. Transkription von Audio- und Videodateien per Whisper.

> *Screenshot: TTS-Interface*

### Bildgenerierung und Zusammenfassung

KI-Bilder zu Lehrinhalten erzeugen, lange Texte automatisch zusammenfassen.

---

## KI-Lernassistent

### Arbeitsräume (Workspaces)

Pro Vorlesung oder Thema ein eigener Arbeitsraum. Quellen, Notizen, Mindmaps und Übungen werden gebündelt.

> *Screenshot: Workspace-Übersicht*

### Chat mit eigenen Quellen (RAG)

PDF, Audio, Video oder Webseiten hochladen, anschließend Fragen dazu stellen. Antworten verweisen auf die Originalstellen.

> *Screenshot: Chat mit Quellen*

### Mindmaps

Themen visuell strukturieren, automatisch aus Quellen generierbar.

> *Screenshot: Mindmap*

### Übungen, Karteikarten, Multiple Choice

Aus Quellmaterial werden automatisch Übungsaufgaben, Lernkarten und Multiple-Choice-Fragen erzeugt.

> *Screenshot: Lernkarten*

### Stundenplan-Extraktion

Vorlesungspläne aus PDF oder DOCX werden erkannt und in den persönlichen Kalender übernommen.

> *Screenshot: Stundenplan*

### Sprachtraining

Karten zum Sprachenlernen, fokussiert auf Fachvokabular.

> *Screenshot: Sprachtraining*

---

## Technische Eckdaten

- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS 4
- **Backend:** FastAPI (Python 3.11), PostgreSQL 16 mit pgvector, Redis, Celery
- **KI-Anbindung:** OpenAI-kompatible LLM-Clients (KISSKI, myLab, lokale Modelle), DeepL, Whisper
- **Sprachen:** Deutsch und Englisch (UI und LLM-Ausgabe)

**Self-hostable:** Komplettes Setup via Docker Compose, alle Daten bleiben auf der eigenen Infrastruktur. Keine Abhängigkeit von US-Cloud-Diensten in der Produktion.

**DSGVO-konform:** Verarbeitung über DSGVO-konforme LLM-Anbieter (z. B. KISSKI, GWDG-myLab) oder vollständig lokal.

---

## Status

KIS ist im aktiven Einsatz und wird laufend weiterentwickelt. Quellcode öffentlich unter Apache 2.0.

---

## Kontakt

**Hamid Mergan**
Institut für Interaktive Systeme (ISy)
Technische Hochschule Lübeck
hamid.mergan@th-luebeck.de
