from redis.asyncio import Redis

from app.repositories.users import UserRepository


class AgeGateService:
    """Persistent consent in PostgreSQL, with Redis on the request hot path."""

    CACHE_TTL_SECONDS = 86_400

    def __init__(self, redis: Redis, users: UserRepository) -> None:
        self.redis, self.users = redis, users

    @staticmethod
    def key(user_id: int) -> str:
        return f"age_gate:v1:{user_id}"

    async def is_confirmed(self, user_id: int) -> bool:
        cached = await self.redis.get(self.key(user_id))
        if cached is not None:
            return cached == "1"
        confirmed = await self.users.is_age_confirmed(user_id)
        await self.redis.set(self.key(user_id), "1" if confirmed else "0", ex=self.CACHE_TTL_SECONDS)
        return confirmed

    async def confirm(self, user_id: int) -> None:
        await self.users.confirm_age(user_id)
        await self.redis.set(self.key(user_id), "1", ex=self.CACHE_TTL_SECONDS)
        referrer_id = await self.redis.get(f"age_referral:v1:{user_id}")
        if referrer_id:
            await self.users.apply_referral(user_id, int(referrer_id))
            await self.redis.delete(f"age_referral:v1:{user_id}")

    async def remember_referral(self, user_id: int, referrer_id: int) -> None:
        if user_id != referrer_id:
            await self.redis.set(f"age_referral:v1:{user_id}", str(referrer_id), ex=86_400)

    async def apply_referral(self, user_id: int, referrer_id: int) -> bool:
        return await self.users.apply_referral(user_id, referrer_id)
