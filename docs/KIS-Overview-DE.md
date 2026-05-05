# KIS — KI-Plattform für Lehre und Studium

KIS ist eine KI-gestützte Plattform für Übersetzung, Medienproduktion und Lernunterstützung an Hochschulen. DSGVO-konform und self-hostable.

Entwickelt am Institut für Interaktive Systeme (ISy), Technische Hochschule Lübeck.

![Login-Bildschirm](images/01-login-desktop.png)

---

## Was kann KIS?

KIS bündelt zwei Bereiche unter einer Oberfläche:

1. **Medien-Werkzeuge** für Dozierende: Dokumente übersetzen, Vorlesungen vertonen, automatische Screencasts erzeugen.
2. **KI-Lernassistent** für Studierende: Arbeitsräume mit eigenen Quellen, Chat, Mindmaps, Karteikarten, Quiz, Stundenplan, Sprachtraining.

Alles läuft mit lokalen oder hochschulinternen LLMs. Keine US-Cloud in der Produktion.

### Startseite

Die Startseite zeigt anstehende Termine aus allen Modulen, dazu eine Tabelle aller eigenen Module mit Status, Quellenanzahl und Aktivierungs-Toggle.

![Startseite mit Modulen und nächsten Terminen](images/02-home-modules.png)

Die Tools-Sidebar links lässt sich einklappen — ein Klick auf das Sidebar-Icon und mehr Platz für den Hauptinhalt:

![Startseite mit eingeklappter Tools-Sidebar](images/02b-home-collapsed.png)

---

## Medien-Werkzeuge

Zugriff über die linke Tools-Sidebar — funktionieren ohne Modul, für Ad-hoc-Arbeit.

### Dokumentenübersetzung

KIS übersetzt DOCX, PPTX, MD, TEX und PDF unter Beibehaltung von Formatierung, Layout und Bildern. Quellsprache und Zielsprache werden gewählt; ein eigenes Glossar erzwingt einheitliche Fachbegriffe. Engine wahlweise DeepL (schnell) oder LLM-basiert.

![Übersetzungs-Tool](images/10-translate.png)

### Text in Sprache (TTS)

Texte und ganze Dokumente werden mit natürlich klingenden Stimmen vertont. Mehrere Anbieter (Kokoro, Thorsten), verschiedene Stimmen, Geschwindigkeit von 0,7x bis 1,2x.

![TTS-Tool](images/11-tts.png)

### Sprache in Text (Transkription)

Audio- und Videodateien werden per Whisper transkribiert. Ausgabe wahlweise als reiner Text oder als Untertitel (.srt / .vtt) mit Zeitstempeln.

![STT-Tool](images/12-stt.png)

### Bildgenerierung

Drei Modi: Text-zu-Bild, bestehendes Bild bearbeiten, Bild analysieren. Größen 1024×1024 oder 1280×720 für Folien.

![Bildgenerierung](images/13-image.png)

### Zusammenfassung

Lange Dokumente, Audios, Videos und Untertitel-Dateien (.srt/.vtt) werden auf das Wesentliche gebracht.

![Zusammenfassung](images/14-summarize.png)

### Glossar

Eigene Begriffslisten anlegen oder importieren. Werden bei Übersetzung und Screencast genutzt, damit Fachbegriffe konsistent bleiben.

![Glossar](images/16-glossary.png)

### Meine Jobs

Jeder Auftrag (Übersetzung, TTS, Bild, Screencast, …) landet in der Job-Übersicht mit Status, Bearbeitungsdauer, Download-Link und Aufbewahrungsfrist.

![Meine Jobs](images/18-jobs.png)

### Persönlicher Zeitplan

Termine aus allen Modulen werden in einer einzigen Timeline gebündelt. Quelle ist immer das jeweilige Modul; Klick führt direkt in den Arbeitsraum.

![Persönlicher Zeitplan](images/19-schedule.png)

---

## Screencast aus PPTX (Wizard)

Eine PowerPoint-Datei wird automatisch in ein vertontes Video umgewandelt. Der Wizard führt durch acht Schritte: Upload → Übersetzen → Prüfen → Anweisungen → Skripte → Einstellungen → Rendern → Fertig.

### Einstieg

![Screencast-Wizard Einstieg](images/15-screencast.png)

### Demo-Modus ohne eigene Datei

Ohne eigene PPTX kann jeder den Demo-Modus starten — der Wizard läuft mit einer fertigen Beispiel-Präsentation.

![Screencast-Demo Startseite](images/60-demo-step1-start.png)

