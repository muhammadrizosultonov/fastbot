from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def categories_keyboard(categories: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🎭 {name} ({count})", callback_data=f"cat:{name}")]
        for name, count in categories
        if len(name.encode()) <= 56
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
