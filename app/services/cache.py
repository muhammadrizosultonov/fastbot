import orjson
from redis.asyncio import Redis

from app.repositories.models import Movie


class MovieCache:
    TTL_SECONDS = 86_400
    NOT_FOUND_TTL_SECONDS = 60
    NOT_FOUND = "!"

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def key(code: str) -> str:
        return f"movie:v1:{code}"

    async def get(self, code: str) -> tuple[bool, Movie | None]:
        """Return (cached, value); cached negatives protect PostgreSQL from code-guessing."""
        raw = await self.redis.get(self.key(code))
        if raw is None:
            return False, None
        if raw == self.NOT_FOUND:
            return True, None
        data = orjson.loads(raw)
        return True, Movie(code=code, file_id=data["f"], title=data.get("t"), caption=data.get("c"), category=data.get("cat", "Boshqa"))

    async def set(self, movie: Movie) -> None:
        payload = orjson.dumps({"f": movie.file_id, "t": movie.title, "c": movie.caption, "cat": movie.category}).decode()
        await self.redis.set(self.key(movie.code), payload, ex=self.TTL_SECONDS)

    async def invalidate(self, code: str) -> None:
        await self.redis.delete(self.key(code))

    async def set_not_found(self, code: str) -> None:
        await self.redis.set(self.key(code), self.NOT_FOUND, ex=self.NOT_FOUND_TTL_SECONDS)

    def rating_key(self, code: str) -> str:
        return f"movie_rating:v1:{code}"

    async def get_rating_summary(self, code: str) -> tuple[bool, tuple[float, int]]:
        raw = await self.redis.get(self.rating_key(code))
        if raw is None:
            return False, (0.0, 0)
        try:
            data = orjson.loads(raw)
            return True, (float(data["avg"]), int(data["cnt"]))
        except Exception:
            return False, (0.0, 0)

    async def set_rating_summary(self, code: str, avg_rating: float, votes_count: int) -> None:
        payload = orjson.dumps({"avg": avg_rating, "cnt": votes_count}).decode()
        await self.redis.set(self.rating_key(code), payload, ex=3600)

    async def invalidate_rating_summary(self, code: str) -> None:
        await self.redis.delete(self.rating_key(code))
