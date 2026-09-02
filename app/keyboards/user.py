from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

POPULAR = "🔥 Eng mashhurlar"
NEW = "🆕 Yangi videolar"
CATEGORIES = "🎭 Kategoriyalar"
TOP_RATED = "⭐ TOP reyting"
RANDOM = "🎲 Tasodifiy video"
FAVORITES = "❤️ Sevimlilar"
INVITE = "👥 Do'st taklif qilish"
BONUSES = "🎁 Bonuslar"


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=POPULAR), KeyboardButton(text=NEW)],
            [KeyboardButton(text=CATEGORIES), KeyboardButton(text=TOP_RATED)],
            [KeyboardButton(text=RANDOM), KeyboardButton(text=FAVORITES)],
            [KeyboardButton(text=INVITE), KeyboardButton(text=BONUSES)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Video kodi yoki nomini yozing...",
    )
