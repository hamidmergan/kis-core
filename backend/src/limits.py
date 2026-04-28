# -----------------------------------------------------------------------------
# limits.py: central configuration file for all adjustable limits
#
# Change any values here that affect limits, timeouts or quotas.
# All other modules import from here.
# -----------------------------------------------------------------------------

# --- Rate limiting: burst block for chat (against bugs/abuse) ---------------
# Idea: anyone sending too many chat requests in a short window (typically a
# frontend bug or script) is briefly excluded from chat. Intentionally no
# daily/hourly limit, no strike system: students must be able to work 24/7.
# Values: 50/60s is at Anthropic tier-1 level, only catches bots/bugs.
RATE_LIMIT_BURST_REQUESTS       = 50   # max chat requests per burst window
RATE_LIMIT_BURST_WINDOW_SECONDS = 60   # burst window
RATE_LIMIT_BLOCK_MINUTES        = 10   # block duration when burst limit triggers

# --- Quota: per-user tool limits ---------------------------------------------
# limit:        max requests per time window
# window_hours: hours until reset (starts when the limit is first hit)
# label:        display name for admin UI and error messages
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

# --- Job management ---------------------------------------------------------
MAX_RESULT_FILES     = 20    # max stored result files per user (oldest is evicted)
JOB_RETENTION_HOURS  = 168  # 7 days, after which the file is marked as "expired"
JOB_WATCHDOG_MINUTES = 20   # job is considered stuck when no heartbeat for X minutes

# --- Upload sizes ------------------------------------------------------------
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # general (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # translation (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # audio upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # image upload (20 MB)
MAX_OUTPUT_VIDEO_BYTES     = 300 * 1024 * 1024   # output video limit (200 MB)

# --- Character limits (per request, not per time window) --------------------
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
SUMMARY_MAX_CHARS    = 100_000
SCREENCAST_MAX_CHARS = 100_000

# --- Bundle download --------------------------------------------------------
BUNDLE_INCLUDE_AUDIO  = False  # include MP3s in ZIP
BUNDLE_INCLUDE_IMAGES = False  # include slide images in ZIP

# --- Screencast -------------------------------------------------------------
MAX_SCREENCAST_SLIDES          = 50
MAX_QUEUED_SCREENCAST_JOBS     = 5  # max jobs in user queue (including running)

# CPU parallelism for render operations: tune to available cores:
# 4 cores  ->  RENDER_MAX_WORKERS = 2
# 8 cores  ->  RENDER_MAX_WORKERS = 4
# 16 cores ->  RENDER_MAX_WORKERS = 8
# Rule of thumb: half the core count, leaves enough CPU for Uvicorn + OS
RENDER_MAX_WORKERS = 2  # ThreadPoolExecutor limit for PDF->PNG and FFmpeg

# --- Celery task timeouts (in seconds) --------------------------------------
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min, SoftTimeLimitExceeded -> graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min, SIGKILL fallback

SCREENCAST_SOFT_TIME_LIMIT      = 3600   # 60 min
SCREENCAST_TIME_LIMIT           = 3720   # 62 min

SCREENCAST_AUTO_SOFT_TIME_LIMIT = 7200   # 2h (translate + scripts + TTS + render)
SCREENCAST_AUTO_TIME_LIMIT      = 7320   # 2h 2min

# --- AI tutor page summaries ------------------------------------------------
KIA_SUMMARY_MAX_RETRIES             = 3
KIA_SUMMARY_TIMEOUT_SMALL           = 120    # ollama, seconds per request
KIA_SUMMARY_TIMEOUT_LARGE           = 180    # cloud/kisski, seconds per request (100 pages take longer)
KIA_SUMMARY_MAX_TOKENS_SMALL        = 2048   # ollama, single page (incl. think overhead)
KIA_SUMMARY_MAX_TOKENS_LARGE        = 2048   # cloud, single page
KIA_SUMMARY_MAX_TOKENS_BATCH        = 16384  # cloud, batch: up to 100 pages x ~400 chars + JSON overhead
KIA_SUMMARY_CONTENT_MAX_CHARS       = 2000   # max chars per page to LLM (200x2000 + 200x400 output = 480k < 512k)
KIA_SUMMARY_PARALLEL_WORKERS_SMALL  = 5      # ollama: parallel single requests
KIA_SUMMARY_PARALLEL_WORKERS_LARGE  = 1      # cloud: sequential, more reliable
KIA_SUMMARY_BATCH_SIZE              = 25     # pages per batch request (500 pages = 20 requests)
KIA_SOURCE_MAX_PAGES                = 500     # max pages per PDF/DOCX/PPTX upload
KIA_MODULE_MAX_SOURCES              = 30      # max sources per workspace
KIA_MODULE_MAX_ACCESS_LINKS         = 10      # max enrollment links per module
KIA_NOTES_MAX_PER_USER              = 100     # max notes per user per workspace
GLOSSARY_LIMIT                        = 150     # max glossary entries per workspace
