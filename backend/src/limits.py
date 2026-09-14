# Central place for all configurable limits, timeouts and quotas.

from src.services.system_capacity import capacity

# Burst block for the chat, it only catches bots and mistakes.
RATE_LIMIT_BURST_REQUESTS       = 50   # max chat requests per burst window
RATE_LIMIT_BURST_WINDOW_SECONDS = 60   # burst window
RATE_LIMIT_BLOCK_MINUTES        = 10   # block duration when burst limit triggers

# Burst block for the tools, uniform and generous.
TOOL_BURST_REQUESTS             = 50   # max requests per burst window per tool
TOOL_BURST_WINDOW_SECONDS       = 60
TOOL_BURST_BLOCK_MINUTES        = 10

# Limits for uploading sources, no cap on concurrent runs.
UPLOAD_HOURLY_MAX               = 100
UPLOAD_HOURLY_WINDOW_SECONDS    = 3600

# Quota per user and tool: count, window length and display name.
QUOTA_DEFAULTS: dict[str, dict] = {
    "tts":            {"limit": 100, "window_hours": 4, "label": "Text in Sprache"},
    "summary":        {"limit": 100, "window_hours": 4, "label": "Zusammenfassung"},
    "translate":      {"limit": 100, "window_hours": 4, "label": "Dokumentenübersetzung"},
    "transcription":  {"limit": 100, "window_hours": 4, "label": "Transkription"},
    "image_generate": {"limit": 100, "window_hours": 4, "label": "Bild-Generierung"},
    "image_edit":     {"limit": 100, "window_hours": 4, "label": "Bild-Bearbeitung"},
    "image_analyze":  {"limit": 100, "window_hours": 4, "label": "Bild-Analyse"},
    "screencast":     {"limit": 100, "window_hours": 4, "label": "Screencast"},
    "podcast":        {"limit": 100, "window_hours": 4, "label": "Podcast"},
    "aia_generate":   {"limit": 300, "window_hours": 4, "label": "KI-Tutor: Generierung"},
}

# --- Terminology glossaries (translation tool, per user, DB-backed) ----------
GLOSSARY_MAX_COUNT   = 10    # max glossaries a single user may keep
GLOSSARY_MAX_ENTRIES = 500   # max term pairs per glossary
GLOSSARY_NAME_MAX    = 120   # max chars for a glossary name

# The pool is the only retention rule, there is no deadline.
MAX_RESULT_FILES            = 100   # jobs kept per user (oldest beyond this is evicted)
JOB_WATCHDOG_MINUTES        = 5     # job is stuck when no heartbeat for X minutes (heartbeat fires every 10 s)
AWAITING_USER_TIMEOUT_HOURS = 168   # awaiting_user jobs older than this are abandoned and cleaned up

# --- Upload sizes ------------------------------------------------------------
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # general (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # translation (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # audio upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # image upload (20 MB)
# --- Character limits (per request, not per time window) --------------------
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
SUMMARY_MAX_CHARS    = 100_000
SCREENCAST_MAX_CHARS = 100_000

# --- Bundle download --------------------------------------------------------
BUNDLE_INCLUDE_AUDIO  = False  # include MP3s in ZIP
BUNDLE_INCLUDE_IMAGES = False  # include slide images in ZIP

# Longest recording that is accepted.
MAX_AUDIO_SEC                  = 6000   # 100 min

# Open jobs per person and tool, counting running, waiting and queued ones.
MAX_OPEN_JOBS_PER_TOOL         = 5

# --- Screencast -------------------------------------------------------------
MAX_SCREENCAST_SLIDES          = 50

# Threads for PDF to PNG and ffmpeg, sized by the machine's cores.
RENDER_MAX_WORKERS = capacity().render_workers

# How many slides are voiced at once, measured and applied per screencast.
SCREENCAST_TTS_PARALLELISM = 8

# --- Podcast ----------------------------------------------------------------
# More sources than this dilute every single one below a useful share.
PODCAST_MAX_SOURCES      = 10
PODCAST_MAX_LINES        = 80
PODCAST_MAX_LINE_CHARS   = 1200
# One breath between two contributions so they do not run into each other.
PODCAST_LINE_PAUSE       = 0.35
# The same lever as the screencast: waiting on the provider, not own CPU.
PODCAST_TTS_PARALLELISM  = 8
# How many uploaded files the hidden per-person store keeps before evicting the least recently used.
PODCAST_STORE_MAX_SOURCES = 20

# How many parts of a long recording go to the provider at once.
STT_CHUNK_PARALLELISM = 2

# --- Celery task timeouts (in seconds) --------------------------------------
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min, SoftTimeLimitExceeded -> graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min, SIGKILL fallback

# Only catches outliers, real hangs are caught by the heartbeat watchdog.
PODCAST_SOFT_TIME_LIMIT = 3600
PODCAST_TIME_LIMIT      = 3720
SCREENCAST_SOFT_TIME_LIMIT      = 7200   # 120 min, SoftTimeLimitExceeded -> Job sauber auf failed
SCREENCAST_TIME_LIMIT           = 7320   # 122 min, SIGKILL als letzte Instanz

