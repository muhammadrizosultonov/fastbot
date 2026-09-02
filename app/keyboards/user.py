from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

RANDOM = "Tasodifiy video 🔞"
TOP_RATED = "TOP SEKSLAR🔥"
INVITE = "👥 Do'st taklif qilish"


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RANDOM), KeyboardButton(text=TOP_RATED)],
            [KeyboardButton(text=INVITE)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Video kodi yoki nomini yozing...",
    )
