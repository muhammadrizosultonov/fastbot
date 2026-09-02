import glob
import logging
import os
import asyncpg

log = logging.getLogger(__name__)


async def run_migrations(pool: asyncpg.Pool) -> None:
    migrations_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "migrations")
    if not os.path.exists(migrations_dir):
        return
    files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    async with pool.acquire() as conn:
        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    sql = f.read()
                if sql.strip():
                    await conn.execute(sql)
            except Exception as e:
                log.warning("Migration warning for %s: %s", file, e)


async def create_pool(dsn: str, min_size: int, max_size: int) -> asyncpg.Pool:
    """A small pool per process prevents connection exhaustion after horizontal scaling."""

    async def init_connection(connection: asyncpg.Connection) -> None:
        await connection.execute("SET TIME ZONE 'UTC'")
        await connection.execute("SET statement_timeout = '5000ms'")

    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        max_queries=50_000,
        max_inactive_connection_lifetime=300,
        command_timeout=6,
        init=init_connection,
    )
    await run_migrations(pool)
    return pool
