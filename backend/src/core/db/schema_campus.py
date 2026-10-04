"""Tables of the campus assistant: crawled pages, their chunks, places of the map, chats."""
import logging

from src.core.db.pool import get_connection

_log = logging.getLogger(__name__)

# The hnsw index covers one embedding width, the same one the assistant uses.
CAMPUS_EMBED_INDEX_DIM = 2560


def create_campus_tables(cur) -> None:
    """Idempotent DDL, runs inside the main init transaction."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_pages (
            id             SERIAL PRIMARY KEY,
            kind           TEXT NOT NULL,
            url            TEXT UNIQUE,
            title          TEXT,
            filename       TEXT,
            file_path      TEXT,
            etag           TEXT,
            last_modified  TEXT,
            content_hash   TEXT,
            status         TEXT NOT NULL DEFAULT 'pending',
            error_message  TEXT,
            chunk_count    INTEGER NOT NULL DEFAULT 0,
            fetched_at     TIMESTAMP,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_campus_pages_kind ON campus_pages (kind, status)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_excluded_urls (
            url         TEXT PRIMARY KEY,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_chunks (
            id             SERIAL PRIMARY KEY,
            page_id        INTEGER NOT NULL REFERENCES campus_pages(id) ON DELETE CASCADE,
            position       INTEGER NOT NULL,
            heading        TEXT,
            content        TEXT NOT NULL,
            embedding      vector,
            search_vector  tsvector
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_campus_chunks_search ON campus_chunks USING gin(search_vector)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_campus_chunks_page ON campus_chunks (page_id, position)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_places (
            id             TEXT PRIMARY KEY,
            code           TEXT,
            kind           TEXT NOT NULL,
            title          JSONB NOT NULL,
            description    JSONB,
            opening_hours  JSONB,
            facilities     JSONB,
            terms          JSONB,
            link           JSONB,
            updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_chats (
            id              SERIAL PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            question_count  INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_campus_chats_user ON campus_chats (user_id, updated_at DESC)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_messages (
            id          SERIAL PRIMARY KEY,
            chat_id     INTEGER NOT NULL REFERENCES campus_chats(id) ON DELETE CASCADE,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            sources     JSONB,
            places      JSONB,
            no_source   BOOLEAN NOT NULL DEFAULT FALSE,
            feedback    SMALLINT NOT NULL DEFAULT 0,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_campus_messages_chat ON campus_messages (chat_id, id)")


def create_campus_hnsw() -> None:
    """Vector index in its own transaction, a failure only costs speed."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SET LOCAL max_parallel_maintenance_workers = 0")
                cur.execute("SET LOCAL maintenance_work_mem = '256MB'")
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_campus_chunks_embedding_hnsw
                    ON campus_chunks USING hnsw ((embedding::halfvec({CAMPUS_EMBED_INDEX_DIM})) halfvec_cosine_ops)
                    WHERE vector_dims(embedding) = {CAMPUS_EMBED_INDEX_DIM}
                """)
                conn.commit()
            except Exception as e:
                conn.rollback()
                _log.warning("campus hnsw index skipped/failed: {}", e)
