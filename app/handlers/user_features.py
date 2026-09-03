from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.keyboards.user import INVITE, RANDOM
from app.services.container import Services
from app.utils.movie_helpers import send_single_movie

router = Router(name="user_features")


@router.callback_query(F.data.startswith("get:"))
async def get_movie_callback(callback: CallbackQuery, services: Services) -> None:
    code = callback.data[4:]
    await callback.answer()
    if not callback.message or not isinstance(callback.message, Message):
        return
    movie = await services.movies.find(code)
    if not movie:
        await callback.message.answer("❌ Bu video topilmadi yoki o'chirilgan.")
        return
    user_id = callback.from_user.id if callback.from_user else None
    await send_single_movie(callback.message, movie, services, user_id=user_id)


@router.message(F.text == RANDOM)
async def random_movie(message: Message, services: Services) -> None:
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("🎲 Tasodifiy video", user_id)
    movie = await services.movies.repository.random()
    if not movie:
        await message.answer("🎲 Hozircha bazada videolar mavjud emas.")
        return
    await send_single_movie(message, movie, services, user_id=user_id)


@router.message(F.text == INVITE)
async def invite(message: Message, services: Services) -> None:
    if not message.from_user:
        return
    await services.discovery.track_section("👥 Do'st taklif qilish", message.from_user.id)
    bot_user = await message.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=ref_{message.from_user.id}"
    points, referrals = await services.users.bonus_summary(message.from_user.id)
    await message.answer(
        f"👥 <b>Do'stlaringizni taklif qiling va bonus oling!</b>\n\n"
        f"Har bir taklif qilingan do'stingiz uchun <b>10 ball</b> beriladi.\n\n"
        f"👥 Siz taklif qilgan do'stlar: <b>{referrals} ta</b>\n"
        f"💎 To'plangan ballar: <b>{points} ball</b>\n\n"
        f"Sizning taklif havolangiz:\n<code>{link}</code>",
        parse_mode="HTML",
    )
