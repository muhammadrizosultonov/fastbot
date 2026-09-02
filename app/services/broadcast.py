import asyncio
import time
from datetime import datetime, timedelta, timezone

import asyncpg
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from redis.asyncio import Redis

from app.repositories.users import UserRepository

log = structlog.get_logger(__name__)

TOKEN_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], 1) end
return current
"""


class BroadcastService:
    """DB row claiming + a fleet-wide Redis rate budget allows safe separate worker processes."""

    def __init__(self, pool: asyncpg.Pool, redis: Redis, users: UserRepository, bot: Bot, concurrency: int, rate: int) -> None:
        self.pool, self.redis, self.users, self.bot = pool, redis, users, bot
        self.concurrency, self.rate = concurrency, rate

    async def create(self, creator_id: int, source_chat_id: int, source_message_id: int) -> int:
        await self.users.ensure_exists(creator_id)
        row = await self.pool.fetchrow(
            """INSERT INTO broadcast_jobs (creator_id, source_chat_id, source_message_id, status)
               VALUES ($1,$2,$3,'preparing') RETURNING id""",
            creator_id, source_chat_id, source_message_id,
        )
        job_id = int(row["id"])
        await self.users.create_broadcast_deliveries(job_id)
        await self.pool.execute("UPDATE broadcast_jobs SET status='queued', started_at=now() WHERE id=$1", job_id)
        return job_id

    async def attach_progress_message(self, job_id: int, chat_id: int, message_id: int) -> None:
        await self.pool.execute(
            "UPDATE broadcast_jobs SET progress_chat_id=$2, progress_message_id=$3 WHERE id=$1",
            job_id, chat_id, message_id,
        )

    async def run_forever(self) -> None:
        while True:
            job_id = await self.pool.fetchval("SELECT id FROM broadcast_jobs WHERE status='queued' ORDER BY id LIMIT 1")
            if job_id is None:
                await asyncio.sleep(1)
                continue
            lock = self.redis.lock(f"broadcast:leader:{job_id}", timeout=30, blocking_timeout=0)
            if not await lock.acquire():
                await asyncio.sleep(0.2)
                continue
            try:
                await self._run_job(int(job_id), lock)
            except Exception:
                log.exception("broadcast_job_failed", job_id=job_id)
            finally:
                try:
                    await lock.release()
                except Exception:
                    pass

    async def _run_job(self, job_id: int, lock) -> None:  # type: ignore[no-untyped-def]
        await self.pool.execute("UPDATE broadcast_jobs SET status='running' WHERE id=$1 AND status='queued'", job_id)
        job = await self.pool.fetchrow(
            "SELECT source_chat_id, source_message_id FROM broadcast_jobs WHERE id=$1", job_id
        )
        if job is None:
            return
        source_chat_id, source_message_id = int(job["source_chat_id"]), int(job["source_message_id"])
        last_report = 0.0
        while True:
            await lock.extend(30, replace_ttl=True)
            rows = await self._claim_batch(job_id, self.concurrency)
            if not rows:
                pending = await self.pool.fetchval(
                    "SELECT 1 FROM broadcast_deliveries WHERE job_id=$1 AND status IN ('pending','retry') LIMIT 1", job_id
                )
                if not pending:
                    await self.pool.execute("UPDATE broadcast_jobs SET status='done', finished_at=now() WHERE id=$1", job_id)
                    await self._report(job_id, done=True)
                    return
                await asyncio.sleep(0.5)
                continue
            await asyncio.gather(
                *(self._deliver(job_id, dict(row), source_chat_id, source_message_id) for row in rows)
            )
            if time.monotonic() - last_report >= 10:
                await self._report(job_id)
                last_report = time.monotonic()

    async def _report(self, job_id: int, done: bool = False) -> None:
        row = await self.pool.fetchrow(
            """SELECT j.progress_chat_id, j.progress_message_id,
                      count(d.id)::bigint AS total,
                      count(d.id) FILTER (WHERE d.status='sent')::bigint AS sent,
                      count(d.id) FILTER (WHERE d.status IN ('failed','blocked'))::bigint AS failed
               FROM broadcast_jobs j LEFT JOIN broadcast_deliveries d ON d.job_id=j.id
               WHERE j.id=$1 GROUP BY j.id""",
            job_id,
        )
        if not row or row["progress_chat_id"] is None or row["progress_message_id"] is None:
            return
        text = f"{'✅ Yakunlandi' if done else '⏳ Yuborilmoqda'} #{job_id}\n\nYuborildi: {row['sent']:,}/{row['total']:,}\nXato/blok: {row['failed']:,}"
        try:
            await self.bot.edit_message_text(text, row["progress_chat_id"], row["progress_message_id"])
        except TelegramBadRequest:
            # The administrator may have deleted the progress message; delivery must continue.
            pass

    async def _claim_batch(self, job_id: int, size: int) -> list[asyncpg.Record]:
        async with self.pool.acquire() as connection, connection.transaction():
            return await connection.fetch(
                """WITH picked AS (
                     SELECT id FROM broadcast_deliveries
                     WHERE job_id=$1 AND status IN ('pending','retry')
                       AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                     ORDER BY id FOR UPDATE SKIP LOCKED LIMIT $2
                   )
                   UPDATE broadcast_deliveries d SET status='sending', attempts=attempts+1
                   FROM picked WHERE d.id=picked.id RETURNING d.id, d.user_id, d.attempts""",
                job_id, size,
            )

    async def _take_token(self) -> None:
        while True:
            # This is shared by every process, avoiding Telegram's global bot limit.
            count = int(await self.redis.eval(TOKEN_LUA, 1, "broadcast:rate:v1"))
            if count <= self.rate:
                return
            await asyncio.sleep(0.05)

    async def _deliver(self, job_id: int, delivery: dict[str, int], source_chat_id: int, source_message_id: int) -> None:
        await self._take_token()
        try:
            await self.bot.copy_message(delivery["user_id"], source_chat_id, source_message_id)
            await self.pool.execute("UPDATE broadcast_deliveries SET status='sent', sent_at=now() WHERE id=$1", delivery["id"])
        except TelegramRetryAfter as error:
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=error.retry_after + 1)
            await self.pool.execute("UPDATE broadcast_deliveries SET status='retry', next_attempt_at=$2 WHERE id=$1", delivery["id"], retry_at)
        except TelegramForbiddenError:
            await self.pool.execute("UPDATE users SET is_blocked=true WHERE id=$1", delivery["user_id"])
            await self.pool.execute("UPDATE broadcast_deliveries SET status='blocked' WHERE id=$1", delivery["id"])
        except TelegramBadRequest:
            await self.pool.execute("UPDATE broadcast_deliveries SET status='failed' WHERE id=$1", delivery["id"])
        except Exception:
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** min(delivery.get("attempts", 1), 8)))
            await self.pool.execute("UPDATE broadcast_deliveries SET status='retry', next_attempt_at=$2 WHERE id=$1", delivery["id"], retry_at)
