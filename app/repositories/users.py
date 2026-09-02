import asyncpg


class UserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def upsert(self, user_id: int, username: str | None, full_name: str) -> None:
        await self.pool.execute(
            """
            INSERT INTO users (id, username, full_name, last_seen_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username, full_name = EXCLUDED.full_name,
                last_seen_at = now(), is_blocked = false
            """,
            user_id,
            username,
            full_name[:255],
        )

    async def ensure_exists(self, user_id: int, username: str | None = None, full_name: str | None = None) -> None:
        """Used before writes with a users FK when Redis session state outlives the database."""
        await self.pool.execute(
            """INSERT INTO users (id, username, full_name) VALUES ($1, $2, $3)
               ON CONFLICT (id) DO NOTHING""",
            user_id, username, (full_name or "")[:255],
        )

    async def mark_blocked(self, user_id: int) -> None:
        await self.pool.execute("UPDATE users SET is_blocked = true WHERE id = $1", user_id)

    async def is_age_confirmed(self, user_id: int) -> bool:
        return bool(await self.pool.fetchval("SELECT age_confirmed FROM users WHERE id = $1", user_id))

    async def confirm_age(self, user_id: int) -> None:
        await self.pool.execute(
            """INSERT INTO users (id, age_confirmed) VALUES ($1, true)
               ON CONFLICT (id) DO UPDATE SET age_confirmed = true""",
            user_id,
        )

    async def stats(self) -> tuple[int, int, int]:
        row = await self.pool.fetchrow(
            """SELECT count(*)::bigint AS total,
                      count(*) FILTER (WHERE last_seen_at >= now() - interval '1 day')::bigint AS daily,
                      count(*) FILTER (WHERE last_seen_at >= now() - interval '30 days')::bigint AS monthly
               FROM users WHERE NOT is_blocked"""
        )
        return (int(row["total"]), int(row["daily"]), int(row["monthly"])) if row else (0, 0, 0)

    async def get_comprehensive_stats(self) -> dict[str, int | float]:
        res: dict[str, int | float] = {
            "total_users": 0, "new_24h": 0, "new_7d": 0,
            "active_24h": 0, "active_7d": 0, "active_30d": 0,
            "blocked_users": 0, "total_referrals": 0,
            "referrals_24h": 0, "referrers_count": 0,
            "total_movies": 0, "new_movies_7d": 0,
            "total_channels": 0, "total_ratings": 0,
            "ratings_users": 0, "ratings_24h": 0,
            "avg_rating": 0.0,
        }
        try:
            user_row = await self.pool.fetchrow(
                """
                SELECT
                    count(*)::bigint AS total_users,
                    count(*) FILTER (WHERE created_at >= now() - interval '24 hours')::bigint AS new_24h,
                    count(*) FILTER (WHERE created_at >= now() - interval '7 days')::bigint AS new_7d,
                    count(*) FILTER (WHERE last_seen_at >= now() - interval '24 hours' AND NOT is_blocked)::bigint AS active_24h,
                    count(*) FILTER (WHERE last_seen_at >= now() - interval '7 days' AND NOT is_blocked)::bigint AS active_7d,
                    count(*) FILTER (WHERE last_seen_at >= now() - interval '30 days' AND NOT is_blocked)::bigint AS active_30d,
                    count(*) FILTER (WHERE is_blocked)::bigint AS blocked_users,
                    count(*) FILTER (WHERE referrer_id IS NOT NULL)::bigint AS total_referrals,
                    count(*) FILTER (WHERE referrer_id IS NOT NULL AND created_at >= now() - interval '24 hours')::bigint AS referrals_24h,
                    count(DISTINCT referrer_id)::bigint AS referrers_count
                FROM users
                """
            )
            if user_row:
                for k, v in user_row.items():
                    if v is not None:
                        res[k] = int(v)
        except Exception:
            pass

        try:
            movie_row = await self.pool.fetchrow(
                """
                SELECT
                    count(*)::bigint AS total_movies,
                    count(*) FILTER (WHERE created_at >= now() - interval '7 days')::bigint AS new_movies_7d
                FROM movies WHERE is_active
                """
            )
            if movie_row:
                res["total_movies"] = int(movie_row["total_movies"] or 0)
                res["new_movies_7d"] = int(movie_row["new_movies_7d"] or 0)
        except Exception:
            pass

        try:
            channel_count = await self.pool.fetchval("SELECT count(*)::bigint FROM required_channels WHERE is_active")
            if channel_count is not None:
                res["total_channels"] = int(channel_count)
        except Exception:
            pass

        try:
            rating_row = await self.pool.fetchrow(
                """
                SELECT
                    count(*)::bigint AS total_ratings,
                    count(DISTINCT user_id)::bigint AS ratings_users,
                    count(*) FILTER (WHERE created_at >= now() - interval '24 hours')::bigint AS ratings_24h,
                    COALESCE(ROUND(AVG(rating)::numeric, 2), 0)::float AS avg_rating
                FROM movie_ratings
                """
            )
            if rating_row:
                res["total_ratings"] = int(rating_row["total_ratings"] or 0)
                res["ratings_users"] = int(rating_row["ratings_users"] or 0)
                res["ratings_24h"] = int(rating_row["ratings_24h"] or 0)
                res["avg_rating"] = float(rating_row["avg_rating"] or 0.0)
        except Exception:
            pass

        return res

    async def create_broadcast_deliveries(self, job_id: int) -> None:
        # One set-based query is substantially cheaper than loading users into Python.
        await self.pool.execute(
            """INSERT INTO broadcast_deliveries (job_id, user_id)
               SELECT $1, id FROM users WHERE NOT is_blocked
               ON CONFLICT DO NOTHING""",
            job_id,
        )

    async def apply_referral(self, user_id: int, referrer_id: int) -> bool:
        """Award only once, after the referred user passes the age gate."""
        if user_id == referrer_id:
            return False
        async with self.pool.acquire() as connection, connection.transaction():
            linked = await connection.fetchval(
                """UPDATE users SET referrer_id=$2 WHERE id=$1 AND referrer_id IS NULL
                   AND EXISTS (SELECT 1 FROM users WHERE id=$2)
                   RETURNING id""",
                user_id, referrer_id,
            )
            if linked is None:
                return False
            await connection.execute("UPDATE users SET bonus_points=bonus_points+10 WHERE id=$1", referrer_id)
            return True

    async def bonus_summary(self, user_id: int) -> tuple[int, int]:
        row = await self.pool.fetchrow(
            """SELECT u.bonus_points, count(r.id)::int AS referral_count
               FROM users u LEFT JOIN users r ON r.referrer_id=u.id
               WHERE u.id=$1 GROUP BY u.id""",
            user_id,
        )
        return (int(row["bonus_points"]), int(row["referral_count"])) if row else (0, 0)
