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
    "tts":            {"limit": 20, "window_hours": 4, "label": "Text in Sprache"},
    "summary":        {"limit": 30, "window_hours": 4, "label": "Zusammenfassung"},
    "translate":      {"limit": 30, "window_hours": 4, "label": "Dokumentenübersetzung"},
    "transcription":  {"limit": 30, "window_hours": 4, "label": "Transkription"},
    "image_generate": {"limit": 30, "window_hours": 4, "label": "Bild-Generierung"},
    "image_edit":     {"limit": 30, "window_hours": 4, "label": "Bild-Bearbeitung"},
    "image_analyze":  {"limit": 30, "window_hours": 4, "label": "Bild-Analyse"},
    "screencast":     {"limit": 20, "window_hours": 4, "label": "Screencast"},
}

# ─── Job-Verwaltung ────────────────────────────────────────────────────────────
MAX_RESULT_FILES     = 20    # max. gespeicherte Ergebnis-Dateien pro User (älteste wird entfernt)
JOB_RETENTION_HOURS  = 168  # 7 Tage — danach wird Datei als "abgelaufen" markiert
JOB_WATCHDOG_MINUTES = 20   # Job gilt als hängend wenn kein Heartbeat seit X Minuten

# ─── Upload-Größen ─────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # allgemein (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # Übersetzung (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # Audio-Upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # Bild-Upload (20 MB)
MAX_OUTPUT_VIDEO_BYTES     = 300 * 1024 * 1024   # Ausgabe-Video-Limit (200 MB)

# ─── Zeichen-Limits (pro Anfrage, nicht pro Zeitfenster) ──────────────────────
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
SUMMARY_MAX_CHARS    = 100_000
SCREENCAST_MAX_CHARS = 100_000

# ─── Bundle Download ───────────────────────────────────────────────────────────
BUNDLE_INCLUDE_AUDIO  = False  # MP3s in ZIP einschließen
BUNDLE_INCLUDE_IMAGES = False  # Slide-Bilder in ZIP einschließen

# ─── Screencast ────────────────────────────────────────────────────────────────
MAX_SCREENCAST_SLIDES          = 50
MAX_QUEUED_SCREENCAST_JOBS     = 5  # max. Jobs in User-Warteschlange (inkl. laufender)

# CPU-Parallelität für Render-Operationen — auf verfügbare Kerne anpassen:
# 4 Kerne  →  RENDER_MAX_WORKERS = 2
# 8 Kerne  →  RENDER_MAX_WORKERS = 4
# 16 Kerne →  RENDER_MAX_WORKERS = 8
# Faustregel: halbe Kernzahl → lässt genug CPU für Uvicorn + OS frei
RENDER_MAX_WORKERS = 2  # ThreadPoolExecutor-Limit für PDF→PNG und FFmpeg

# ─── Celery Task Timeouts (in Sekunden) ───────────────────────────────────────
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min — SoftTimeLimitExceeded → graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min — SIGKILL Fallback

SCREENCAST_SOFT_TIME_LIMIT      = 3600   # 60 min
SCREENCAST_TIME_LIMIT           = 3720   # 62 min

SCREENCAST_AUTO_SOFT_TIME_LIMIT = 7200   # 2h (translate + scripts + TTS + render)
SCREENCAST_AUTO_TIME_LIMIT      = 7320   # 2h 2min

# ─── KI-Tutor Seitenzusammenfassungen ─────────────────────────────────────────
TUTOR_SUMMARY_MAX_RETRIES             = 3
TUTOR_SUMMARY_TIMEOUT_SMALL           = 120    # ollama, Sekunden pro Request
TUTOR_SUMMARY_TIMEOUT_LARGE           = 90     # cloud/kisski, Sekunden pro Request
TUTOR_SUMMARY_MAX_TOKENS_SMALL        = 2048   # ollama, Einzel-Seite (inkl. Think-Overhead)
TUTOR_SUMMARY_MAX_TOKENS_LARGE        = 2048   # cloud, Einzel-Seite
TUTOR_SUMMARY_MAX_TOKENS_BATCH        = 8192   # cloud, Batch: Think-Block (~3k) + N × 400 Zeichen
TUTOR_SUMMARY_CONTENT_MAX_CHARS       = 3000   # max. Zeichen pro Seite an LLM
TUTOR_SUMMARY_PARALLEL_WORKERS_SMALL  = 5      # ollama: parallele Einzel-Requests
TUTOR_SUMMARY_PARALLEL_WORKERS_LARGE  = 3      # cloud: parallele Batch-Requests
TUTOR_SUMMARY_BATCH_SIZE              = 10      # Seiten pro Batch-Request (große Modelle)
TUTOR_SOURCE_MAX_PAGES                = 300     # max. Seiten pro PDF/DOCX/PPTX-Upload