# Timeouts of the tutor tools, generous because an overrun throws everything away.
AIA_TOOL_SOFT_TIME_LIMIT        = 300    # 5 min, SoftTimeLimitExceeded -> Set sauber auf failed
AIA_TOOL_TIME_LIMIT             = 360    # 6 min, SIGKILL als letzte Instanz

# How many packets one table may cost, measured against its own time limit.
AIA_TABLE_MAX_PACKETS           = 10

# The table asks packet by packet, several calls need more room than a single one.
AIA_TABLE_SOFT_TIME_LIMIT       = 600    # 10 min
AIA_TABLE_TIME_LIMIT            = 720    # 12 min

# The schedule spans the whole course and needs more room.
AIA_SCHEDULE_SOFT_TIME_LIMIT    = 1200   # 20 min
AIA_SCHEDULE_TIME_LIMIT         = 1320   # 22 min

# Long recordings on a slow model take a while, a hanging provider must still end.
AIA_TRANSLATE_SOFT_TIME_LIMIT   = 1800   # 30 min
AIA_TRANSLATE_TIME_LIMIT        = 1860   # 31 min

# --- AI tutor source limits -------------------------------------------------
AIA_SOURCE_MAX_PAGES                = 200     # max pages per PDF/DOCX/PPTX upload;
# Very large documents are rejected so the overview does not become front-heavy.
AIA_WORKSPACE_MAX_SOURCES              = 50      # max sources per workspace (admin-tunable 1..1000)

# --- Web page as a source ---------------------------------------------------
WEB_PAGE_MAX_URL_CHARS           = 2000
WEB_PAGE_MAX_REDIRECTS           = 5
WEB_PAGE_CONNECT_TIMEOUT_SECONDS = 5
WEB_PAGE_TIMEOUT_SECONDS         = 15
WEB_PAGE_MAX_HTML_BYTES          = 5 * 1024 * 1024
WEB_PAGE_MAX_PDF_BYTES           = 50 * 1024 * 1024
WEB_PAGE_MIN_WORDS               = 100     # fewer means the page carried no readable text
WEB_PAGE_TITLE_MAX_CHARS         = 120

# --- YouTube video as a source ----------------------------------------------
# Cheap guard against a huge paste, the duration below is the real cap.
YOUTUBE_TRANSCRIPT_MAX_CHARS     = 1_000_000
# A video may weigh about as much as the largest document a workspace accepts.
YOUTUBE_MAX_DURATION_SECONDS     = 4 * 3600
YOUTUBE_OEMBED_TIMEOUT_SECONDS   = 5
YOUTUBE_LAST_SEGMENT_SECONDS     = 5.0     # the pasted text names no end for the last line

# Hard limit for a single chat question, the search query is shortened on top.
AIA_QUESTION_MAX_CHARS                 = 8000
AIA_EMBED_QUERY_MAX_CHARS              = 2000

# Character budget for the overview context, sized for the smallest supported tier.
AIA_CONTEXT_MAX_CHARS                  = 250000
# Hard ceiling for the configurable budget, guards against a typo in the admin area.
AIA_CONTEXT_HARD_CAP                    = 800000
# Context of a specific question, more context made the measurement worse.
AIA_SPECIFIC_MAX_CHARS                  = 60000
# Budget of the overview tools (mind map, data table, schedule, podcast), measured: 600k still pass, 700k are refused.
AIA_TOOL_CONTEXT_MAX_CHARS             = 500_000
# Hard ceiling for both tool budgets, higher than the chat's.
AIA_TOOL_CONTEXT_HARD_CAP              = 1_000_000
# Budget of the exercise tools (flashcards, quiz, cloze, grammar), one set of 15 needs no more.
AIA_EXERCISE_CONTEXT_MAX_CHARS         = 100_000
# Characters per batch for the summary during ingest.
AIA_SUMMARY_BATCH_MAX_CHARS            = 360000
# Chunks per embedding request, the client halves it on a refusal itself.
AIA_EMBEDDING_BATCH_SIZE               = 1000
# Timeout for the source chip embeddings, otherwise the answer goes out chip free.
AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS  = 30
AIA_WORKSPACE_MAX_ACCESS_LINKS         = 10      # max enrollment links per workspace
AIA_NOTES_MAX_PER_USER              = 100     # max notes per user per workspace
GLOSSARY_LIMIT                        = 150     # max glossary entries per workspace

# Shared slot pool for background work, a fixed number instead of detection.
AIA_PARALLEL_SLOTS                     = 4
AIA_AREA_WEIGHTS                       = {"studio": 2, "ingest": 1}

# Maximum concurrent uploads in the heavy phase, sized by the machine.
AIA_MAX_CONCURRENT_UPLOADS             = capacity().max_concurrent_uploads

# Characters per speech request, set by the provider's 60 second edge.
TTS_MAX_CHARS_PER_REQUEST              = 400


# Thread pool and connection pool belong together, the pool stays smaller.
REQUEST_THREAD_LIMIT                   = 32
DB_POOL_MAX_CONNECTIONS                = 40


# Nightly backup into object storage, on top of the snapshots.
DB_BACKUP_KEEP_DAYS                    = 7
DB_BACKUP_KEEP_WEEKS                   = 5
DB_BACKUP_KEEP_MONTHS                  = 12
# Generous so the backup is never cut off midway.
DB_BACKUP_TIME_LIMIT_SECONDS           = 3600
