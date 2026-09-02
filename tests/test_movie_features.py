import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

# Stub third-party dependencies if running in minimal testing environment
if "aiogram" not in sys.modules:
    aiogram_mock = MagicMock()
    
    class InlineKeyboardButton:
        def __init__(self, text: str, callback_data: str | None = None, url: str | None = None):
            self.text = text
            self.callback_data = callback_data
            self.url = url

    class InlineKeyboardMarkup:
        def __init__(self, inline_keyboard: list[list[InlineKeyboardButton]]):
            self.inline_keyboard = inline_keyboard

    class Message:
        pass

    class CallbackQuery:
        pass

    class ParseMode:
        HTML = "HTML"

    class ChatMemberStatus:
        CREATOR = "creator"
        ADMINISTRATOR = "administrator"
        MEMBER = "member"
        RESTRICTED = "restricted"
        LEFT = "left"
        KICKED = "kicked"

    types_mock = SimpleNamespace(
        InlineKeyboardButton=InlineKeyboardButton,
        InlineKeyboardMarkup=InlineKeyboardMarkup,
        Message=Message,
        CallbackQuery=CallbackQuery,
    )
    enums_mock = SimpleNamespace(ParseMode=ParseMode, ChatMemberStatus=ChatMemberStatus)
    exceptions_mock = SimpleNamespace(
        TelegramBadRequest=Exception,
        TelegramForbiddenError=Exception,
        TelegramRetryAfter=Exception,
    )

    sys.modules["aiogram"] = aiogram_mock
    sys.modules["aiogram.types"] = types_mock
    sys.modules["aiogram.enums"] = enums_mock
    sys.modules["aiogram.exceptions"] = exceptions_mock
    sys.modules["aiogram.filters"] = MagicMock()
    sys.modules["aiogram.fsm"] = MagicMock()
    sys.modules["aiogram.fsm.context"] = MagicMock()
    sys.modules["aiogram.fsm.state"] = MagicMock()

if "redis" not in sys.modules or "redis.asyncio" not in sys.modules:
    sys.modules["redis"] = MagicMock()
    sys.modules["redis.asyncio"] = MagicMock()

if "asyncpg" not in sys.modules:
    sys.modules["asyncpg"] = MagicMock()

if "pydantic" not in sys.modules:
    pydantic_mock = MagicMock()
    pydantic_mock.Field = lambda default=None, default_factory=None: default or (default_factory() if default_factory else None)
    pydantic_mock.field_validator = lambda *args, **kwargs: (lambda fn: fn)
    pydantic_mock.SecretStr = lambda val="": str(val)
    sys.modules["pydantic"] = pydantic_mock

if "pydantic_settings" not in sys.modules:
    pydantic_settings_mock = MagicMock()
    pydantic_settings_mock.BaseSettings = object
    pydantic_settings_mock.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = pydantic_settings_mock

if "structlog" not in sys.modules:
    sys.modules["structlog"] = MagicMock()

if "orjson" not in sys.modules:
    import json
    class OrJsonMock:
        @staticmethod
        def dumps(obj):
            return json.dumps(obj).encode("utf-8")
        @staticmethod
        def loads(b):
            return json.loads(b)
    sys.modules["orjson"] = OrJsonMock()


from app.keyboards.movie_actions import movie_actions
from app.repositories.models import Movie
from app.services.cache import MovieCache
from app.utils.movie_helpers import format_movie_caption


class TestMovieHelpers(unittest.TestCase):
    def test_format_movie_caption_without_ratings(self):
        movie = Movie(
            code="101",
            file_id="BAADBAAD...",
            title="Forsaj 10",
            caption="Eng tezkor poyga",
            category="Jangari",
        )
        caption = format_movie_caption(movie, avg_rating=0.0, votes_count=0, user_rating=None)
        self.assertIn("Forsaj 10", caption)
        self.assertIn("101", caption)
        self.assertIn("Jangari", caption)
        self.assertIn("Hali baholanmagan", caption)
        self.assertIn("Eng tezkor poyga", caption)

    def test_format_movie_caption_with_ratings_and_user_rating(self):
        movie = Movie(
            code="102",
            file_id="BAADBAAD...",
            title="Avatar 2",
            caption="Suv yo'li",
            category="Fantastika",
        )
        caption = format_movie_caption(movie, avg_rating=4.8, votes_count=25, user_rating=5)
        self.assertIn("Avatar 2", caption)
        self.assertIn("102", caption)
        self.assertIn("Fantastika", caption)
        self.assertIn("4.8/5 (25 ta ovoz)", caption)
        self.assertIn("Sizning bahoingiz: 5⭐️", caption)


