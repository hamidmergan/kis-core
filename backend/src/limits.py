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
    "tts":            {"limit": 100, "window_hours": 4, "label": "Text in Audio"},
    "summary":        {"limit": 100, "window_hours": 4, "label": "Zusammenfassung"},
    "translate":      {"limit": 100, "window_hours": 4, "label": "Dokumentenübersetzung"},
    "transcription":  {"limit": 100, "window_hours": 4, "label": "Transkription"},
    "image_generate": {"limit": 100, "window_hours": 4, "label": "Bild-Generierung"},
    "image_edit":     {"limit": 100, "window_hours": 4, "label": "Bild-Bearbeitung"},
    "image_analyze":  {"limit": 100, "window_hours": 4, "label": "Bild-Analyse"},
    "screencast":     {"limit": 100, "window_hours": 4, "label": "Screencast"},
    "podcast":        {"limit": 100, "window_hours": 4, "label": "Podcast"},
    # No daily cap, the one-running-job rule in the start route is the only brake.
    "praesentation":  {"limit": -1, "window_hours": 4, "label": "Präsentation"},
    "aia_generate":   {"limit": 300, "window_hours": 4, "label": "KI-Tutor: Generierung"},
}

# --- Terminology glossaries (translation tool, per user, DB-backed) ----------
GLOSSARY_MAX_COUNT   = 10    # max glossaries a single user may keep
GLOSSARY_MAX_ENTRIES = 500   # max term pairs per glossary
GLOSSARY_NAME_MAX    = 120   # max chars for a glossary name

# The pool is the only retention rule, there is no deadline.
MAX_RESULT_FILES            = 100   # jobs kept per user (oldest beyond this is evicted)
JOB_WATCHDOG_MINUTES        = 10    # job is stuck when no finished unit reported it for X minutes
AWAITING_USER_TIMEOUT_HOURS = 168   # awaiting_user and paused jobs idle for longer are abandoned

# A test account from an access code stays locked this long before the sweep removes it.
ACCESS_ACCOUNT_DELETE_AFTER_DAYS = 30   # 0 switches the sweep off entirely

# Conversations of the interpreter, kept at the account, the least recently used drops out.
MAX_INTERPRETER_SESSIONS    = 100

# A failed stage resumes by itself this often, then the job pauses and waits for the person.
MAX_AUTO_RESUMES       = 3
RETRY_BACKOFF_SECONDS  = (60, 180, 600)

# --- Upload sizes ------------------------------------------------------------
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # general (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # translation (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # audio upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # image upload (20 MB)
# --- Character limits (per request, not per time window) --------------------
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
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
# The same ceiling every other tool uses, the line count only catches a runaway model.
PODCAST_MAX_CHARS        = 100_000
PODCAST_MAX_LINES        = 250
PODCAST_MAX_LINE_CHARS   = 1200
# One breath between two contributions so they do not run into each other.
PODCAST_LINE_PAUSE       = 0.35
# The same lever as the screencast: waiting on the provider, not own CPU.
PODCAST_TTS_PARALLELISM  = 8
# --- Podcast: reading every source into facts --------------------------------
# One call per source, so no source depends any more on its place in the list.
# The numbers are the podcast's own, the summary is calibrated on a dossier of ten files.
# What one fact is worth of the material budget, and the least and most one source may bring.
PODCAST_FACTS_MIN_CHARS      = 3_000
PODCAST_FACTS_MAX_CHARS      = 12_000
# The script prompt is short, unlike the dossier's, so little has to be kept free for it.
PODCAST_PROMPT_RESERVE_CHARS = 10_000
# Characters one read call may carry. Beyond this no model window takes the source whole,
# and three doomed calls per file cost more than the tail of a very long document.
PODCAST_READ_MAX_SOURCE_CHARS = 500_000
# Facts one read call may return, the guard against a model that runs away with a source.
PODCAST_READ_MAX_FACTS       = 40
PODCAST_READ_MAX_OUTPUT_TOKENS = 8_250
# Three at once, the value measured for the summary on 20.09. against the same providers.
PODCAST_MAP_CONCURRENCY      = 3
PODCAST_READ_MAX_ATTEMPTS    = 3
PODCAST_RETRY_DELAY_SECONDS  = 3
PODCAST_MAX_BACKOFF_SECONDS  = 60
PODCAST_CALL_TIMEOUT_SECONDS = 270
# A whole read phase can pass without a single job update, so a pulse reports in meanwhile.
PODCAST_HEARTBEAT_SECONDS    = 60

# --- Präsentation ------------------------------------------------------------
PRAESENTATION_MAX_SLIDES = 30
# The floor a usable outline needs: cover, one slide of content, closing.
PRAESENTATION_MIN_SLIDES = 3
PRAESENTATION_MAX_TEMPLATES = 10
PRAESENTATION_TEMPLATE_MAX_MB = 30
PRAESENTATION_MAX_SOURCES = 10
# Slides per model call: enough context per slide, few enough calls per deck.
PRAESENTATION_BATCH = 5
PRAESENTATION_IMAGE_PARALLELISM = 4
# Material for a single slide, whether searched or cut out of the run's snapshot.
PRAESENTATION_SLIDE_CONTEXT_CHARS = 6000

# How many parts of a long recording go to the provider at once.
STT_CHUNK_PARALLELISM = 2

