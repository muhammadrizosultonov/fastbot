from redis.asyncio import Redis

from app.repositories.admins import AdminRepository


class AdminService:
    def __init__(self, redis: Redis, repository: AdminRepository, bootstrap_ids: set[int]) -> None:
        self.redis, self.repository, self.bootstrap_ids = redis, repository, bootstrap_ids

    async def is_admin(self, user_id: int) -> bool:
        if user_id in self.bootstrap_ids:
            return True
        key = f"admin:v1:{user_id}"
        cached = await self.redis.get(key)
        if cached is not None:
            return cached == "1"
        allowed = await self.repository.is_admin(user_id)
        await self.redis.set(key, "1" if allowed else "0", ex=300)
        return allowed

    async def add(self, user_id: int, permissions: int = 1) -> None:
        await self.repository.add(user_id, permissions)
        await self.redis.delete(f"admin:v1:{user_id}")

    async def deactivate(self, user_id: int) -> bool:
        if user_id in self.bootstrap_ids:
            return False
        changed = await self.repository.deactivate(user_id)
        await self.redis.delete(f"admin:v1:{user_id}")
        return changed

    async def list_active(self) -> list[int]:
        return sorted(self.bootstrap_ids | set(await self.repository.list_active()))

    def is_root(self, user_id: int) -> bool:
        return user_id in self.bootstrap_ids
