from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.keyboards.user import RANDOM, TOP_MOVIES
from app.services.container import Services
from app.utils.movie_helpers import send_movie_list, send_single_movie

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


@router.message(F.text.in_({RANDOM, "🎲 Tasodifiy video", "Tasodifiy video 🔞"}))
async def random_movie(message: Message, services: Services) -> None:
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("🎲 Tasodifiy video", user_id)
    movie = await services.movies.repository.random()
    if not movie:
        await message.answer("🎲 Hozircha bazada videolar mavjud emas.")
        return
    await send_single_movie(message, movie, services, user_id=user_id)


@router.message(F.text.in_({TOP_MOVIES, "🔥 TOP kinolar", "TOP kinolar", "TOP SEKSLAR🔥", "⭐ TOP reyting"}))
async def top_movies(message: Message, services: Services) -> None:
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("🔥 TOP kinolar", user_id)
    movies = await services.discovery.popular(limit=10)
    await send_movie_list(
        message,
        movies,
        services,
        "🔥 <b>Eng ko'p ko'rilayotgan TOP kinolar:</b>",
        user_id=user_id,
    )
