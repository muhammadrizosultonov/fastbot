from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.repositories.models import RequiredChannel


def required_channels_keyboard(channels: list[RequiredChannel]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        if channel.invite_link:
            link = channel.invite_link.strip()
            if not link.startswith("http://") and not link.startswith("https://"):
                link = f"https://t.me/{link.lstrip('@')}"
            builder.button(text=f"📢 {channel.title}", url=link)
    builder.button(text="✅ Tekshirish", callback_data="subscription:check")
    builder.adjust(1)
    return builder.as_markup()
