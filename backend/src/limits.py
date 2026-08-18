# -----------------------------------------------------------------------------
# limits.py: central configuration file for all adjustable limits
#
# Change any values here that affect limits, timeouts or quotas.
# All other modules import from here.
#
# Werte, die von der MASCHINE abhängen (Kerne, RAM), stehen absichtlich nicht als
# Zahl hier drin, sondern werden erkannt. Siehe services/system_capacity.py.
# Werte, die vom ANBIETER abhängen, sind gemessene Konstanten. Bewusst keine
# Automatik: wie viel gerade frei ist, hängt an den anderen Projekten der
# Hochschule, und das kann KIS nicht wissen. Bei einer Absage wiederholt der
# jeweilige Aufruf mit wachsender Wartezeit.
# -----------------------------------------------------------------------------

from src.services.system_capacity import capacity

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
# Der Vorrat ist die einzige Aufbewahrungsregel. Es gibt keine Frist mehr: was in
# der Liste steht, bleibt, bis es von neueren Auftraegen verdraengt wird.
MAX_RESULT_FILES            = 20    # jobs kept per user (oldest beyond this is evicted)
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

# --- Screencast -------------------------------------------------------------
MAX_SCREENCAST_SLIDES          = 50
MAX_QUEUED_SCREENCAST_JOBS     = 5  # max jobs in user queue (including running)

# Threads für PDF nach PNG und ffmpeg. Rein rechenlastig, deshalb an den Kernen
# der Maschine bemessen und NICHT mehr von Hand gepflegt. Hier stand jahrelang
# eine 2 mit dem Kommentar "für 4 Kerne", während die Entwicklungsmaschine 18
# Kerne hat: eine Handkonstante veraltet still, eine Erkennung nicht.
# Formel und Container-Fallstricke stehen in services/system_capacity.py.
RENDER_MAX_WORKERS = capacity().render_workers

# Wie viele Folien gleichzeitig vertont werden.
#
# Die Vertonung ist reine Wartezeit am Anbieter, sie kostet keine eigene CPU.
# Sie ist trotzdem der Flaschenhals: gemessen an einem Screencast mit 34 Folien
# entfielen 713 von 734 Sekunden auf die Vertonung, alles andere zusammen auf
# 21 Sekunden.
#
# Durchsatz gegen THL myLab, gemessen 2026-07-27, keine einzige Absage:
#   1 gleichzeitig ->  5,4 Anfragen/min
#   2 gleichzeitig ->  6,8
#   4 gleichzeitig ->  8,2
#   8 gleichzeitig -> 13,0
# Der Anbieter staut ab 8 spürbar (11 s je Anfrage werden zu 32 s), unterm
# Strich bleibt es schneller. Über 8 lohnt es nicht mehr.
#
# Feste Konstante, keine Einstellung. Der Wert ist gemessen, nicht geraten, und
# 8 ist genau das, was auf der Produktionsmaschine bisher im Admin eingestellt
# war. Hier stand als Voreinstellung 4, weil eine falsche Zahl im Admin bis zur
# nächsten Beschwerde falsch blieb. Diese Vorsicht ist mit dem Feld entfallen.
#
# Achtung beim Rechnen: die Zahl gilt JE SCREENCAST. Der screencast-Arbeiter
# nimmt mehrere Aufträge gleichzeitig an (auf 4 Kernen zwei), beim Anbieter
# kommt also das Doppelte an. Bei einer Absage greift die Wiederholung mit
# wachsender Wartezeit in screencast/generation.py.
SCREENCAST_TTS_PARALLELISM = 8

# --- Transkription: gleichzeitig hochgeladene Audio-Teile --------------------
# Eine lange Aufnahme wird in Teile von je 9 Minuten geschnitten. Wie viele
# davon gleichzeitig zum Anbieter gehen, ist der gemessene Wert 2, jetzt als
# Konstante statt als Einstellung. Bei einer Absage wiederholt der Aufruf mit
# wachsender Wartezeit, das reicht.
STT_CHUNK_PARALLELISM = 2

# --- Celery task timeouts (in seconds) --------------------------------------
TTS_SOFT_TIME_LIMIT             = 5400   # 90 min, SoftTimeLimitExceeded -> graceful DB update
TTS_TIME_LIMIT                  = 5520   # 92 min, SIGKILL fallback

