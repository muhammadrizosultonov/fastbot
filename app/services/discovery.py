from datetime import datetime, timedelta, timezone
from redis.asyncio import Redis

from app.repositories.models import Movie
from app.repositories.movies import MovieRepository

TRACKED_SECTIONS = [
    "🆕 Yangi videolar",
    "🎲 Tasodifiy video",
    "🔥 Eng mashhurlar",
    "❤️ Sevimlilar",
    "⭐ TOP reyting",
    "🎁 Bonuslar",
    "🎭 Kategoriyalar",
    "⭐ Baholash",
    "👥 Do'st taklif qilish",
    "🔎 Qidirish",
]


class DiscoveryService:
    POPULAR_KEY = "movies:popular:v1"
    SECTIONS_COUNT_KEY = "stats:sections:count:v1"
    SECTIONS_USERS_KEY = "stats:sections:users:v1:"
    VIEWS_TOTAL_KEY = "stats:views:total:v1"
    VIEWS_DAILY_KEY = "stats:views:daily:v1:"
    VIEWS_USERS_DAILY_KEY = "stats:views:users:daily:v1:"
    VIEWS_USERS_7D_KEY = "stats:views:users:7d:v1"

    def __init__(self, redis: Redis, movies: MovieRepository) -> None:
        self.redis, self.movies = redis, movies

    async def record_view(self, code: str, user_id: int | None = None) -> None:
        try:
            await self.redis.zincrby(self.POPULAR_KEY, 1, str(code))
            await self.redis.incr(self.VIEWS_TOTAL_KEY)

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await self.redis.incr(f"{self.VIEWS_DAILY_KEY}{today_str}")

            if user_id is not None:
                uid_str = str(user_id)
                await self.redis.pfadd(f"{self.VIEWS_USERS_DAILY_KEY}{today_str}", uid_str)
                await self.redis.pfadd(self.VIEWS_USERS_7D_KEY, uid_str)
        except Exception:
            pass

    async def track_section(self, section: str, user_id: int | None = None) -> None:
        try:
            await self.redis.hincrby(self.SECTIONS_COUNT_KEY, section, 1)
            if user_id is not None:
                await self.redis.pfadd(f"{self.SECTIONS_USERS_KEY}{section}", str(user_id))
        except Exception:
            pass

    async def popular(self, limit: int = 10) -> list[Movie]:
        try:
            codes = await self.redis.zrevrange(self.POPULAR_KEY, 0, limit - 1)
            clean_codes = [c.decode() if isinstance(c, bytes) else str(c) for c in codes]
            movies = await self.movies.list_by_codes(clean_codes)
            return movies or await self.movies.list_new(limit)
        except Exception:
            return await self.movies.list_new(limit)

    async def build_stats_report(self, db_stats: dict[str, int | float]) -> str:
        # 1. 24h & 7d Views and Unique Viewers
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")

        try:
            views_24h_raw = await self.redis.get(f"{self.VIEWS_DAILY_KEY}{today_str}")
            views_24h = int(views_24h_raw) if views_24h_raw else 0
        except Exception:
            views_24h = 0

        try:
            views_24h_users = int(await self.redis.pfcount(f"{self.VIEWS_USERS_DAILY_KEY}{today_str}") or 0)
        except Exception:
            views_24h_users = 0

        views_7d = 0
        try:
            for i in range(7):
                d_str = (now_utc - timedelta(days=i)).strftime("%Y-%m-%d")
                c = await self.redis.get(f"{self.VIEWS_DAILY_KEY}{d_str}")
                if c:
                    views_7d += int(c)
        except Exception:
            pass
        views_7d = max(views_7d, views_24h)

        try:
            views_7d_users = int(await self.redis.pfcount(self.VIEWS_USERS_7D_KEY) or 0)
        except Exception:
            views_7d_users = 0
        views_7d_users = max(views_7d_users, views_24h_users)

        try:
            total_views_raw = await self.redis.get(self.VIEWS_TOTAL_KEY)
            total_views = int(total_views_raw) if total_views_raw else views_7d
        except Exception:
            total_views = views_7d

        # 2. Top Kodlar (7 kun)
        top_codes_tuples = []
        try:
            top_codes_tuples = await self.redis.zrevrange(self.POPULAR_KEY, 0, 4, withscores=True)
        except Exception:
            pass

        medals = ["🥇", "🥈", "🥉", "4.", "5."]
        if top_codes_tuples:
            top_lines = []
            for idx, item in enumerate(top_codes_tuples):
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    code, score = item
                else:
                    code, score = item, 0
                code_str = code.decode() if isinstance(code, bytes) else str(code)
                medal = medals[idx] if idx < len(medals) else f"{idx+1}."
                top_lines.append(f"{medal} {code_str} — {int(float(score)):,}")
            top_codes_str = "\n".join(top_lines)
        else:
            top_codes_str = "• Hozircha ma'lumot yo'q"

        # 3. Bo'limlardan foydalanish (7 kun)
        section_lines = []
        for sec in TRACKED_SECTIONS:
            sec_count = 0
            sec_users = 0
            try:
                val = await self.redis.hget(self.SECTIONS_COUNT_KEY, sec)
                if val:
                    sec_count = int(val)
                sec_users = int(await self.redis.pfcount(f"{self.SECTIONS_USERS_KEY}{sec}") or 0)
            except Exception:
                pass
            section_lines.append(f"• {sec}: {sec_count:,}  ({sec_users:,} kishi)")
        sections_str = "\n".join(section_lines)

        # 4. Tashkent Time
        tashkent_tz = timezone(timedelta(hours=5))
        tashkent_now = datetime.now(tashkent_tz).strftime("%d.%m.%Y %H:%M")

        total_users = int(db_stats.get("total_users", 0))
        new_24h = int(db_stats.get("new_24h", 0))
        new_7d = int(db_stats.get("new_7d", 0))
        active_24h = int(db_stats.get("active_24h", 0))
        active_7d = int(db_stats.get("active_7d", 0))
        active_30d = int(db_stats.get("active_30d", 0))
        blocked_users = int(db_stats.get("blocked_users", 0))
        total_referrals = int(db_stats.get("total_referrals", 0))
        referrals_24h = int(db_stats.get("referrals_24h", 0))
        referrers_count = int(db_stats.get("referrers_count", 0))
        total_movies = int(db_stats.get("total_movies", 0))
        new_movies_7d = int(db_stats.get("new_movies_7d", 0))
        total_channels = int(db_stats.get("total_channels", 0))
        total_ratings = int(db_stats.get("total_ratings", 0))
        ratings_users = int(db_stats.get("ratings_users", 0))
        ratings_24h = int(db_stats.get("ratings_24h", 0))
        avg_rating = float(db_stats.get("avg_rating", 0.0))

        report = (
            "📊 <b>Statistika</b>\n\n"
            f"👥 <b>Jami foydalanuvchilar:</b> {total_users:,}\n\n"
            "🆕 <b>Yangi kirganlar</b>\n"
            f"• 24 soat: {new_24h:,}\n"
            f"• 7 kun: {new_7d:,}\n\n"
            "🟢 <b>Faol foydalanuvchilar</b>\n"
            f"• 24 soat: {active_24h:,}\n"
            f"• 7 kun: {active_7d:,}\n\n"
            "🎬 <b>So'ralgan kinolar</b>\n"
            f"• 24 soat: {views_24h:,}  ({views_24h_users:,} kishi)\n"
            f"• 7 kun: {views_7d:,}  ({views_7d_users:,} kishi)\n\n"
            "🔥 <b>Top kodlar (7 kun)</b>\n"
            f"{top_codes_str}\n\n"
            "👥 <b>Referral</b>\n"
            f"• Havola orqali kelganlar: {total_referrals:,}\n"
            f"• Shundan 24 soatda: {referrals_24h:,}\n"
            f"• Taklif qilayotganlar: {referrers_count:,}\n\n"
            "📂 <b>Bo'limlardan foydalanish (7 kun)</b>\n"
            f"{sections_str}\n\n"
            "🎬 <b>Ko'rishlar va faollik</b>\n"
            f"• 24 soatda ko'rilgan: {views_24h:,}  ({views_24h_users:,} kishi)\n"
            f"• 7 kunda ko'rilgan: {views_7d:,}  ({views_7d_users:,} kishi)\n"
            f"• 30 kunda faol: {active_30d:,} kishi\n"
            f"• 🆕 7 kunda qo'shilgan video: {new_movies_7d:,}\n\n"
            "🏅 <b>Reyting</b>\n"
            f"• Jami ovoz: {total_ratings:,}  ({ratings_users:,} kishi)\n"
            f"• 24 soatda: {ratings_24h:,} ovoz\n"
            f"• Umumiy o'rtacha: {avg_rating:.2f} / 5\n\n"
            "📦 <b>Baza</b>\n"
            f"🎬 Kinolar: {total_movies:,}\n"
            f"📡 Majburiy kanallar: {total_channels:,}\n"
            f"👁 Jami ko'rishlar: {total_views:,}\n"
            f"🚫 Botni bloklaganlar: {blocked_users:,}\n\n"
            f"<i>Yangilandi: {tashkent_now} (Toshkent)</i>"
        )
        return report
