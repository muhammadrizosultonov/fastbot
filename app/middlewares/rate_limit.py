from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, limit: int) -> None:
        self.redis, self.limit = redis, limit

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        key = f"rate:v1:{user.id}"
        # Atomic pipeline avoids races that can allow burst traffic through under load.
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 1, nx=True)
            count, _ = await pipe.execute()
        if int(count) > self.limit:
            cb = event if isinstance(event, CallbackQuery) else getattr(event, "callback_query", None)
            if cb:
                await cb.answer("Juda tez so'rov. Biroz kuting.", show_alert=False)
            return None
        return await handler(event, data)
