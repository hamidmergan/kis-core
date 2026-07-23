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

# --- Rate limiting: burst block for tools (AI assistant + classic) ----------
# Unified across all tools so users see consistent behavior. The threshold is
# generous (parallel studio use, multi-job submissions) and only catches
# scripts/bugs firing dozens of requests per second.
TOOL_BURST_REQUESTS             = 50   # max requests per burst window per tool
TOOL_BURST_WINDOW_SECONDS       = 60
TOOL_BURST_BLOCK_MINUTES        = 10

# --- Source upload limits ---------------------------------------------------
# There is no concurrent in-flight cap: backpressure for indexing lives in the
# Celery worker (bounded ``--concurrency`` on the ``aia`` queue), so extra
# uploads just wait as ``pending`` instead of being rejected with a 429. The
# hourly cap throttles the drip pattern: 100/hour comfortably covers a lecturer
# setting up a course while blocking bot-style spam. The per-workspace ceiling
# (AIA_WORKSPACE_MAX_SOURCES) is the other guard.
UPLOAD_HOURLY_MAX               = 100
UPLOAD_HOURLY_WINDOW_SECONDS    = 3600

# --- Quota: per-user tool limits ---------------------------------------------
# limit:        max requests per time window
# window_hours: hours until reset (starts when the limit is first hit)
# label:        display name for admin UI and error messages
QUOTA_DEFAULTS: dict[str, dict] = {
    "tts":            {"limit": 100, "window_hours": 4, "label": "Text in Sprache"},
    "summary":        {"limit": 100, "window_hours": 4, "label": "Zusammenfassung"},
    "translate":      {"limit": 100, "window_hours": 4, "label": "Dokumentenübersetzung"},
    "transcription":  {"limit": 100, "window_hours": 4, "label": "Transkription"},
    "image_generate": {"limit": 100, "window_hours": 4, "label": "Bild-Generierung"},
    "image_edit":     {"limit": 100, "window_hours": 4, "label": "Bild-Bearbeitung"},
    "image_analyze":  {"limit": 100, "window_hours": 4, "label": "Bild-Analyse"},
    "screencast":     {"limit": 100, "window_hours": 4, "label": "Screencast"},
    "aia_generate":   {"limit": 300, "window_hours": 4, "label": "KI-Tutor: Generierung"},
}

# --- Terminology glossaries (translation tool, per user, DB-backed) ----------
GLOSSARY_MAX_COUNT   = 10    # max glossaries a single user may keep
GLOSSARY_MAX_ENTRIES = 500   # max term pairs per glossary
GLOSSARY_NAME_MAX    = 120   # max chars for a glossary name

# --- Job management ---------------------------------------------------------
MAX_RESULT_FILES            = 20    # max stored result files per user (oldest is evicted)
JOB_RETENTION_HOURS         = 168   # 7 days, after which the file is marked as "expired"
JOB_WATCHDOG_MINUTES        = 5     # job is stuck when no heartbeat for X minutes (heartbeat fires every 10 s)
AWAITING_USER_TIMEOUT_HOURS = 168   # awaiting_user jobs older than this are abandoned and cleaned up

# --- Upload sizes ------------------------------------------------------------
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # general (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # translation (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # audio upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # image upload (20 MB)
MAX_OUTPUT_VIDEO_BYTES     = 300 * 1024 * 1024   # output video limit (300 MB)

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

# Per-provider TTS concurrency for screencast batch generation.
# Conservative default (1) — providers are identified by numeric ID now;
# parallelism can be tuned per-provider in the admin panel if needed.
SCREENCAST_TTS_DEFAULT_PARALLELISM = 1

# --- Celery task timeouts (in seconds) --------------------------------------
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min, SoftTimeLimitExceeded -> graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min, SIGKILL fallback

SCREENCAST_SOFT_TIME_LIMIT      = 3600   # 60 min
SCREENCAST_TIME_LIMIT           = 3720   # 62 min

# --- AI tutor source limits -------------------------------------------------
AIA_SOURCE_MAX_PAGES                = 200     # max pages per PDF/DOCX/PPTX upload;
# lange Skripte kapitelweise hochladen. Bis ~200 S. bleibt eine Quelle handhabbar; sehr
# große Dokumente (489-S.-Monster) werden weiter abgelehnt, damit der Überblick nicht
# front-lastig wird. Admin-tunable (1..2000). Reject-Meldung: ``ai.source.tooManyPages``.
AIA_WORKSPACE_MAX_SOURCES              = 50      # max sources per workspace (admin-tunable 1..1000)

# --- AI tutor chat question input -------------------------------------------
# Hard cap on a single chat question's length. Mirrored in the ChatBody schema
# (max_length -> clean 422) and the chat textarea (maxLength). 8000 chars ~ 2000
# tokens: long enough for a pasted multi-part question, but safely under any
# model window. Without it an unbounded paste could overflow the embedding call
# or the answer context. The retrieval query is ADDITIONALLY truncated to
# AIA_EMBED_QUERY_MAX_CHARS before embedding: the embedding provider is admin-
# configurable and may have a low input limit (e.g. a 512-token model), and a
# very long query also yields a washed-out, less precise search vector. Only the
# SEARCH query is shortened; the full question still reaches the answer model.
AIA_QUESTION_MAX_CHARS                 = 8000
AIA_EMBED_QUERY_MAX_CHARS              = 2000