### Schritt 3 — Übersetzung prüfen

Nach automatischem Upload und Übersetzung zeigt der Wizard alle übersetzten Folien als Vorschau-Raster. Die übersetzte PPTX kann heruntergeladen, manuell korrigiert und wieder hochgeladen werden.

![Schritt 3: Übersetzung prüfen](images/61-demo-step3-review.png)

### Schritt 4 — Anweisungen für die Skript-Erzeugung

Drei Wege zum Sprechertext: KI generiert die Skripte automatisch aus den Folieninhalten, manuell tippen oder als JSON importieren.

![Schritt 4: Anweisungen](images/62-demo-step4-instructions.png)

### Schritt 5 — Skripte überprüfen und anpassen

Pro Folie wird der generierte Sprechertext angezeigt — mit Wortzahl und Schätzung der Sprechzeit. Jedes Skript lässt sich neu generieren oder direkt im Editor anpassen.

![Schritt 5: Skripte](images/63-demo-step5-scripts.png)

### Schritt 6 — Einstellungen

TTS-Anbieter, Stimme, Geschwindigkeit, Pause zwischen Folien und Bildqualität. Unten eine Live-Schätzung von Folienanzahl, Wortzahl und TTS-Zeichenkontingent.

![Schritt 6: Einstellungen](images/64-demo-step6-settings.png)

### Schritt 8 — Fertiges Video

Das vertonte Video lässt sich direkt im Browser abspielen, als MP4 oder als ZIP (inkl. Skripte und übersetzter PPTX) herunterladen.

![Schritt 8: Fertiges Video](images/65-demo-step8-done.png)

---

## KI-Lernassistent (Workspaces)

Pro Vorlesung, Seminar oder Thema ein eigener Arbeitsraum. Drei-Panel-Layout: links die Quellen, mittig der Chat mit der KI „Hilde", rechts das Studio mit Lerntools, Glossar, Notizen, Statistik und Zeitplan.

![Workspace-Übersicht](images/20-workspace-overview.png)

### Chat mit eigenen Quellen (RAG)

PDFs, Folien, Audios, Videos und Webseiten werden als Quellen hochgeladen. Hilde antwortet **ausschließlich** auf Basis dieser Quellen und verlinkt jede Aussage mit konkreten Belegen — bei Videos als Zeitstempel, bei PDFs als Seitenzahl. Ein Klick auf einen Beleg öffnet den Original-Viewer an genau dieser Stelle.

### Video-Quellen mit Beleg-Sprung

Klick auf einen Zeitstempel-Chip im Chat öffnet das Video links und scrollt das Transkript automatisch an die Stelle. Transkript wahlweise nur Deutsch, nur Englisch oder beidsprachig parallel.

![Video-Quelle mit Zeitstempel-Beleg](images/32-video-citation.png)

### PDF-Viewer mit Text-Selection

Klick auf einen Seiten-Chip öffnet das PDF im integrierten Viewer. Text lässt sich direkt markieren — eine Aktions-Leiste erscheint mit Optionen wie Hervorhebung, Unterstreichung, Kommentar, Zitat-Suche und KI-Erklärung.

![PDF-Text markiert mit Aktions-Popup](images/51-pdf-selection.png)

### Mindmaps

Mindmaps werden automatisch aus den ausgewählten Quellen erzeugt. Jeder Knoten ist mit dem Quellbeleg verknüpft (Seite oder Zeitstempel). Im Panel-Modus integriert ins Studio:

![Mindmap im Studio-Panel](images/21-mindmap-panel.png)

Im **Vollbild-Modus** mit „Alle ausklappen" wird die komplette Hierarchie sichtbar — jeder Knoten klickbar, jeder Beleg verlinkt:

![Mindmap im Vollbild](images/22-mindmap-fullscreen.png)

### Karteikarten

Frage-Antwort-Karten mit Tipp-Funktion und Quellenbeleg pro Karte. Jede Karte zeigt unten, woher die Antwort stammt — Seite, Folie oder Zeitstempel.

![Karteikarten](images/24-flashcards.png)

### Quiz

Multiple-Choice-Aufgaben aus dem Quellmaterial. Vier Antworten, Tipp-Hinweis, Zeitstempel-Beleg. Statistik (richtig / falsch) wird im Studio mitgeführt.

![Quiz](images/25-quiz.png)

### Datentabelle

Strukturierte Übersichtstabellen aus mehreren Quellen — etwa Anforderungen, Termine, Definitionen — als kompakte Vergleichsmatrix.

![Datentabelle](images/26-datatable.png)

