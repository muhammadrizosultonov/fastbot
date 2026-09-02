from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.keyboards.age_gate import AGE_WARNING, age_confirmation_keyboard
from app.services.container import Services


class AgeGateMiddleware(BaseMiddleware):
    """Blocks every user path until adult confirmation is persisted."""

    def __init__(self, services: Services) -> None:
        self.services = services

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        # Bootstrap and delegated admins must retain operational access even when
        # the public 18+ gate is enabled.
        if await self.services.admins.is_admin(user.id):
            return await handler(event, data)

        cb = event if isinstance(event, CallbackQuery) else getattr(event, "callback_query", None)
        msg = event if isinstance(event, Message) else getattr(event, "message", None)

        if cb and cb.data in {"age:accept", "age:decline"}:
            return await handler(event, data)
        if await self.services.age_gate.is_confirmed(user.id):
            return await handler(event, data)
        if msg and msg.text and msg.text.startswith("/start ref_"):
            try:
                await self.services.age_gate.remember_referral(user.id, int(msg.text.split(maxsplit=1)[1][4:]))
            except (IndexError, ValueError):
                pass
        if cb:
            await cb.answer("Avval 18+ tasdiqlovini bering.", show_alert=True)
            if cb.message:
                await cb.message.answer(AGE_WARNING, reply_markup=age_confirmation_keyboard())
        elif msg:
            await msg.answer(AGE_WARNING, reply_markup=age_confirmation_keyboard())
        return None
