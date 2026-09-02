from __future__ import annotations

from aiogram.enums import ParseMode
from aiogram.types import Message

import html

from app.keyboards.movie_actions import movie_actions, movie_list_keyboard
from app.repositories.models import Movie
from app.services.container import Services


def format_movie_caption(
    movie: Movie,
    avg_rating: float = 0.0,
    votes_count: int = 0,
    user_rating: int | None = None,
) -> str:
    raw_title = (movie.title or "").strip()
    raw_caption = (movie.caption or "").strip()

    is_file_name = any(raw_title.lower().endswith(ext) for ext in [".mov", ".mp4", ".mkv", ".avi", ".webm", ".3gp"]) or raw_title.startswith(("IMG_", "VID_", "video_", "file_"))

    if is_file_name and raw_caption:
        display_title = raw_caption.split("\n", 1)[0].strip()
        desc = raw_caption[len(display_title):].strip()
    elif raw_title and not is_file_name:
        display_title = raw_title
        desc = raw_caption if raw_caption != raw_title else ""
    elif raw_caption:
        display_title = raw_caption.split("\n", 1)[0].strip()
        desc = raw_caption[len(display_title):].strip()
    else:
        display_title = f"Kino #{movie.code}"
        desc = ""

    lines = []
    lines.append(f"🎬 <b>{html.escape(display_title)}</b>")
    lines.append("")
    lines.append(f"🔢 <b>Kodi:</b> <code>{html.escape(str(movie.code))}</code>")
    lines.append(f"🎭 <b>Kategoriya:</b> {html.escape(movie.category or 'Boshqa')}")

    if votes_count > 0:
        user_part = f" <i>(Sizning bahoingiz: {user_rating}⭐️)</i>" if user_rating else ""
        lines.append(f"⭐️ <b>Reyting:</b> {avg_rating:.1f}/5 ({votes_count} ta ovoz){user_part}")
    else:
        lines.append("⭐️ <b>Reyting:</b> Hali baholanmagan (birinchi bo'lib baholang!)")

    if desc and desc != display_title:
        lines.append("")
        lines.append(f"📝 <b>Tavsif:</b>\n{html.escape(desc)}")

    return "\n".join(lines)


async def send_single_movie(
    message: Message,
    movie: Movie,
    services: Services,
    user_id: int | None = None,
) -> Message:
    uid = user_id or (message.from_user.id if message.from_user else None)
    
    # Try Redis cached rating summary first
    hit, summary = await services.movies.cache.get_rating_summary(movie.code)
    if hit and not uid:
        avg_rating, votes_count = summary
        user_rating = None
        is_fav = False
    else:
        avg_rating, votes_count, user_rating = await services.movies.repository.get_rating_info(movie.code, uid)
        await services.movies.cache.set_rating_summary(movie.code, avg_rating, votes_count)
        is_fav = await services.movies.repository.is_favorite(uid, movie.code) if uid else False

    caption = format_movie_caption(movie, avg_rating, votes_count, user_rating)
    reply_markup = movie_actions(
        code=movie.code,
        is_fav=is_fav,
        user_rating=user_rating,
        avg_rating=avg_rating,
        votes_count=votes_count,
    )

    try:
        msg = await message.answer_video(
            movie.file_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        plain_caption = f"🎬 {movie.title or movie.caption or movie.code}\n🔢 Kodi: {movie.code}\n🎭 Kategoriya: {movie.category or 'Boshqa'}"
        msg = await message.answer_video(
            movie.file_id,
            caption=plain_caption,
            reply_markup=reply_markup,
        )

    await services.discovery.record_view(movie.code, uid)
    return msg


async def send_movie_list(
    message: Message,
    movies: list[Movie],
    services: Services,
    title: str,
    user_id: int | None = None,
) -> None:
    if not movies:
        await message.answer(f"{title}\n\nHozircha video topilmadi.", parse_mode=ParseMode.HTML)
        return
    text = f"{title}\n\n👇 <b>Kerakli videoni tomosha qilish uchun tanlang:</b>"
    kb = movie_list_keyboard(movies)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
