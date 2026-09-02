import glob
import logging
import os
import asyncpg

log = logging.getLogger(__name__)

INITIAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255) NOT NULL DEFAULT '',
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    age_confirmed BOOLEAN NOT NULL DEFAULT false,
    referrer_id BIGINT REFERENCES users(id),
    bonus_points INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS users_active_seen_idx ON users (last_seen_at DESC) WHERE NOT is_blocked;
CREATE INDEX IF NOT EXISTS users_referrer_idx ON users (referrer_id) WHERE referrer_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS movies (
    code VARCHAR(64) PRIMARY KEY,
    file_id TEXT NOT NULL,
    title VARCHAR(255),
    caption TEXT,
    category VARCHAR(48) NOT NULL DEFAULT 'Boshqa',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS movies_active_code_idx ON movies (code) WHERE is_active;
CREATE INDEX IF NOT EXISTS movies_category_new_idx ON movies (category, created_at DESC) WHERE is_active;
CREATE INDEX IF NOT EXISTS movies_title_prefix_idx ON movies (lower(title) text_pattern_ops) WHERE is_active AND title IS NOT NULL;

CREATE TABLE IF NOT EXISTS required_channels (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(128) NOT NULL,
    invite_link TEXT,
    is_join_request BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    sort_order SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admins (
    user_id BIGINT PRIMARY KEY,
    permissions INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS broadcast_jobs (
    id BIGSERIAL PRIMARY KEY,
    creator_id BIGINT NOT NULL REFERENCES users(id),
    source_chat_id BIGINT NOT NULL,
    source_message_id BIGINT NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'preparing',
    progress_chat_id BIGINT,
    progress_message_id BIGINT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS broadcast_jobs_queued_idx ON broadcast_jobs (id) WHERE status = 'queued';

CREATE TABLE IF NOT EXISTS broadcast_deliveries (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES broadcast_jobs(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    attempts SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    UNIQUE (job_id, user_id)
);
CREATE INDEX IF NOT EXISTS broadcast_claim_idx
    ON broadcast_deliveries (job_id, status, next_attempt_at, id)
    WHERE status IN ('pending', 'retry');

CREATE TABLE IF NOT EXISTS movie_favorites (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    movie_code VARCHAR(64) NOT NULL REFERENCES movies(code) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, movie_code)
);
CREATE INDEX IF NOT EXISTS movie_favorites_user_created_idx ON movie_favorites (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS movie_ratings (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    movie_code VARCHAR(64) NOT NULL REFERENCES movies(code) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, movie_code)
);
CREATE INDEX IF NOT EXISTS movie_ratings_movie_idx ON movie_ratings (movie_code, rating DESC);
"""


async def run_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        try:
            await conn.execute(INITIAL_SCHEMA_SQL)
        except Exception as e:
            log.warning("Initial schema execution warning: %s", e)

        # Also apply any extra SQL files in migrations/ directory if present
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "migrations")
        if os.path.exists(migrations_dir):
            files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
            for file in files:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        sql = f.read()
                    if sql.strip():
                        await conn.execute(sql)
                except Exception as e:
                    log.warning("Migration warning for %s: %s", file, e)


async def create_pool(dsn: str, min_size: int, max_size: int) -> asyncpg.Pool:
    """A small pool per process prevents connection exhaustion after horizontal scaling."""

    async def init_connection(connection: asyncpg.Connection) -> None:
        await connection.execute("SET TIME ZONE 'UTC'")
        await connection.execute("SET statement_timeout = '5000ms'")

    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        max_queries=50_000,
        max_inactive_connection_lifetime=300,
        command_timeout=6,
        init=init_connection,
    )
    await run_migrations(pool)
    return pool