# Diese Grenze fängt nur noch Ausreißer. Einen echten Hänger erkennt der Wächter
# schon nach JOB_WATCHDOG_MINUTES ohne Lebenszeichen, dafür braucht es keine
# Gesamtlaufzeit-Grenze. Die zählt nämlich auch bei gesunder Arbeit mit.
#
# Rechnung: die Vertonung kostet gemessen 4,9 s je 100 Zeichen (THL myLab,
# 2026-07-27). Das erlaubte Maximum von SCRIPT_MAX_CHARS entspricht damit rund
# 82 Minuten reiner Sprechzeit, also mehr als die alten 60 Minuten. Eine
# 90-Minuten-Vorlesung als Screencast lief mit dem alten Wert garantiert ins
# Zeitlimit, nach einer Stunde Wartezeit und ohne Ergebnis.
SCREENCAST_SOFT_TIME_LIMIT      = 7200   # 120 min, SoftTimeLimitExceeded -> Job sauber auf failed
SCREENCAST_TIME_LIMIT           = 7320   # 122 min, SIGKILL als letzte Instanz

# Die Werkzeuge des KI-Tutors. Sie standen als nackte Zahlen in den Task-Dekoratoren,
# jeder Wert an einer anderen Stelle.
#
# Ein Übungs-Set ist nicht ein Modell-Aufruf, sondern eine Kette: Generierung, beim
# Grammatik-Quiz ein zweiter Wurf, ein Nachschlag für übersprungene Abschnitte und
# zuletzt der Titel. Bei fünf Quellen sind das vier bis fünf Aufrufe hintereinander.
#
# Gemessen am 2026-08-05 über sieben Sets auf einer schnellen Maschine: 7, 10, 21, 24,
# 47, 61 und 74 Sekunden. Der schlechteste Lauf verbrauchte also schon 74 der alten 120
# Sekunden, und das an einem guten Tag. Das Schreibtempo des Anbieters schwankt gemessen
# um den Faktor 25 (4 bis 200 Zeichen/s), damit reißt derselbe Lauf die alte Grenze ohne
# jeden Fehler im Code. Ein Zeitüberlauf wirft die ganze Arbeit weg, deshalb jetzt so
# grosszügig wie die Mindmap, die dieselbe Art Arbeit macht.
#
# Der Preis ist gering: der Arbeiter skaliert bis 16 Prozesse, ein hängender Auftrag
# blockiert einen davon.
AIA_TOOL_SOFT_TIME_LIMIT        = 300    # 5 min, SoftTimeLimitExceeded -> Set sauber auf failed
AIA_TOOL_TIME_LIMIT             = 360    # 6 min, SIGKILL als letzte Instanz

# Der Zeitplan geht über den ganzen Kurs statt über einen Satz Aufgaben und braucht
# deshalb mehr Luft als die übrigen Werkzeuge.
AIA_SCHEDULE_SOFT_TIME_LIMIT    = 600    # 10 min
AIA_SCHEDULE_TIME_LIMIT         = 720    # 12 min

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
# Per-batch char cap for the ingest-side DOC SUMMARY (aia_summarizer). Sized to keep
# each batch small enough that its summary still carries real detail (the output is
# capped, so a huge batch compresses too hard — see private/summary-batching-erklaert.md).
# 360k chars ≈ ~102k tokens; measured ~23s/call on qwen3-30b (256k ctx). A large doc
# still spills into more batches + a combine call.
# Admin-tunable: ``aia_summary_batch_max_chars``.
AIA_SUMMARY_BATCH_MAX_CHARS            = 360000
# Chunks (input texts) per embedding request at ingest. Higher = fewer requests.
# Measured safe on myLab qwen3-embedding-4b:
# 1000 OK (~13s), 2000 → 502. Each chunk is tiny (~300 tok, well under the
# model's 40k/input limit), so a full 1000-batch is fine.
# BEWUSST KEINE Admin-Einstellung: der frühere Regler hatte Standard UND
# Obergrenze auf diesem Wert, konnte also nur bremsen, und was ein fremder
# Anbieter verträgt, kann im Admin-Bereich niemand wissen. Lehnt ein Endpunkt
# diese Größe ab, halbiert der Client selbst und merkt sich die Zahl, die
# durchging (siehe aia_embeddings._learned_batch_size).
AIA_EMBEDDING_BATCH_SIZE               = 1000
# Zeitschranke fuer die Embeddings der Quellenchips (nachtraegliche Zuordnung).
# Bewusst kuerzer als die 60s des Uploads: hier sitzt jemand vor dem fertig
# geschriebenen Text und wartet nur noch auf die Chips. Ein warmer Aufruf braucht
# deutlich unter einer Sekunde (gemessen 0,2s fuer 31 Zeilen). Laeuft die Schranke
# ab, geht die Antwort ohne Chips raus statt den Text minutenlang festzuhalten.
# 30 und nicht 20, weil der ERSTE Aufruf gegen einen kalten Anbieter 15-50s dauern
# kann (siehe routes/admin/_embedding.py). Bei 20 waere die erste Antwort nach einer
# langen Pause regelmaessig chiplos gewesen, obwohl gar nichts kaputt ist.
AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS  = 30
AIA_WORKSPACE_MAX_ACCESS_LINKS         = 10      # max enrollment links per workspace
AIA_NOTES_MAX_PER_USER              = 100     # max notes per user per workspace
GLOSSARY_LIMIT                        = 150     # max glossary entries per workspace

