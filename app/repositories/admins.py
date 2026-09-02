import asyncpg


class AdminRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def is_admin(self, user_id: int) -> bool:
        return bool(await self.pool.fetchval("SELECT 1 FROM admins WHERE user_id=$1 AND is_active", user_id))

    async def add(self, user_id: int, permissions: int = 1) -> None:
        await self.pool.execute(
            """INSERT INTO admins (user_id, permissions) VALUES ($1, $2)
               ON CONFLICT (user_id) DO UPDATE SET is_active=true, permissions=EXCLUDED.permissions""",
            user_id, permissions,
        )

    async def deactivate(self, user_id: int) -> bool:
        result = await self.pool.execute("UPDATE admins SET is_active=false WHERE user_id=$1", user_id)
        return result.endswith("1")

    async def list_active(self) -> list[int]:
        rows = await self.pool.fetch("SELECT user_id FROM admins WHERE is_active ORDER BY user_id")
        return [int(row["user_id"]) for row in rows]
