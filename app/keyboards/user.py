from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

RANDOM = "Tasodifiy video 🔞"
TOP_MOVIES = "TOP SEKSLAR🔥"


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RANDOM), KeyboardButton(text=TOP_MOVIES)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Video kodi yoki nomini yozing...",
    )
