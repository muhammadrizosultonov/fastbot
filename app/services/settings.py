from redis.asyncio import Redis

from app.repositories.settings import SettingsRepository


class BotSettingsService:
    def __init__(self, redis: Redis, repository: SettingsRepository) -> None:
        self.redis, self.repository = redis, repository

    async def get(self, key: str, default: str) -> str:
        cache_key = f"setting:v1:{key}"
        cached = await self.redis.get(cache_key)
        if cached is not None:
            return cached
        value = await self.repository.get(key) or default
        await self.redis.set(cache_key, value, ex=300)
        return value

    async def set(self, key: str, value: str) -> None:
        await self.repository.set(key, value)
        await self.redis.delete(f"setting:v1:{key}")
