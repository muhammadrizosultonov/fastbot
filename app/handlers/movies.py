import re

from aiogram import F, Router
from aiogram.types import Message

from app.services.container import Services
from app.utils.movie_helpers import send_movie_list, send_single_movie

router = Router(name="movies")
CODE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@router.message(F.text)
async def movie_by_code(message: Message, services: Services) -> None:
    raw_text = (message.text or "").strip()
    if not raw_text or raw_text.startswith("/"):
        return

    code = raw_text.lower()
    user_id = message.from_user.id if message.from_user else None
    await services.discovery.track_section("🔎 Qidirish", user_id)

    # 1. First check if it matches a direct movie code
    if CODE.fullmatch(code):
        movie = await services.movies.find(code)
        if movie is not None:
            await send_single_movie(message, movie, services, user_id=user_id)
            return

    # 2. If not found by code, try searching by title, caption, or substring
    if len(raw_text) >= 2:
        movies = await services.movies.repository.search_by_title(raw_text)
        if movies:
            if len(movies) == 1:
                await send_single_movie(message, movies[0], services, user_id=user_id)
            else:
                await send_movie_list(
                    message,
                    movies,
                    services,
                    f"🔎 <b>{len(movies)} ta video topildi:</b>",
                    user_id=user_id,
                )
            return

    await message.answer(
        "❌ Bunday kod yoki nomli kino topilmadi.\n"
        "Iltimos, kino kodi yoki nomini to'g'ri kiritganingizni tekshiring."
    )