# --- AI tutor background dispatcher -----------------------------------------
# We manage a shared pool of parallel processing slots for BACKGROUND jobs, NOT
# API quotas (those are the provider's concern, not ours). Chat is NOT in this pool: it runs synchronously in the request, not
# as a background job. The pool covers upload (ingest) and studio tools.
#
# A freed slot goes to an area by weight, then round-robin across users so one
# user can never block the others. Studio outweighs ingest because a student
# actively waits on a studio tool, while uploads process in the background.
#
# Feste Zahl, BEWUSST nicht aus der Maschine abgeleitet. Der Versuch war da und
# ist an drei Dingen gescheitert:
#
# 1. Der Topf ist geteilt, die Erkennung ist es nicht. Das Backend verteilt beim
#    Hochladen, der aia-Arbeiter nach jedem fertigen Auftrag. Der Arbeiter hat
#    aber ein eigenes mem_limit von 1,5 GB und käme damit auf eine ganz andere
#    Zahl als das Backend mit den 8 GB der Maschine. Zwei Prozesse mit
#    verschiedenen Werten am selben Topf: der kleinere gewinnt still, und die
#    Hintergrundarbeit läuft plötzlich der Reihe nach statt parallel.
# 2. Die Grenze, auf die es ankommt, ist die eines ANDEREN Containers. Die
#    Aufträge laufen in kis-celery-aia, nicht hier. Was der eigene Prozess an
#    Speicher sieht, sagt darüber nichts.
# 3. Diese Aufträge WARTEN auf das KI-Modell, sie rechnen nicht. Eine Formel
#    nach Kernen ist die falsche Regel dafür. Derselbe Grund, aus dem der
#    aia-Arbeiter unten mit dem dreifachen der Kernzahl skaliert und nicht mit
#    der Hälfte.
#
# Der Wert 4 ist nicht geraten, er lief bisher so (Einstellung aia_parallel_slots)
# und verträgt sich nachweislich mit dem 1,5-GB-Limit des Arbeiters.
AIA_PARALLEL_SLOTS                     = 4
AIA_AREA_WEIGHTS                       = {"studio": 2, "ingest": 1}

# Max simultaneous source uploads in the HTTP layer (the streaming + convert +
# store phase). Caps RAM/CPU when several people upload large media at once.
# Ebenfalls erkannt statt eingestellt: die schwere Phase startet LibreOffice und
# ffmpeg, der Bedarf hängt an Kernen UND Speicher, nicht an einer Meinung.
AIA_MAX_CONCURRENT_UPLOADS             = capacity().max_concurrent_uploads

