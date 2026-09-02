from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


AGE_WARNING = (
    "⚠️ <b>18+ ogohlantirish</b>\n\n"
    "Bu bot faqat 18 yoshdan katta foydalanuvchilar uchun mo'ljallangan. "
    "Davom etish orqali 18 yoshdan o'tganingizni tasdiqlaysiz."
)


def age_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha, 18 yoshdan o'tganman", callback_data="age:accept")],
            [InlineKeyboardButton(text="❌ Yo'q", callback_data="age:decline")],
        ]
    )
