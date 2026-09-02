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
