from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from app.keyboards.subscription import required_channels_keyboard
from app.keyboards.user import RANDOM, TOP_MOVIES, user_menu
from app.services.container import Services

router = Router(name="common")

DEFAULT_WELCOME_TEXT = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "🎬 <b>Kinolar botiga xush kelibsiz!</b>\n\n"
    "🔢 Tomosha qilmoqchi bo'lgan <b>kino kodini</b> yoki nomini yuboring:\n"
    "<i>(Yoki quyidagi bo'limlardan birini tanlang)</i>"
)

INVALID_WELCOME_VALUES = {
    RANDOM, TOP_MOVIES, "👥 Do'st taklif qilish", "TOP SEKSLAR🔥", "⭐ TOP reyting",
    "🔥 Eng mashhurlar", "🆕 Yangi videolar", "🎭 Kategoriyalar", "❤️ Sevimlilar", "🎁 Bonuslar",
    "🎬 Kino kodini yuboring.", "start", "/start"
}


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, services: Services) -> None:
    if command.args and command.args.startswith("ref_") and message.from_user:
        try:
            referrer_id = int(command.args[4:])
            await services.users.apply_referral(message.from_user.id, referrer_id)
        except (ValueError, TypeError):
            pass

    user_id = message.from_user.id if message.from_user else None
    if user_id and not await services.admins.is_admin(user_id):
        missing = await services.subscriptions.missing(user_id)
        if missing:
            text = (
                "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi homiy kanallarga obuna bo'ling:</b>\n\n"
                "<i>Kanallarga a'zo bo'lgach, <b>«✅ Tekshirish»</b> tugmasini bosing:</i>"
            )
            await message.answer(text, reply_markup=required_channels_keyboard(missing), parse_mode="HTML")
            return

    text = await services.configuration.get("welcome_text", DEFAULT_WELCOME_TEXT)
    if not text or text in INVALID_WELCOME_VALUES:
        text = DEFAULT_WELCOME_TEXT
    await message.answer(text, reply_markup=user_menu(), parse_mode="HTML")


@router.callback_query(F.data == "subscription:check")
async def check_subscription(callback: CallbackQuery, services: Services) -> None:
    if not callback.from_user:
        return
    # Invalidate cache to guarantee fresh check
    await services.subscriptions.invalidate_user(callback.from_user.id)
    missing = await services.subscriptions.missing(callback.from_user.id)
    if missing:
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        if callback.message and isinstance(callback.message, Message):
            text = (
                "⚠️ <b>Siz hali barcha kanallarga obuna bo'lmadingiz!</b>\n\n"
                "<i>Iltimos, quyidagi barcha kanallarga obuna bo'ling va so'ng tekshirish tugmasini bosing:</i>"
            )
            await callback.message.answer(text, reply_markup=required_channels_keyboard(missing), parse_mode="HTML")
        return
    await callback.answer("✅ Obuna tasdiqlandi!")
    if callback.message and isinstance(callback.message, Message):
        text = await services.configuration.get("welcome_text", DEFAULT_WELCOME_TEXT)
        if not text or text in INVALID_WELCOME_VALUES:
            text = DEFAULT_WELCOME_TEXT
        await callback.message.answer(text, reply_markup=user_menu(), parse_mode="HTML")
