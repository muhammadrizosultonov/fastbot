from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.keyboards.subscription import required_channels_keyboard
from app.services.container import Services


class SubscriptionMiddleware(BaseMiddleware):
    """Blocks every interaction until all required channel subscriptions are verified."""

    def __init__(self, services: Services) -> None:
        self.services = services

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if not user or await self.services.admins.is_admin(user.id):
            return await handler(event, data)

        cb = event if isinstance(event, CallbackQuery) else getattr(event, "callback_query", None)
        msg = event if isinstance(event, Message) else getattr(event, "message", None)

        # Allow admin command and subscription check callback through
        if msg and msg.text and msg.text.startswith("/admin"):
            return await handler(event, data)
        if cb and cb.data == "subscription:check":
            return await handler(event, data)

        missing = await self.services.subscriptions.missing(user.id)
        if not missing:
            return await handler(event, data)

        text = (
            "⚠️ <b>Botdan foydalanish uchun quyidagi homiy kanallarga obuna bo'ling:</b>\n\n"
            "<i>Kanallarga a'zo bo'lgach, <b>«✅ Tekshirish»</b> tugmasini bosing:</i>"
        )
        keyboard = required_channels_keyboard(missing)
        if cb:
            await cb.answer("Avval kanallarga obuna bo'ling!", show_alert=True)
            if cb.message and isinstance(cb.message, Message):
                await cb.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        elif msg:
            await msg.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return None
