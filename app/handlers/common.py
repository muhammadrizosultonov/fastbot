from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from app.keyboards.subscription import required_channels_keyboard
from app.keyboards.age_gate import AGE_WARNING, age_confirmation_keyboard
from app.keyboards.user import BONUSES, CATEGORIES, FAVORITES, INVITE, NEW, POPULAR, RANDOM, TOP_RATED, user_menu
from app.services.container import Services

router = Router(name="common")

DEFAULT_WELCOME_TEXT = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "🎬 <b>Kinolar botiga xush kelibsiz!</b>\n\n"
    "🔢 Tomosha qilmoqchi bo'lgan <b>kino kodini</b> yoki nomini yuboring:\n"
    "<i>(Yoki quyidagi bo'limlardan birini tanlang)</i>"
)

INVALID_WELCOME_VALUES = {
    POPULAR, NEW, CATEGORIES, TOP_RATED, RANDOM, FAVORITES, INVITE, BONUSES,
    "🎬 Kino kodini yuboring.", "start", "/start"
}


@router.callback_query(F.data == "age:accept")
async def confirm_age(callback: CallbackQuery, services: Services) -> None:
    if not callback.from_user:
        return
    await services.age_gate.confirm(callback.from_user.id)
    await callback.answer("✅ Yosh chegarasi tasdiqlandi.")
    if callback.message and isinstance(callback.message, Message):
        # Check if user needs to subscribe to required channels
        missing = await services.subscriptions.missing(callback.from_user.id)
        if missing:
            text = (
                "⚠️ <b>Botdan to'liq foydalanish uchun quyidagi homiy kanallarga obuna bo'ling:</b>\n\n"
                "<i>Kanallarga a'zo bo'lgach, <b>«✅ Tekshirish»</b> tugmasini bosing:</i>"
            )
            await callback.message.answer(text, reply_markup=required_channels_keyboard(missing), parse_mode="HTML")
        else:
            text = await services.configuration.get("welcome_text", DEFAULT_WELCOME_TEXT)
            if not text or text in INVALID_WELCOME_VALUES:
                text = DEFAULT_WELCOME_TEXT
            await callback.message.answer(text, reply_markup=user_menu(), parse_mode="HTML")


@router.callback_query(F.data == "age:decline")
async def decline_age(callback: CallbackQuery) -> None:
    # The warning remains visible and the gate continues blocking every later update.
    await callback.answer(AGE_WARNING.replace("<b>", "").replace("</b>", ""), show_alert=True)


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, services: Services) -> None:
    if command.args and command.args.startswith("ref_") and message.from_user:
        try:
            await services.age_gate.apply_referral(message.from_user.id, int(command.args[4:]))
        except ValueError:
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
