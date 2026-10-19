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

# Stand codes of the event stamp card: wrong codes per visitor before a short lock, and how
# long Redis remembers a visitor's wrong tries at all.
EVENT_CODE_MAX_ATTEMPTS         = 5
EVENT_CODE_LOCK_SECONDS         = 30
EVENT_CODE_ATTEMPT_TTL_SECONDS  = 3600

# Quota per user and tool: count, window length and display name.
QUOTA_DEFAULTS: dict[str, dict] = {
    "tts":            {"limit": 100, "window_hours": 4, "label": "Text in Audio"},
    "summary":        {"limit": 100, "window_hours": 4, "label": "Report"},
    "pages":          {"limit": 100, "window_hours": 4, "label": "Pages"},
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
# A full provider is no failure: the job waits a random span in this range and tries again,
# uncounted, and only after this long of full provider it counts as a normal attempt.
# Capped low (09.10.2026: a 12h value hammered myLab with a retry every 1-3 min for hours).
PROVIDER_BUSY_WAIT_SECONDS = (60, 180)
PROVIDER_BUSY_MAX_HOURS    = 1
# A learning tool has a person waiting in front of it, after this long of full provider it gives up
# with an error instead of requeueing for hours, measured 08.10.2026: a mind map waited 28 Min.
AIA_TOOL_BUSY_MAX_MINUTES  = 15

# --- Upload sizes ------------------------------------------------------------
MAX_UPLOAD_BYTES           = 500 * 1024 * 1024   # general (500 MB)
TRANSLATE_MAX_UPLOAD_BYTES = 500 * 1024 * 1024   # translation (500 MB)
MAX_TRANSCRIPTION_BYTES    = 500 * 1024 * 1024   # audio upload (500 MB)
MAX_IMAGE_BYTES            = 20  * 1024 * 1024   # image upload (20 MB)
# An image description or a transcribed page stays well below this, a runaway answer stops here.
IMAGE_ANALYZE_MAX_TOKENS   = 1_500
# --- Character limits (per request, not per time window) --------------------
TTS_MAX_CHARS        = 100_000
TRANSLATE_MAX_CHARS  = 100_000
SCRIPT_MAX_CHARS     = 100_000
SCREENCAST_MAX_CHARS = 100_000
# Extra documents for the scripts, the same file and character limits as the other services.
SCREENCAST_MAX_SOURCES = 10
# Characters of material one slide script may read.
SCREENCAST_MATERIAL_PER_SLIDE = 4_000
# Slides per assignment call, keeps the answer of one call short.
SCREENCAST_MATERIAL_SLIDES_PER_CALL = 25

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

# Voicings at one provider at once, the value its admin field starts with. Measured 26.09.2026 at
# myLab: 4 at once gave the most, 8 lost half, 12 lost every single one.
TTS_PROVIDER_MAX_CONCURRENT = 4

# Pictures at one provider at once, the value its admin field starts with, myLab draws one at a time in about 11 s.
IMAGE_PROVIDER_MAX_CONCURRENT = 2

# How long any call waits for a seat at a provider whose admin field sets a cap, below the watchdog.
PROVIDER_SEAT_WAIT_SECONDS    = 120
# A tutor tool waits as long as one call may take, giving up costs a requeue of one to three minutes
# while the seat may already be free again, measured 08.10.2026 with four tools on one local Ollama seat.
AIA_TOOL_SEAT_WAIT_SECONDS    = 270
# From this many characters an LLM call counts as a lot of material, measured 27.09.2026: five of them at
# once at myLab delivered almost nothing and most ran into our time limits.
LLM_LARGE_INPUT_CHARS         = 100_000
# Such calls get at most this share of the LLM seats, a fifth, so 2 of 10.
LLM_LARGE_INPUT_SHARE         = 5
# How long a first choice that did not answer is skipped when it names no time of its own.
PROVIDER_DOWN_SECONDS         = 60
# The availability page checks with real calls, which cost quota at GWDG (1000 a day for prod and dev
# together), so only on opening when the last check is older than this, never in the background.
PROVIDER_CHECK_MAX_AGE_SECONDS = 600
# The refresh button runs real calls again at most this often, however many people press it.
PROVIDER_CHECK_MIN_GAP_SECONDS = 60
# A check waits this long for a seat, a provider whose seats stay full is busy with our own jobs.
PROVIDER_CHECK_SEAT_WAIT_SECONDS = 20
# A provider dropdown checks every entry again with a real call once its result is older than this,
# so a provider costs at most one call per two minutes however often the dropdown opens.
PROVIDER_CHECK_DROPDOWN_MAX_AGE_SECONDS = 120
# The dropdown waits this long for those checks, one that takes longer keeps its last result.
PROVIDER_CHECK_DROPDOWN_WAIT_SECONDS = 8

# How many slides are voiced at once per screencast, more than the provider's seats only waits.
SCREENCAST_TTS_PARALLELISM = TTS_PROVIDER_MAX_CONCURRENT

# --- Podcast ----------------------------------------------------------------
# More sources than this dilute every single one below a useful share.
PODCAST_MAX_SOURCES      = 10
# The same ceiling every other tool uses, the line count only catches a runaway model.
PODCAST_MAX_CHARS        = 100_000
PODCAST_MAX_LINES        = 250
PODCAST_MAX_LINE_CHARS   = 1200
# Contributions one script call writes: 27 x 27 words stay inside SERVICE_WRITE_TOKENS.
PODCAST_LINES_PER_CALL   = 27
# Seconds between two contributions: before a quick reaction, a normal turn, after a long explanation.
PODCAST_PAUSES           = (0.12, 0.25, 0.45)
# The same lever as the screencast: waiting on the provider, not own CPU.
PODCAST_TTS_PARALLELISM  = TTS_PROVIDER_MAX_CONCURRENT
# --- Podcast: reading every source into facts --------------------------------
# One call per source, so no source depends any more on its place in the list.
# The numbers are the podcast's own, the summary is calibrated on a dossier of ten files.
# What one fact is worth of the material budget, and the least and most one source may bring.
# The script prompt is short, unlike the dossier's, so little has to be kept free for it.
# Characters one read call may carry. Beyond this no model window takes the source whole,
# and three doomed calls per file cost more than the tail of a very long document.
# Facts one read call may return, the guard against a model that runs away with a source.
# Three at once, the value measured for the summary on 20.09. against the same providers.
# A whole read phase can pass without a single job update, so a pulse reports in meanwhile.

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
# Slide batches written at once, the same fixed width the summary uses, never an admin setting.
PRAESENTATION_WRITE_PARALLELISM = 3
# Original text for a single slide. Reading is cheap, five slides share one call.
PRAESENTATION_SLIDE_CONTEXT_CHARS = 15_000

# --- Präsentation: reading every source into facts ---------------------------
# One call per source, so no source depends any more on its place in the list.
# The least and most one source may bring to the pool.
# The outline prompt carries the roles and the rules of a deck, so it needs more room
# kept free than the podcast's script prompt does.
# Characters one read call may carry, beyond this no model window takes the source whole.
# Facts one read call may return, the guard against a model that runs away with a source.
# A whole read phase can pass without a single job update, so a pulse reports in meanwhile.

# How many parts of a long recording go to the provider at once.
STT_CHUNK_PARALLELISM = 2

# --- Celery task timeouts (in seconds) --------------------------------------
# A long job works in stages: it stops after STAGE_SECONDS, saves, and re-queues itself,
# so no single task run can outlast the limits below however long the result gets.
STAGE_SECONDS           = 600    # 10 min of work per stage, checked before each unit
STAGE_SOFT_TIME_LIMIT   = 1200   # 20 min, SoftTimeLimitExceeded -> one failed attempt
STAGE_TIME_LIMIT        = 1320   # 22 min, SIGKILL fallback, the watchdog picks the job up

# Timeouts of the tutor tools, generous because an overrun throws everything away and starts over.
# A local model needs up to 270 s for one call, a set is a chain of up to four calls.
AIA_TOOL_SOFT_TIME_LIMIT        = 600    # 10 min, SoftTimeLimitExceeded -> Set sauber auf failed
AIA_TOOL_TIME_LIMIT             = 720    # 12 min, SIGKILL als letzte Instanz

# How many packets one table may cost, measured against its own time limit.
AIA_TABLE_MAX_PACKETS           = 10

# The table asks packet by packet, several calls need more room than a single one.
AIA_TABLE_SOFT_TIME_LIMIT       = 1200   # 20 min
AIA_TABLE_TIME_LIMIT            = 1320   # 22 min

# The schedule spans the whole course and needs more room.
AIA_SCHEDULE_SOFT_TIME_LIMIT    = 1200   # 20 min
AIA_SCHEDULE_TIME_LIMIT         = 1320   # 22 min

# Long recordings on a slow model take a while, a hanging provider must still end.
AIA_TRANSLATE_SOFT_TIME_LIMIT   = 1800   # 30 min
AIA_TRANSLATE_TIME_LIMIT        = 1860   # 31 min

# --- AI tutor source limits -------------------------------------------------
AIA_SOURCE_MAX_PAGES                = 200     # max pages per PDF/DOCX/PPTX upload;
# Characters one workspace document may bring, counted after reading. At this size a source
# still fits alone into podcast, presentation and summary.
AIA_SOURCE_MAX_CHARS                = 500_000
# A pasted text source stays this short so it serves as its own summary.
AIA_TEXT_SOURCE_MAX_CHARS           = 4_000
# Very large documents are rejected so the overview does not become front-heavy.
AIA_WORKSPACE_MAX_SOURCES              = 50      # max sources per workspace (admin-tunable 1..200)
# Mehr nicht: ein Ueberblick teilt 60.000 Zeichen auf alle Quellen, bei 200 bleiben je 300 Zeichen.
AIA_WORKSPACE_MAX_SOURCES_CAP          = 200

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

# Rounds of a chat the pre-call may read to make a follow-up question stand on its own.
FOLLOWUP_HISTORY_ROUNDS                = 4

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

# --- Material der Dienste Podcast, Praesentation, Zusammenfassung --------------
# myLab bricht jeden Aufruf nach etwa 300 s ab (gemessen 20.09.). Lesen ist schnell,
# 250k Zeichen in 12 s (gemessen 22.09.), Schreiben langsam, etwa 14 Token/s. Darum
# plant ein Aufruf ueber dem ganzen nummerierten Text und schreibt dabei wenig, und
# jeder Schreibaufruf schreibt aus dem Originaltext hoechstens SERVICE_WRITE_TOKENS.
# Hochgeladen werden hoechstens so viele Zeichen, ueber alle Dateien zusammen.
SOURCES_MAX_TOTAL_CHARS  = 500_000
# Was Auftrag und Antwortschema eines Planungsaufrufs im Fenster belegen.
MAP_PROMPT_TOKENS        = 3_000
# Deckel eines Planungsaufrufs, nur als Alarm. Eine Gliederung schreibt etwa 2.000 Token.
MAP_OUTPUT_TOKENS        = 4_000
# Darunter wird abgelehnt. 32k wie ein lokales Ollama tragen etwa 77.000 Zeichen je Aufruf,
# groesseres Material geht ueber die Themen, die Schreibaufrufe kuerzen sich aufs Fenster.
MAP_MIN_WINDOW_TOKENS    = 32_768
# Ein nie vermessenes Modell wird wie das kleinste zugelassene Fenster behandelt.
MAP_UNMEASURED_WINDOW_TOKENS = 131_072
# Themen je Teil, wenn der Text nicht in einen Planungsaufruf passt.
MAP_MAX_TOPICS_PER_PART  = 25
# Hoechstens so viele Themen insgesamt, so viele wie ein 128k-Fenster bei 500.000 Zeichen bildet
# (2 Teile). Ein kleines Fenster schneidet in viele Teile, 174 Themen liessen gemma den Plan nie
# fertig schreiben.
MAP_MAX_TOPICS_TOTAL     = 50
# Themen, die jede Datei in der Themenstufe mindestens bekommt, sonst faellt eine hinten liegende weg.
MAP_MIN_TOPICS_PER_FILE  = 2
# Stellen je Eintrag einer Gliederung, und wie weit ein Bereich wie "12-15" reichen darf.
MAP_MAX_REFS             = 60
MAP_RANGE_MAX            = 40
# Originaltext, den ein Schreibaufruf bekommt. Lesen kostet kaum Zeit, 150k Zeichen
# sind etwa 50.000 Token und passen auch in ein 128k-Fenster.
MAP_MATERIAL_MAX_CHARS   = 150_000
# Ein Plan gibt jeder Datei mindestens ein Viertel ihres Gewichts im Material, sonst
# wird er einmal nachgefordert. Dateien unter einem Zwanzigstel sind ausgenommen.
MAP_FILE_WEIGHT_FLOOR    = 0.25
MAP_MIN_FILE_SHARE       = 0.05
# Stuecke davor und danach, die jede Stelle mitbringt.
MAP_PASSAGE_NEIGHBOURS   = 1
# Kuerzer werden abgeschriebene Anfangsworte nie gesucht, sie stuenden an zu vielen Orten.
MAP_ANKER_MIN_ZEICHEN    = 16
# Verschoben wird nur, wenn so viel der abgeschriebenen Worte dort steht. Ein Inhaltsverzeichnis
# traegt die Ueberschrift, aber nicht den Satz danach.
MAP_ANKER_MIN_ANTEIL     = 0.8
# Was ein Schreibaufruf hoechstens schreiben soll: (270 s - 15 s Lesen) mal 10 Token/s.
SERVICE_WRITE_TOKENS     = 2_500
# Unsere Zeitgrenze je Aufruf, sie muss vor der des Anbieters greifen.
SERVICE_CALL_TIMEOUT_SECONDS = 270

# --- Summary tool -----------------------------------------------------------
SUMMARY_MAX_SOURCES          = 10
# Facts one read call may return, the share of the pool one source gets.
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
# One section per this many characters of facts, the planner gets it as a target.
SUMMARY_CHARS_PER_SECTION    = 4_000
SUMMARY_MIN_SECTIONS         = 3
SUMMARY_MAX_SECTIONS         = 20
# Sections every source gets at least, so no file drops out of the plan.
SUMMARY_SECTIONS_PER_SOURCE  = 2
# Characters of prose one writing call may produce, so several small sections share a call.
# SERVICE_WRITE_TOKENS times three characters, so a group stays inside the five minutes.
SUMMARY_SECTION_GROUP_CHARS  = 6_000
# Measured 20.09.: a section costs about this much prose, plus per fact.
SUMMARY_SECTION_BASE_CHARS   = 600
# Facts one assignment call places. Measured 20.09.: 400 in one answer, no gap, because the
# answer is only two numbers per fact. What a weaker model still drops gets one more call.
# Assignment calls out at once, the answers are applied in the order of the batches.
# A writing call may return this many tokens, a group of sections or the whole fallback text.
# Measured 20.09.: the provider takes 32.000, so 4.000 was cutting long sections for nothing.
# A cap only, a group is planned for SERVICE_WRITE_TOKENS.
SUMMARY_WRITE_MAX_TOKENS     = 4_000
# The shared client cuts reads at 120 s, this tool's calls may take longer.
# Measured 20.09.: myLab drops a call at about 300 s with a bare 500. Ours has to fire
# first, so a long call comes back as a timeout we retry, not as a server error.
SUMMARY_CALL_TIMEOUT_SECONDS = 270
# The watchdog counts silence, so the run reports in this often.
# Writing calls out at once. Measured 20.09. on the real documents: at three the slowest
# call takes 161 s and the provider drops a call at about 300 s, so 139 s are left over.
# At five it is 205 s for 27 percent more throughput, and a provider half as fast kills it.
SUMMARY_WRITE_CONCURRENCY    = 3
# The planner sees this much of each file's beginning, enough for a law's full name and abbreviation.
SUMMARY_SOURCE_OPENING_CHARS = 300
SUMMARY_RETRY_DELAY_SECONDS  = 3
# The waiting time doubles per attempt and stops growing here.
SUMMARY_OUTLINE_MAX_ATTEMPTS = 2
# Load tests 29.09.2026: an outline takes 12 to 30 s, but 2 to 3 of 20 ran on to the 270 s limit at every
# provider in turn, so a cap ends such an answer after about two minutes and the second attempt takes over.
SUMMARY_OUTLINE_MAX_TOKENS   = 4_096
# The fallback call writes the whole document from facts that are already on disk.
# One dropped call would otherwise cost the stage everything it read.
SUMMARY_COMPOSE_MAX_ATTEMPTS = 2

# --- Pages tool ---------------------------------------------------------------
# Pages are kept outside the job pool, so a shared page never vanishes behind newer jobs.
PAGES_MAX_PER_USER       = 50
# What one page may hold, so an edit can never break the layout.
PAGES_MAX_SECTIONS       = 20
PAGES_MAX_BLOCKS         = 4      # blocks per section
PAGES_MAX_IMAGES         = 10
PAGES_MAX_TABLE_ROWS     = 12
PAGES_MAX_TABLE_COLS     = 6
PAGES_MAX_ITEMS          = 10     # bullets, cards, steps, bars and chart categories
PAGES_MAX_SHORT_CHARS    = 120    # headings, labels, table cells
PAGES_MAX_ITEM_CHARS     = 300    # a bullet, a card text, a step text
PAGES_MAX_LONG_CHARS     = 1_500  # leads and running text
# A saved page larger than this is refused, a full page of 20 sections stays far below it.
PAGES_MAX_JSON_BYTES     = 400_000
# Long side of a stored picture, enough for the page's full width on a sharp screen.
PAGES_IMAGE_MAX_PX       = 1_600
PAGES_IMAGE_QUALITY      = 82
# The person's own picture style, long enough for a palette and a manner, short for the prompt.
PAGES_IMAGE_STYLE_MAX_CHARS = 600
# Fewer sections than a summary, a page is read on a screen.
PAGES_SECTIONS           = (4, 10)
# What one section of a page writes, its running text, one further block, lead and terms.
PAGES_SECTION_CHARS      = 2_000
# What one block call of a page writes at most, so several sections share a call.
PAGES_SECTION_GROUP_CHARS = 10_000
# Pictures one page may ever have drawn, the run's and every redraw together.
PAGES_MAX_DRAWS          = 40
# A picture or a language not done after this many minutes counts as failed, its worker is gone.
PAGES_DRAW_WAIT_MINUTES  = 10
PAGES_TRANSLATE_WAIT_MINUTES = 20
# Further languages one page may carry besides its own.
PAGES_MAX_LANGUAGES      = 4
# Texts per translation call, several sections share one.
PAGES_TRANSLATE_BATCH    = 80
# Characters per translation call, the answer stays well inside the call's time limit.
PAGES_TRANSLATE_BATCH_CHARS = 7_000

# A next stage or a resumed job queues behind fresh work of its queue (with Redis 9 is last), so a job that
# keeps running into limits never retakes its slot at once.
CONTINUED_PRIORITY                     = 9

# Longer texts and recordings start in the long queue, under load 95,000 characters took 20 minutes to translate.
LONG_QUEUE_TRANSLATE_CHARS             = 20_000
# A 96-minute lecture holds a process for minutes, a clip of a few minutes for seconds.
LONG_QUEUE_MEDIA_SECONDS               = 20 * 60

# Shared slot pool for all Francis background work, as many as the aia worker has processes.
AIA_PARALLEL_SLOTS                     = 6
# Sources first because every tool waits for them, simulated on the load test of 26.09.2026 as 5 instead of 16 minutes.
AIA_AREA_WEIGHTS                       = {"studio": 1, "ingest": 2}
# A 155-page PDF holds a process at 365 MB, tools mostly wait on the model, so sources take at most half.
AIA_AREA_CAPS                          = {"ingest": 3}

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


# Campus assistant: one question stays readable, one chat stays a conversation, not an archive.
CAMPUS_QUESTION_MAX_CHARS              = 2_000
# Past this many, the oldest question and answer drop out of the chat.
CAMPUS_MAX_QUESTIONS_PER_CHAT          = 50
# The oldest chat makes room once a person holds this many.
CAMPUS_MAX_CHATS_PER_USER              = 100
# Chats without activity for this long are removed nightly, 0 keeps them.
CAMPUS_CHAT_RETENTION_DAYS             = 90
CAMPUS_TITLE_MAX_CHARS                 = 60
# Context for one answer, page chunks are short so this holds about 30 of them.
CAMPUS_CONTEXT_MAX_CHARS               = 40_000
CAMPUS_SEARCH_CANDIDATES               = 60
CAMPUS_SOURCE_CARDS_MAX                = 5
# A source card only for pages an answer sentence lies this close to, measured 0.25 to 0.45 for real use.
CAMPUS_SOURCE_MAX_DISTANCE             = 0.5
# A sentence too far from every passage still gets the one page holding this many of its rare words that no other fetched page holds.
CAMPUS_SOURCE_MIN_RARE_WORDS           = 2
# One place per answer, the first one mentioned, the rest is found on the map.
CAMPUS_PLACE_CARDS_MAX                 = 1
# Web pages the index holds at most, new sitemap links beyond it are left out until pages drop away.
CAMPUS_CRAWL_MAX_PAGES                 = 5_000
# Chunks one web page brings at most, the rest of an overlong page is not indexed.
CAMPUS_PAGE_MAX_CHUNKS                 = 200
CAMPUS_PAGE_MAX_BYTES                  = 5_000_000
CAMPUS_CRAWL_CONCURRENCY               = 4
# Pages the link walk below start addresses reads per night, for sections no sitemap lists.
CAMPUS_LINK_WALK_MAX_PAGES             = 1_000
CAMPUS_FETCH_TIMEOUT_SECONDS           = 20
# A first run over a few thousand pages embeds everything, later nights finish in minutes.
CAMPUS_CRAWL_TIME_LIMIT_SECONDS        = 3600