### Sprachtraining (Fachsprache)

Eigener Bereich für Fremdsprachen-Vokabel-Training auf Fachvokabular. Drei Modi:

- **Lernkarten:** Fachbegriff → Definition mit Übersetzung, Bewertung richtig/falsch, Spaced Repetition.

  ![Sprachtraining Lernkarten](images/23-language-flashcards.png)

- **Lückentext:** Begriffe in Kontext-Sätzen ergänzen.

  ![Lückentext](images/27-cloze.png)

- **Begriffe-Quiz:** Multiple-Choice auf Fachvokabular.

### Notizen

Eigene Notizen direkt am Workspace. Antworten aus dem Chat können mit einem Klick als Notiz gespeichert werden.

![Notizen](images/28-notes.png)

### Workspace-Glossar

KIS extrahiert automatisch Fachbegriffe inklusive englischer Übersetzung und Quellbeleg. Manuell ergänzbar.

![Workspace-Glossar](images/30-workspace-glossary.png)

### Lernstatistik

Aktivitäts-Heatmap (GitHub-Stil), aktive Tage, Anzahl Antworten, Quote richtig — pro Workspace.

![Lernstatistik](images/31-workspace-stats.png)

### Stundenplan & Aufgaben

Vorlesungspläne werden aus PDF oder DOCX automatisch erkannt: Termine mit Datum, Uhrzeit und Quellenseite landen direkt im Workspace-Zeitplan und in der zentralen Schedule-Ansicht. Extrahierte Termine lassen sich nachträglich bearbeiten, eigene Termine können jederzeit manuell hinzugefügt werden — Vorlesungen, Abgaben, Klausuren oder freie Notizen.

Damit funktioniert der Zeitplan auch als persönliche Todo-Liste pro Modul: Jeder Eintrag lässt sich als erledigt abhaken; abgehakte Termine verschwinden aus der Default-Ansicht und können bei Bedarf wieder eingeblendet werden.

![Workspace-Zeitplan](images/29-workspace-schedule.png)

---

## Responsive Design

KIS funktioniert auf Smartphone, Tablet und Desktop — das Drei-Panel-Layout passt sich der Bildschirmgröße an. Auf dem Tablet bleiben alle drei Panels nebeneinander, auf dem Smartphone klappt der Workspace zu Tab-Navigation: Quellen / Chat / Studio.

![Mobile Workspace Quellen](images/42-mobile-workspace.png) ![Mobile Workspace Chat](images/43-mobile-chat.png)

### Dunkler Modus

Komplettes Light/Dark-Theme über den Sonne/Mond-Button im Header.

![Dunkler Modus Startseite](images/46-darkmode-home.png)

![Dunkler Modus Workspace](images/47-darkmode-workspace.png)

---

## Hilde — die KI-Begleiterin

Hilde ist die Eulen-Maskotte, die durch den KI-Assistenten führt. Sie hat fünf Stimmungen (Idle, Denkt nach, Hat's gefunden, Verwirrt, Begrüßt), erscheint in verschiedenen Größen vom Avatar (32 px) bis zur Hero-Darstellung (320 px) und passt sich dem Chat-Kontext an. Im Admin-Bereich gibt es eine Spielwiese, in der jede Stimmung, Größe und das Verhalten im Chat-Kontext live ausprobiert werden können.

![Hilde-Spielwiese](images/70-hilde-playground.png)

---

## Technische Eckdaten

- **Frontend:** Next.js 15, React 19, TypeScript, Tailwind CSS 4
- **Backend:** FastAPI (Python 3.11), PostgreSQL 16 mit pgvector, Redis, Celery
- **KI-Anbindung:** OpenAI-kompatible LLM-Clients (KISSKI, THL myLab, lokale Modelle via Ollama), DeepL, Whisper, Kokoro/Thorsten TTS
- **Sprachen:** Deutsch und Englisch (UI und LLM-Ausgabe)
- **Auth:** LDAP, vorbereitet für SSO

**Self-hostable:** Komplettes Setup via Docker Compose, alle Daten bleiben auf der eigenen Infrastruktur.

**DSGVO-konform:** Verarbeitung über DSGVO-konforme LLM-Anbieter (KISSKI, THL myLab) oder vollständig lokal.

---

## Status

KIS ist im aktiven Einsatz und wird laufend weiterentwickelt. Quellcode öffentlich unter Apache 2.0.

---

## Kontakt

**Hamid Mergan**
Institut für Interaktive Systeme (ISy)
Technische Hochschule Lübeck
hamid.mergan@th-luebeck.de