class TestMovieKeyboards(unittest.TestCase):
    def test_movie_actions_unfavorited_unrated(self):
        kb = movie_actions(code="marvel_1", is_fav=False, user_rating=None, avg_rating=0.0, votes_count=0)
        self.assertIsNotNone(kb)
        # Check favorite button
        self.assertEqual(kb.inline_keyboard[0][0].text, "🤍 Sevimlilarga qo'shish")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "fav:marvel_1")
        # Check rating buttons
        rating_row = kb.inline_keyboard[1]
        self.assertEqual(len(rating_row), 5)
        self.assertEqual(rating_row[0].text, "1 ⭐")
        self.assertEqual(rating_row[0].callback_data, "rate:1:marvel_1")
        # Check stats button
        self.assertEqual(kb.inline_keyboard[2][0].text, "⭐️ Hali baholanmagan")
        self.assertEqual(kb.inline_keyboard[2][0].callback_data, "info:marvel_1")

    def test_movie_actions_favorited_and_rated(self):
        kb = movie_actions(code="marvel_1", is_fav=True, user_rating=4, avg_rating=4.5, votes_count=10)
        self.assertIsNotNone(kb)
        # Check favorite button toggled
        self.assertEqual(kb.inline_keyboard[0][0].text, "💖 Sevimlilarda (O'chirish)")
        # Check 4th star is highlighted
        rating_row = kb.inline_keyboard[1]
        self.assertEqual(rating_row[3].text, "★ 4 🌟")
        self.assertEqual(rating_row[3].callback_data, "rate:4:marvel_1")
        # Check stats button shows info
        self.assertIn("4.5 / 5 (10 ta ovoz)", kb.inline_keyboard[2][0].text)

    def test_movie_list_keyboard(self):
        from app.keyboards.movie_actions import movie_list_keyboard
        movies = [
            Movie(code="101", file_id="f1", title="Forsaj 10", caption="Tavsif", category="Jangari"),
            Movie(code="102", file_id="f2", title="Avatar 2", caption="Suv yo'li", category="Fantastika"),
        ]
        kb = movie_list_keyboard(movies)
        self.assertEqual(len(kb.inline_keyboard), 2)
        self.assertEqual(kb.inline_keyboard[0][0].text, "🎬 Forsaj 10")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "get:101")
        self.assertEqual(kb.inline_keyboard[1][0].text, "🎬 Avatar 2")
        self.assertEqual(kb.inline_keyboard[1][0].callback_data, "get:102")


class TestMovieCache(unittest.IsolatedAsyncioTestCase):
    async def test_cache_serialization_includes_category(self):
        redis_mock = AsyncMock()
        cache = MovieCache(redis_mock)

        movie = Movie(
            code="test_code",
            file_id="file_123",
            title="Test Kino",
            caption="Test Tavsif",
            category="Komediya",
        )
        await cache.set(movie)
        redis_mock.set.assert_called_once()
        call_args = redis_mock.set.call_args[0]
        self.assertEqual(call_args[0], "movie:v1:test_code")
        self.assertIn('"cat": "Komediya"', call_args[1].replace('"cat":"Komediya"', '"cat": "Komediya"'))

        # Test get reconstruction
        redis_mock.get.return_value = '{"f":"file_123","t":"Test Kino","c":"Test Tavsif","cat":"Komediya"}'
        hit, retrieved = await cache.get("test_code")
        self.assertTrue(hit)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.category, "Komediya")
        self.assertEqual(retrieved.title, "Test Kino")


