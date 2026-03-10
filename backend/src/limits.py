# ─────────────────────────────────────────────────────────────────────────────
# limits.py — Zentrale Konfigurationsdatei für alle anpassbaren Limits
#
# Hier alle Werte ändern die Limits, Timeouts oder Quotas betreffen.
# Alle anderen Module importieren von hier.
# ─────────────────────────────────────────────────────────────────────────────

# ─── Quota: Tool-Limits pro User ──────────────────────────────────────────────
# limit:        max. Anfragen pro Zeitfenster
# window_hours: Stunden bis Reset (startet wenn Limit erstmals erreicht wird)
# label:        Anzeigename für Admin-UI und Fehlermeldungen
QUOTA_DEFAULTS: dict[str, dict] = {
    "tts":            {"limit": 30, "window_hours": 4, "label": "Text-to-Speech"},
    "summary":        {"limit": 30, "window_hours": 4, "label": "Zusammenfassung"},
    "translate":      {"limit": 30, "window_hours": 4, "label": "Dokumentenübersetzung"},
    "transcription":  {"limit": 30, "window_hours": 4, "label": "Transkription"},
    "image_generate": {"limit": 30, "window_hours": 4, "label": "Bild-Generierung"},
    "image_edit":     {"limit": 30, "window_hours": 4, "label": "Bild-Bearbeitung"},
    "image_analyze":  {"limit": 30, "window_hours": 4, "label": "Bild-Analyse"},
    "screencast":     {"limit": 30, "window_hours": 4, "label": "Screencast"},
}

# ─── Job-Verwaltung ────────────────────────────────────────────────────────────
MAX_RESULT_FILES     = 20    # max. gespeicherte Ergebnis-Dateien pro User (älteste wird entfernt)
JOB_RETENTION_HOURS  = 168  # 7 Tage — danach wird Datei als "abgelaufen" markiert
JOB_WATCHDOG_MINUTES = 20   # Job gilt als hängend wenn kein Heartbeat seit X Minuten

# ─── Upload-Größen ─────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES           = 200 * 1024 * 1024   # allgemein (200 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # Übersetzung: größere Dokumente erlaubt (500 MB)
MAX_TRANSCRIPTION_BYTES    = 200 * 1024 * 1024   # Audio-Upload (200 MB)
MAX_IMAGE_BYTES            = 10  * 1024 * 1024   # Bild-Upload (10 MB)
MAX_OUTPUT_VIDEO_BYTES     = 200 * 1024 * 1024   # Ausgabe-Video-Limit (200 MB)

# ─── Zeichen-Limits (pro Anfrage, nicht pro Zeitfenster) ──────────────────────
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
SUMMARY_MAX_CHARS    = 100_000
SCREENCAST_MAX_CHARS = 100_000

# ─── Screencast ────────────────────────────────────────────────────────────────
MAX_SCREENCAST_SLIDES = 50

# ─── Celery Task Timeouts (in Sekunden) ───────────────────────────────────────
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min — SoftTimeLimitExceeded → graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min — SIGKILL Fallback

SCREENCAST_SOFT_TIME_LIMIT      = 3600   # 60 min
SCREENCAST_TIME_LIMIT           = 3720   # 62 min

SCREENCAST_AUTO_SOFT_TIME_LIMIT = 7200   # 2h (translate + scripts + TTS + render)
SCREENCAST_AUTO_TIME_LIMIT      = 7320   # 2h 2min