# --- Celery task timeouts (in seconds) --------------------------------------
# A long job works in stages: it stops after STAGE_SECONDS, saves, and re-queues itself,
# so no single task run can outlast the limits below however long the result gets.
STAGE_SECONDS           = 600    # 10 min of work per stage, checked before each unit
STAGE_SOFT_TIME_LIMIT   = 1200   # 20 min, SoftTimeLimitExceeded -> one failed attempt
STAGE_TIME_LIMIT        = 1320   # 22 min, SIGKILL fallback, the watchdog picks the job up

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
# An instruction to a learning tool, longer ones are cut at the same place in the schema.
AIA_INSTRUCTION_MAX_CHARS              = 500

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
# Material an exercise tool gets per requested item, a set of 15 lands on the measured 100k.
AIA_EXERCISE_CHARS_PER_ITEM            = 6_700
# Characters per batch for the summary during ingest, a ceiling and not a target.
# Measured on the model: 600k pass, 700k are refused, so 500k keeps a margin. It lets
# a document of up to ~150 pages be summarised in one call instead of two plus a
# merge, and merging two partial summaries always loses detail. A refused batch costs
# the summary, never the source.
AIA_SUMMARY_BATCH_MAX_CHARS            = 500000
# Chunks per embedding request, the client halves it on a refusal itself.
AIA_EMBEDDING_BATCH_SIZE               = 1000
# Timeout for the source chip embeddings, otherwise the answer goes out chip free.
AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS  = 30
AIA_WORKSPACE_MAX_ACCESS_LINKS         = 10      # max enrollment links per workspace
AIA_WORKSPACE_MAX_MEMBERS              = 100     # max enrolled members per workspace
AIA_NOTES_MAX_PER_USER              = 100     # max notes per user per workspace
GLOSSARY_LIMIT                        = 150     # max glossary entries per workspace

# --- Summary tool -----------------------------------------------------------
SUMMARY_MAX_SOURCES          = 10
# Counted after extraction, so it holds for every format. A file goes into one call whole,
# so this is also what the model's window has to carry.
SUMMARY_MAX_CHARS_PER_SOURCE = 500_000
# Facts one read call may return, the share of the pool one source gets.
SUMMARY_FACTS_MAX_CHARS      = 10_000
SUMMARY_FACTS_MIN_CHARS      = 3_000
# Room in a call for the prompt, the build plan and the sections already written.
SUMMARY_PROMPT_RESERVE_CHARS = 60_000
# Facts one read call may return. Measured 20.09.: a fact costs 89 to 152 tokens as JSON
# with its proof, and the model saturates at about 33 facts per call anyway. Two files in
# one call therefore returned 33 between them instead of 33 each, which is why every file
# gets a call of its own.
SUMMARY_READ_MAX_FACTS       = 40
# Ceiling on the answer of a read call, the cap above times what a fact costs as JSON.
# Measured 20.09.: the model stops at about 4.300 tokens on its own, so this only ever
# catches a cap raised by hand, and a cut off answer costs the whole file.
SUMMARY_MAX_OUTPUT_TOKENS    = 8_250
# What the prompt around a read call costs on top of the file and its answer.
SUMMARY_WINDOW_PROMPT_TOKENS = 1_500
# One section per this many characters of facts, the planner gets it as a target.
SUMMARY_CHARS_PER_SECTION    = 4_000
SUMMARY_MIN_SECTIONS         = 3
SUMMARY_MAX_SECTIONS         = 20
# Sections every source gets at least, so no file drops out of the plan.
SUMMARY_SECTIONS_PER_SOURCE  = 2
# Characters of prose one writing call may produce, so several small sections share a call.
# Well below SUMMARY_WRITE_MAX_TOKENS times three, the rest is room for running long.
SUMMARY_SECTION_GROUP_CHARS  = 15_000
# Measured 20.09.: a section costs about this much prose, plus per fact.
SUMMARY_SECTION_BASE_CHARS   = 600
SUMMARY_SECTION_FACT_CHARS   = 160
# Facts one assignment call places. Measured 20.09.: 400 in one answer, no gap, because the
# answer is only two numbers per fact. What a weaker model still drops gets one more call.
SUMMARY_ASSIGN_BATCH_FACTS   = 400
# Assignment calls out at once, the answers are applied in the order of the batches.
SUMMARY_ASSIGN_CONCURRENCY   = 5
# A writing call may return this many tokens, a group of sections or the whole fallback text.
# Measured 20.09.: the provider takes 32.000, so 4.000 was cutting long sections for nothing.
SUMMARY_WRITE_MAX_TOKENS     = 8_000
# The shared client cuts reads at 120 s, this tool's calls may take longer.
# Measured 20.09.: myLab drops a call at about 300 s with a bare 500. Ours has to fire
# first, so a long call comes back as a timeout we retry, not as a server error.
SUMMARY_CALL_TIMEOUT_SECONDS = 270
# The watchdog counts silence, so the run reports in this often.
SUMMARY_HEARTBEAT_SECONDS    = 60
# Read calls out at once. Measured 20.09. on the real documents: at three the slowest
# call takes 161 s and the provider drops a call at about 300 s, so 139 s are left over.
# At five it is 205 s for 27 percent more throughput, and a provider half as fast kills it.
SUMMARY_MAP_CONCURRENCY      = 3
SUMMARY_READ_MAX_ATTEMPTS    = 3
SUMMARY_RETRY_DELAY_SECONDS  = 3
# The waiting time doubles per attempt and stops growing here.
SUMMARY_MAX_BACKOFF_SECONDS  = 60
SUMMARY_OUTLINE_MAX_ATTEMPTS = 2
# The fallback call writes the whole document from facts that are already on disk.
# One dropped call would otherwise cost the stage everything it read.
SUMMARY_COMPOSE_MAX_ATTEMPTS = 2

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
