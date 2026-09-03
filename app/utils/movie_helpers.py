from __future__ import annotations

import html
from aiogram.enums import ParseMode
from aiogram.types import Message

from app.keyboards.movie_actions import movie_list_keyboard
from app.repositories.models import Movie
from app.services.container import Services


def format_movie_caption(movie: Movie) -> str:
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
        display_title = f"Video #{movie.code}"
        desc = ""

    lines = [f"🎬 <b>{html.escape(display_title)}</b>"]
    if desc and desc != display_title:
        lines.append("")
        lines.append(f"{html.escape(desc)}")

    return "\n".join(lines)


async def send_single_movie(
    message: Message,
    movie: Movie,
    services: Services,
    user_id: int | None = None,
) -> Message:
    uid = user_id or (message.from_user.id if message.from_user else None)
    caption = format_movie_caption(movie)

    try:
        msg = await message.answer_video(
            movie.file_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        plain_caption = f"🎬 {movie.title or movie.caption or movie.code}"
        msg = await message.answer_video(
            movie.file_id,
            caption=plain_caption,
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