# --- AI tutor GENERIC context budget ----------------------------------------
# The overview path fills context round-robin across the active sources and
# truncates at this CHARACTER budget — sized for the supported minimum tier
# (Mid, ~128k token context; Small 8B/32k is no longer a design target). Math:
# at a conservative ~3.5 chars/token (mixed DE / non-Latin scripts) 250k chars
# ≈ ~71k tokens of context, leaving ample room for system prompt + question +
# answer inside a 128k window. The SPECIFIC path shares this builder and packs
# into ONE window (multi=False): hits beyond the budget are DROPPED, not split
# into map-reduce batches anymore (neighbor expansion bounds SPECIFIC to one
# coherent window). A higher budget mainly helps the FIT-shortcut (whole sources
# sent in full) and GENERIC breadth; SPECIFIC stays bounded by its expansion
# regardless. Admin-tunable per deployment; raise toward AIA_CONTEXT_HARD_CAP
# for large/cloud models.
AIA_CONTEXT_MAX_CHARS                  = 250000
# Hard ceiling for the admin-tunable budget (~228k tokens at ~3.5 chars/token).
# Sized for a 256k-token model, leaving ~28k tokens of headroom for system
# prompt + question + answer. Even a deployment on the largest cloud models
# cannot exceed this — guards against an admin typo (1M+) that would stall/
# overflow the model and waste a giant DB read. Enforced both on write (admin
# PATCH validation, which imports this constant) and on read (_context_budget clamp).
AIA_CONTEXT_HARD_CAP                    = 800000
# Separate context budget for the GENERATION TOOLS (mindmap, data table, quiz,
# flashcards, glossary, cloze, cards) — kept distinct from the chat budget above
# so an admin can give the tools a much larger window without enlarging every
# chat turn. A tool packs (a share of) a WHOLE document into ONE generation call,
# so the budget is divided by the number of selected sources at the call site.
# Default matches the chat budget (safe for the supported minimum tier, ~128k);
# raise toward the tool hard cap for large/cloud models. Admin-tunable via
# ``aia_tool_context_max_chars``.
AIA_TOOL_CONTEXT_MAX_CHARS             = 250000
# Hard ceiling for the tool budget — higher than the chat cap because the tools
# pack a whole document into a single call and an admin may run a large/cloud
# model (target up to ~900k chars ≈ ~257k tokens). Enforced on write (admin
# PATCH validation) and on read (tool_context_budget clamp).
AIA_TOOL_CONTEXT_HARD_CAP              = 1_000_000
# Per-batch char cap for the ingest-side DOC SUMMARY (aia_summarizer). Sized to
# MINIMISE the number of GWDG-rate-limited summary calls per ingest (the shared
# limit is 2/s, 15/min for the whole university), while keeping each batch small
# enough that its summary still carries real detail (the output is capped, so a
# huge batch compresses too hard — see private/summary-batching-erklaert.md).
# 360k chars ≈ ~102k tokens; measured ~23s/call on KISSKI qwen3-30b (256k ctx),
# well within limits. A large doc still spills into more batches + a combine call.
# Admin-tunable: ``aia_summary_batch_max_chars``.
AIA_SUMMARY_BATCH_MAX_CHARS            = 360000
# Chunks (input texts) per embedding request at ingest. Higher = fewer requests
# against the shared GWDG rate limit. Measured safe on myLab qwen3-embedding-4b:
# 1000 OK, 2000 → 502 → bounded to 1000 (see aia_embeddings._BATCH_SIZE ceiling).
# Admin-tunable: ``aia_embedding_batch_size``.
AIA_EMBEDDING_BATCH_SIZE               = 1000
AIA_WORKSPACE_MAX_ACCESS_LINKS         = 10      # max enrollment links per workspace
AIA_NOTES_MAX_PER_USER              = 100     # max notes per user per workspace
GLOSSARY_LIMIT                        = 150     # max glossary entries per workspace

# --- AI tutor background dispatcher -----------------------------------------
# We manage a shared pool of parallel processing slots for BACKGROUND jobs, NOT
# API rate limits (the per-second / 15-per-minute caps are KISSKI/GWDG's concern,
# not ours). Chat is NOT in this pool: it runs synchronously in the request, not
# as a background job. The pool covers upload (ingest) and studio tools.
#
# A freed slot goes to an area by weight, then round-robin across users so one
# user can never block the others. Studio outweighs ingest because a student
# actively waits on a studio tool, while uploads process in the background.
#
# Admin-tunable at runtime (settings: aia_parallel_slots, aia_area_weights).
# Raise AIA_PARALLEL_SLOTS (or set 0 = unlimited) once we run on our own GPU and
# the parallelism no longer needs rationing.
AIA_PARALLEL_SLOTS                     = 2       # total background jobs in flight (0 = unlimited)
AIA_AREA_WEIGHTS                       = {"studio": 2, "ingest": 1}

# Max simultaneous source uploads in the HTTP layer (the streaming + convert +
# store phase). Caps RAM/CPU when several people upload large media at once on
# the small box. 0 = unlimited. Admin-tunable at runtime (aia_max_concurrent_uploads).
AIA_MAX_CONCURRENT_UPLOADS             = 3
