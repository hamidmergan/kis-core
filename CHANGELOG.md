# Changelog

## [Unreleased]

### Geändert
- Startseite ist eine Kachel-Übersicht: der KI-Assistent und jedes Werkzeug als Kachel mit Kurztext, ganze Kachel ist der Link. Wer nur ein Ziel hat, landet direkt dort
- Modulliste liegt unter `/workspace`, Einladungslinks zeigen dorthin, alte Links auf `/?code=` leiten weiter
- Begrüßung auf der Modulliste nur noch für wen direkt dort landet

### Entfernt
- Werkzeugleiste links und der Rundgang durch die Werkzeuge, die Kacheln erklären jedes Werkzeug selbst. Spalte `tools_tour_seen_at` und `POST /api/me/tools-tour-seen` sind weg
