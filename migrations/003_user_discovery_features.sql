-- User-facing discovery, favourites, ratings and referral/bonus support.
ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT REFERENCES users(id);
ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_points INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS users_referrer_idx ON users (referrer_id) WHERE referrer_id IS NOT NULL;

ALTER TABLE movies ADD COLUMN IF NOT EXISTS category VARCHAR(48) NOT NULL DEFAULT 'Boshqa';
CREATE INDEX IF NOT EXISTS movies_category_new_idx ON movies (category, created_at DESC) WHERE is_active;

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
