from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def movie_actions(
    code: str,
    is_fav: bool = False,
    user_rating: int | None = None,
    avg_rating: float = 0.0,
    votes_count: int = 0,
) -> InlineKeyboardMarkup | None:
    # Telegram callback_data is capped at 64 bytes.
    if len(code.encode()) > 50:
        return None

    fav_text = "💖 Sevimlilarda (O'chirish)" if is_fav else "🤍 Sevimlilarga qo'shish"

    rating_buttons = []
    for r in range(1, 6):
        if user_rating == r:
            btn_text = f"★ {r} 🌟"
        else:
            btn_text = f"{r} ⭐"
        rating_buttons.append(
            InlineKeyboardButton(text=btn_text, callback_data=f"rate:{r}:{code}")
        )

    if votes_count > 0:
        info_text = f"⭐️ {avg_rating:.1f} / 5 ({votes_count} ta ovoz)"
    else:
        info_text = "⭐️ Hali baholanmagan"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=fav_text, callback_data=f"fav:{code}")],
            rating_buttons,
            [InlineKeyboardButton(text=info_text, callback_data=f"info:{code}")],
        ]
    )


def movie_list_keyboard(movies: list) -> InlineKeyboardMarkup:
    buttons = []
    for m in movies:
        raw_name = m.title or m.caption or f"Kino #{m.code}"
        clean_name = raw_name.replace("\n", " ").strip()
        if len(clean_name) > 42:
            clean_name = clean_name[:39] + "..."
        btn_text = f"🎬 {clean_name}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"get:{m.code}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
