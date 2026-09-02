from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.container import Services


class UserMiddleware(BaseMiddleware):
    def __init__(self, services: Services) -> None:
        self.services = services

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user:
            # Cache this session marker: writing `last_seen_at` for every code lookup would
            # turn the database into the hot path. New users still get inserted immediately.
            first_seen_in_window = await self.services.subscriptions.redis.set(
                f"user:seen:v1:{user.id}", "1", ex=300, nx=True
            )
            if first_seen_in_window:
                await self.services.users.upsert(user.id, user.username, user.full_name or "")
            else:
                await self.services.users.ensure_exists(user.id, user.username, user.full_name or "")
        data["services"] = self.services
        return await handler(event, data)
