from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

RANDOM = "Tasodifiy video 🔞"
INVITE = "👥 Do'st taklif qilish"


def user_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=RANDOM), KeyboardButton(text=INVITE)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Video kodi yoki nomini yozing...",
    )
