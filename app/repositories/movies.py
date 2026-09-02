import asyncpg

from app.repositories.models import Movie


class MovieRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def get_by_code(self, code: str) -> Movie | None:
        row = await self.pool.fetchrow(
            "SELECT code, file_id, title, caption, created_at, category FROM movies WHERE code = $1 AND is_active",
            code,
        )
        return Movie(**dict(row)) if row else None

    async def upsert(self, movie: Movie) -> None:
        await self.pool.execute(
            """INSERT INTO movies (code, file_id, title, caption, category)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (code) DO UPDATE SET file_id=EXCLUDED.file_id, title=EXCLUDED.title,
                   caption=EXCLUDED.caption, category=EXCLUDED.category, is_active=true, updated_at=now()""",
            movie.code,
            movie.file_id,
            movie.title,
            movie.caption,
            movie.category,
        )

    async def delete(self, code: str) -> bool:
        result = await self.pool.execute("UPDATE movies SET is_active=false WHERE code=$1", code)
        return result.endswith("1")

    async def count_active(self) -> int:
        return await self.pool.fetchval("SELECT count(*) FROM movies WHERE is_active") or 0

    async def list_paginated(self, limit: int = 5, offset: int = 0) -> tuple[list[Movie], int]:
        total = await self.count_active()
        rows = await self.pool.fetch(
            "SELECT code, file_id, title, caption, created_at, category FROM movies WHERE is_active ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
        return [Movie(**dict(row)) for row in rows], total

    async def list_new(self, limit: int = 10) -> list[Movie]:
        return await self._list("ORDER BY created_at DESC LIMIT $1", limit)

    async def search_by_title(self, query: str, limit: int = 10) -> list[Movie]:
        cleaned = query.strip()
        if not cleaned:
            return []
        rows = await self.pool.fetch(
            """SELECT code, file_id, title, caption, created_at, category FROM movies
               WHERE is_active AND (
                   lower(code) = lower($1)
                   OR lower(title) LIKE '%' || lower($1) || '%'
                   OR (caption IS NOT NULL AND lower(caption) LIKE '%' || lower($1) || '%')
               )
               ORDER BY
                   CASE
                       WHEN lower(code) = lower($1) THEN 1
                       WHEN lower(title) LIKE lower($1) || '%' THEN 2
                       WHEN lower(title) LIKE '%' || lower($1) || '%' THEN 3
                       ELSE 4
                   END,
                   created_at DESC
               LIMIT $2""",
            cleaned, limit,
        )
        return [Movie(**dict(row)) for row in rows]

    async def list_by_codes(self, codes: list[str]) -> list[Movie]:
        if not codes:
            return []
        rows = await self.pool.fetch(
            "SELECT code, file_id, title, caption, created_at, category FROM movies WHERE is_active AND code = ANY($1::varchar[])",
            codes,
        )
        by_code = {str(row["code"]): Movie(**dict(row)) for row in rows}
        return [by_code[code] for code in codes if code in by_code]

    async def random(self) -> Movie | None:
        total = await self.pool.fetchval("SELECT count(*) FROM movies WHERE is_active")
        if not total:
            return None
        row = await self.pool.fetchrow(
            """SELECT code, file_id, title, caption, created_at, category FROM movies
               WHERE is_active ORDER BY code OFFSET floor(random() * $1)::int LIMIT 1""",
            int(total),
        )
        return Movie(**dict(row)) if row else None

    async def categories(self) -> list[tuple[str, int]]:
        rows = await self.pool.fetch(
            """SELECT category, count(*)::int AS count FROM movies WHERE is_active
               GROUP BY category ORDER BY count DESC, category LIMIT 20"""
        )
        return [(str(row["category"]), int(row["count"])) for row in rows]

    async def list_category(self, category: str, limit: int = 10) -> list[Movie]:
        rows = await self.pool.fetch(
            """SELECT code, file_id, title, caption, created_at, category FROM movies
               WHERE is_active AND category=$1 ORDER BY created_at DESC LIMIT $2""",
            category, limit,
        )
        return [Movie(**dict(row)) for row in rows]

    async def is_favorite(self, user_id: int, code: str) -> bool:
        return bool(
            await self.pool.fetchval(
                "SELECT 1 FROM movie_favorites WHERE user_id=$1 AND movie_code=$2",
                user_id, code,
            )
        )

    async def toggle_favorite(
        self,
        user_id: int,
        code: str,
        username: str | None = None,
        full_name: str | None = None,
    ) -> bool:
        """True means it was added; DELETE first makes the common unfavorite path cheap."""
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """INSERT INTO users (id, username, full_name) VALUES ($1, $2, $3)
                   ON CONFLICT (id) DO NOTHING""",
                user_id, username, (full_name or "")[:255],
            )
            removed = await connection.fetchval(
                "DELETE FROM movie_favorites WHERE user_id=$1 AND movie_code=$2 RETURNING 1", user_id, code
            )
            if removed:
                return False
            await connection.execute(
                "INSERT INTO movie_favorites (user_id, movie_code) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                user_id, code,
            )
            return True

    async def favorites(self, user_id: int, limit: int = 20) -> list[Movie]:
        rows = await self.pool.fetch(
            """SELECT m.code, m.file_id, m.title, m.caption, m.created_at, m.category
               FROM movie_favorites f JOIN movies m ON m.code=f.movie_code
               WHERE f.user_id=$1 AND m.is_active ORDER BY f.created_at DESC LIMIT $2""",
            user_id, limit,
        )
        return [Movie(**dict(row)) for row in rows]

    async def rate(
        self,
        user_id: int,
        code: str,
        rating: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> None:
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """INSERT INTO users (id, username, full_name) VALUES ($1, $2, $3)
                   ON CONFLICT (id) DO NOTHING""",
                user_id, username, (full_name or "")[:255],
            )
            await connection.execute(
                """INSERT INTO movie_ratings (user_id, movie_code, rating) VALUES ($1,$2,$3)
                   ON CONFLICT (user_id, movie_code) DO UPDATE SET rating=EXCLUDED.rating, updated_at=now()""",
                user_id, code, rating,
            )

    async def get_rating_info(self, code: str, user_id: int | None = None) -> tuple[float, int, int | None]:
        """Returns (avg_rating, votes_count, user_rating)."""
        row = await self.pool.fetchrow(
            """SELECT COALESCE(ROUND(AVG(r.rating)::numeric, 1), 0)::float AS avg_rating,
                      COUNT(r.user_id)::int AS votes_count,
                      MAX(CASE WHEN r.user_id = $2 THEN r.rating ELSE NULL END) AS user_rating
               FROM movie_ratings r
               WHERE r.movie_code = $1""",
            code, user_id,
        )
        if not row:
            return 0.0, 0, None
        return float(row["avg_rating"]), int(row["votes_count"]), row["user_rating"]

    async def top_rated(self, limit: int = 10) -> list[Movie]:
        rows = await self.pool.fetch(
            """SELECT m.code, m.file_id, m.title, m.caption, m.created_at, m.category
               FROM movies m LEFT JOIN movie_ratings r ON r.movie_code=m.code
               WHERE m.is_active GROUP BY m.code
               ORDER BY COALESCE(avg(r.rating), 0) DESC, count(r.user_id) DESC, m.created_at DESC LIMIT $1""",
            limit,
        )
        return [Movie(**dict(row)) for row in rows]

    async def _list(self, order_clause: str, limit: int) -> list[Movie]:
        rows = await self.pool.fetch(
            f"SELECT code, file_id, title, caption, created_at, category FROM movies WHERE is_active {order_clause}", limit
        )
        return [Movie(**dict(row)) for row in rows]
