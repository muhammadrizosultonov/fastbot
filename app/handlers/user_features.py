import contextlib

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.keyboards.movie_actions import movie_actions
from app.keyboards.user import INVITE, RANDOM, TOP_RATED
from app.services.container import Services
from app.utils.movie_helpers import format_movie_caption, send_movie_list, send_single_movie

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


@router.message(F.text == TOP_RATED)
async def top_rated(message: Message, services: Services) -> None:
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("⭐ TOP reyting", user_id)
    movies = await services.movies.repository.top_rated()
    await send_movie_list(message, movies, services, "⭐ <b>Eng yuqori baholangan videolar:</b>", user_id=user_id)


@router.message(F.text == RANDOM)
async def random_movie(message: Message, services: Services) -> None:
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("🎲 Tasodifiy video", user_id)
    movie = await services.movies.repository.random()
    if not movie:
        await message.answer("🎲 Hozircha bazada videolar mavjud emas.")
        return
    await message.answer("🎲 <b>Tasodifiy video:</b>", parse_mode="HTML")
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


@router.callback_query(F.data.startswith("fav:"))
async def toggle_favorite(callback: CallbackQuery, services: Services) -> None:
    if not callback.from_user:
        return
    user_id = callback.from_user.id
    code = callback.data[4:]

    await services.users.ensure_exists(
        user_id, callback.from_user.username, callback.from_user.full_name
    )
    is_fav = await services.movies.repository.toggle_favorite(
        user_id, code, callback.from_user.username, callback.from_user.full_name
    )
    await callback.answer(
        "❤️ Sevimlilarga qo'shildi!" if is_fav else "💔 Sevimlilardan o'chirildi!"
    )

    if callback.message:
        movie = await services.movies.find(code)
        if movie:
            avg_rating, votes_count, user_rating = await services.movies.repository.get_rating_info(
                code, user_id
            )
            caption = format_movie_caption(movie, avg_rating, votes_count, user_rating)
            kb = movie_actions(
                code=code,
                is_fav=is_fav,
                user_rating=user_rating,
                avg_rating=avg_rating,
                votes_count=votes_count,
            )
            with contextlib.suppress(TelegramBadRequest, Exception):
                await callback.message.edit_caption(
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="HTML",
                )


@router.callback_query(F.data.startswith("rate:"))
async def rate_movie(callback: CallbackQuery, services: Services) -> None:
    if not callback.from_user:
        return
    try:
        _, rating_str, code = callback.data.split(":", 2)
        rating_int = int(rating_str)
        if rating_int not in range(1, 6):
            raise ValueError
    except ValueError:
        await callback.answer("Noto'g'ri baho.", show_alert=True)
        return

    user_id = callback.from_user.id
    await services.discovery.track_section("⭐ Baholash", user_id)
    await services.users.ensure_exists(
        user_id, callback.from_user.username, callback.from_user.full_name
    )
    await services.movies.repository.rate(
        user_id, code, rating_int, callback.from_user.username, callback.from_user.full_name
    )
    await services.movies.cache.invalidate_rating_summary(code)
    await callback.answer(f"✅ Siz {rating_int}⭐️ baho berdingiz!")

    if callback.message:
        movie = await services.movies.find(code)
        if movie:
            avg_rating, votes_count, user_rating = await services.movies.repository.get_rating_info(
                code, user_id
            )
            is_fav = await services.movies.repository.is_favorite(user_id, code)
            caption = format_movie_caption(movie, avg_rating, votes_count, user_rating)
            kb = movie_actions(
                code=code,
                is_fav=is_fav,
                user_rating=user_rating,
                avg_rating=avg_rating,
                votes_count=votes_count,
            )
            with contextlib.suppress(TelegramBadRequest, Exception):
                await callback.message.edit_caption(
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="HTML",
                )


@router.callback_query(F.data.startswith("info:"))
async def info_movie(callback: CallbackQuery, services: Services) -> None:
    code = callback.data[5:]
    avg_rating, votes_count, _ = await services.movies.repository.get_rating_info(code)
    if votes_count > 0:
        await callback.answer(
            f"⭐️ O'rtacha reyting: {avg_rating:.1f} / 5\n📊 Jami baholar soni: {votes_count} ta",
            show_alert=True,
        )
    else:
        await callback.answer(
            "⭐️ Bu video hali baholanmagan.\nBirinchi bo'lib yulduzchalardan birini tanlab baho bering!",
            show_alert=True,
        )