class TestMovieRepositoryMethods(unittest.IsolatedAsyncioTestCase):
    async def test_repository_get_rating_info(self):
        from app.repositories.movies import MovieRepository
        pool_mock = AsyncMock()
        pool_mock.fetchrow.return_value = {
            "avg_rating": 4.5,
            "votes_count": 8,
            "user_rating": 5,
        }
        repo = MovieRepository(pool_mock)
        avg, count, user_vote = await repo.get_rating_info("kino1", user_id=123)
        self.assertEqual(avg, 4.5)
        self.assertEqual(count, 8)
        self.assertEqual(user_vote, 5)

    async def test_repository_is_favorite(self):
        from app.repositories.movies import MovieRepository
        pool_mock = AsyncMock()
        pool_mock.fetchval.return_value = 1
        repo = MovieRepository(pool_mock)
        is_fav = await repo.is_favorite(123, "kino1")
        self.assertTrue(is_fav)

    async def test_repository_search_by_title(self):
        from app.repositories.movies import MovieRepository
        pool_mock = AsyncMock()
        pool_mock.fetch.return_value = [
            {"code": "101", "file_id": "fid_1", "title": "Forsaj 10", "caption": "Tavsif", "created_at": None, "category": "Jangari"}
        ]
        repo = MovieRepository(pool_mock)
        results = await repo.search_by_title("forsaj")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "101")
        self.assertEqual(results[0].title, "Forsaj 10")
        pool_mock.fetch.assert_called_once()

    async def test_repository_rate(self):
        from app.repositories.movies import MovieRepository
        conn_mock = AsyncMock()
        conn_mock.transaction = MagicMock()
        pool_mock = MagicMock()
        pool_mock.acquire.return_value.__aenter__.return_value = conn_mock
        repo = MovieRepository(pool_mock)
        await repo.rate(123, "kino1", 5, "user1", "Full Name")
        # Ensure user insertion and rating insertion happened
        self.assertEqual(conn_mock.execute.call_count, 2)
        first_sql = conn_mock.execute.call_args_list[0][0][0]
        second_sql = conn_mock.execute.call_args_list[1][0][0]
        self.assertIn("INSERT INTO users", first_sql)
        self.assertIn("INSERT INTO movie_ratings", second_sql)

    async def test_repository_toggle_favorite(self):
        from app.repositories.movies import MovieRepository
        conn_mock = AsyncMock()
        conn_mock.transaction = MagicMock()
        conn_mock.fetchval.return_value = None  # means not removed, so it will insert
        pool_mock = MagicMock()
        pool_mock.acquire.return_value.__aenter__.return_value = conn_mock
        repo = MovieRepository(pool_mock)
        added = await repo.toggle_favorite(123, "kino1", "user1", "Full Name")
        self.assertTrue(added)
        first_sql = conn_mock.execute.call_args_list[0][0][0]
        self.assertIn("INSERT INTO users", first_sql)

    async def test_repository_count_and_paginated(self):
        from app.repositories.movies import MovieRepository
        pool_mock = AsyncMock()
        pool_mock.fetchval.return_value = 12
        pool_mock.fetch.return_value = [
            {"code": "c1", "file_id": "f1", "title": "Kino 1", "caption": "Desc 1", "created_at": None, "category": "Action"},
            {"code": "c2", "file_id": "f2", "title": "Kino 2", "caption": "Desc 2", "created_at": None, "category": "Action"},
        ]
        repo = MovieRepository(pool_mock)
        total = await repo.count_active()
        self.assertEqual(total, 12)

        movies, total_count = await repo.list_paginated(limit=2, offset=0)
        self.assertEqual(len(movies), 2)
        self.assertEqual(total_count, 12)
        self.assertEqual(movies[0].code, "c1")


class TestDiscoveryAndStats(unittest.IsolatedAsyncioTestCase):
    async def test_build_stats_report(self):
        from app.services.discovery import DiscoveryService
        redis_mock = AsyncMock()
        redis_mock.get.return_value = "100"
        redis_mock.pfcount.return_value = 50
        redis_mock.zrevrange.return_value = [("33", 10.0), ("forsaj", 5.0)]
        redis_mock.hget.return_value = "25"

        movies_repo_mock = AsyncMock()
        discovery = DiscoveryService(redis_mock, movies_repo_mock)

        db_stats = {
            "total_users": 477,
            "new_24h": 477,
            "new_7d": 477,
            "active_24h": 477,
            "active_7d": 477,
            "active_30d": 51,
            "blocked_users": 66,
            "total_referrals": 0,
            "referrals_24h": 0,
            "referrers_count": 0,
            "total_movies": 4,
            "new_movies_7d": 4,
            "total_channels": 6,
            "total_ratings": 22,
            "ratings_users": 15,
            "ratings_24h": 22,
            "avg_rating": 3.45,
        }
        report = await discovery.build_stats_report(db_stats)
        self.assertIn("Jami foydalanuvchilar:</b> 477", report)
        self.assertIn("🥇 33 — 10", report)
        self.assertIn("🥈 forsaj — 5", report)
        self.assertIn("Umumiy o'rtacha: 3.45 / 5", report)
        self.assertIn("Toshkent", report)


if __name__ == "__main__":
    unittest.main()
