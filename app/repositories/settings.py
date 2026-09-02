import asyncpg


class SettingsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def get(self, key: str) -> str | None:
        return await self.pool.fetchval("SELECT value FROM bot_settings WHERE key=$1", key)

    async def set(self, key: str, value: str) -> None:
        await self.pool.execute(
            """INSERT INTO bot_settings (key, value) VALUES ($1, $2)
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()""",
            key, value,
        )