# Zeichen je Sprachausgabe-Anfrage. Nicht die Grenze des Modells, sondern die
# Zeitgrenze davor: gemessen an THL myLab (2026-07-27) bricht jede Anfrage nach
# genau 60 Sekunden mit HTTP 500 ab, unabhängig vom Inhalt.
#
#   100 Zeichen ->  6,0 s   OK
#   300 Zeichen -> 19,3 s   OK
#   600 Zeichen -> 59,9 s   gerade noch
#  1000 Zeichen -> 60,1 s   HTTP 500
#
# Der Aufwand wächst überproportional, deshalb liegt der Standard deutlich
# unter der gemessenen Kante. Ein Screencast-Skript hat 1500 bis 2000 Zeichen
# und ging vorher als eine einzige Anfrage raus, also immer in den Timeout.
# Admin-Einstellung zur Laufzeit: tts_max_chars_per_request.
TTS_MAX_CHARS_PER_REQUEST              = 400


# ── Nebenläufigkeit im Web-Prozess ───────────────────────────────────────────
# Die meisten Routen sind mit `def` deklariert, nicht `async def`. FastAPI führt
# solche Routen in einem Threadpool aus, statt sie in den Event-Loop zu legen.
# Das ist Absicht: sie rufen psycopg2, ldap3 und httpx blockierend auf, und in
# einer `async def`-Route würde ein einziger dieser Aufrufe den kompletten
# Prozess anhalten, also alle anderen Nutzer gleich mit.
#
# Die beiden Werte gehören zusammen und dürfen nicht getrennt geändert werden:
# jeder Thread kann eine DB-Verbindung belegen, und ThreadedConnectionPool
# BLOCKIERT NICHT, wenn er leer ist, sondern wirft PoolError. Der Threadpool muss
# deshalb kleiner bleiben als der Verbindungsvorrat, sonst bekommen Nutzer unter
# Last 500er statt kurz zu warten.
REQUEST_THREAD_LIMIT                   = 32
DB_POOL_MAX_CONNECTIONS                = 40


# ── Datenbank-Sicherung ──────────────────────────────────────────────────────
# Naechtlicher pg_dump in den Objektspeicher, zusaetzlich zu den taeglichen
# Hetzner-Snapshots. Der Unterschied: ein Snapshot dreht immer den GANZEN Server
# zurueck, ein Dump erlaubt es, einzelne Tabellen oder Zeilen zu retten, ohne
# alles seit dem Snapshot zu verlieren.
#
# Gemessen am 2026-07-30 bei 138.511 Textabschnitten: 1,6 GB je Sicherung im
# komprimierten Format, Dauer 121 Sekunden. Der Hauptteil sind die
# Einbettungsvektoren in aia_chunks (2,7 GB in der Datenbank). Die sind bewusst
# MIT drin: sie liessen sich zwar neu berechnen, aber nur ueber viele
# Modell-Aufrufe.
#
# Gestaffelt aufbewahrt, weil manche Fehler erst nach Wochen auffallen. Nur
# taegliche Sicherungen wuerden bedeuten: was vor drei Wochen still kaputtging,
# ist nicht mehr rettbar.
#   backups/daily/    7 Stueck  -> etwa 11 GB
#   backups/weekly/   5 Stueck  -> etwa  8 GB
#   backups/monthly/ 12 Stueck  -> etwa 18 GB
# Zusammen etwa 37 GB im Bucket, also weiter Centbetraege im Monat.
#
# Die Wochenstufe ist nicht schmueckendes Beiwerk, sie schliesst eine echte
# Luecke. Ohne sie deckt die Aufbewahrung am 30. eines Monats nur den 24. bis 30.
# ab plus den Monatsersten. Vom 2. bis zum 23. gaebe es nichts, ein Fehler vom
# 10. waere am 30. nicht mehr rettbar.
#
# Die Wochen- und Monatskopien entstehen als serverseitige Kopie im Bucket, die
# 1,5 GB gehen also nicht mehrfach ueber die Leitung.
#
# Entspricht dem verbreiteten Grossvater-Vater-Sohn-Schema: taeglich 7 bis 14,
# woechentlich 4 bis 6, monatlich 12 bis 24.
DB_BACKUP_KEEP_DAYS                    = 7
DB_BACKUP_KEEP_WEEKS                   = 5
DB_BACKUP_KEEP_MONTHS                  = 12
# Grosszuegig, damit die Sicherung nie mitten drin abgeschnitten wird. Gemessen
# waren es 121 Sekunden, auf einer langsameren Maschine entsprechend mehr.
DB_BACKUP_TIME_LIMIT_SECONDS           = 3600
