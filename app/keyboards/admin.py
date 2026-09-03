import math
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.repositories.models import Movie, RequiredChannel

ADMIN_MOVIES = "🎬 Kinolar"
ADMIN_CHANNELS = "📡 Majburiy kanallar"
ADMIN_STATS = "📊 Statistika"
ADMIN_BROADCAST = "✉️ Xabar yuborish"
ADMIN_ADMINS = "👤 Adminlar"
ADMIN_SETTINGS = "⚙️ Sozlamalar"
ADMIN_BACK_TO_USER = "◀️ Oddiy menyuga qaytish"


def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADMIN_MOVIES), KeyboardButton(text=ADMIN_CHANNELS)],
            [KeyboardButton(text=ADMIN_STATS), KeyboardButton(text=ADMIN_BROADCAST)],
            [KeyboardButton(text=ADMIN_ADMINS), KeyboardButton(text=ADMIN_SETTINGS)],
            [KeyboardButton(text=ADMIN_BACK_TO_USER)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Boshqaruv bo'limini tanlang...",
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data="admin:stats")
    builder.button(text="✉️ Xabar yuborish", callback_data="admin:broadcast")
    builder.button(text="🎬 Kinolar (CRUD)", callback_data="admin:movies:menu")
    builder.button(text="🔐 Obuna kanallar", callback_data="admin:channels:menu")
    builder.button(text="👤 Adminlar", callback_data="admin:admins")
    builder.button(text="⚙️ Sozlamalar", callback_data="admin:settings")
    builder.adjust(2)
    return builder.as_markup()


def movies_crud_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi kino qo'shish", callback_data="admin:movie:add")
    builder.button(text="📋 Kinolar ro'yxati", callback_data="admin:movie:list:0")
    builder.button(text="🗑 Kino o'chirish", callback_data="admin:movie:del_list:0")
    builder.button(text="🔙 Asosiy admin panel", callback_data="admin:home")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def movies_list_admin_keyboard(movies: list[Movie], page: int, total: int, limit: int = 5) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in movies:
        title = (m.title or m.caption or f"Kino #{m.code}").split("\n", 1)[0].strip()
        if len(title) > 32:
            title = title[:29] + "..."
        builder.button(text=f"🎬 {title} ({m.code})", callback_data=f"admin:movie:view:{m.code}")
    builder.adjust(1)

    max_pages = max(1, math.ceil(total / limit))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:movie:list:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{max_pages}", callback_data="admin:noop"))
    if (page + 1) * limit < total:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:movie:list:{page + 1}"))

    inline_keyboard = list(builder.as_markup().inline_keyboard)
    if nav_buttons:
        inline_keyboard.append(nav_buttons)
    inline_keyboard.append([
        InlineKeyboardButton(text="➕ Yangi qo'shish", callback_data="admin:movie:add"),
        InlineKeyboardButton(text="🔙 Kinolar menyusi", callback_data="admin:movies:menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def movies_delete_admin_keyboard(movies: list[Movie], page: int, total: int, limit: int = 5) -> InlineKeyboardMarkup:
    inline_keyboard = []
    for m in movies:
        title = (m.title or m.caption or f"Kino #{m.code}").split("\n", 1)[0].strip()
        if len(title) > 20:
            title = title[:17] + "..."
        inline_keyboard.append([
            InlineKeyboardButton(text=f"🎬 {title} (#{m.code})", callback_data=f"admin:movie:view:{m.code}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin:movdel:{m.code}:{page}"),
        ])

    max_pages = max(1, math.ceil(total / limit))
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin:movie:del_list:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{max_pages}", callback_data="admin:noop"))
    if (page + 1) * limit < total:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin:movie:del_list:{page + 1}"))

    if nav_buttons:
        inline_keyboard.append(nav_buttons)

    inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Kinolar menyusi", callback_data="admin:movies:menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def movie_detail_admin_keyboard(code: str, back_page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"admin:medit:title:{code}"),
                InlineKeyboardButton(text="🎭 Kategoriyani o'zgartirish", callback_data=f"admin:medit:cat:{code}"),
            ],
            [
                InlineKeyboardButton(text="📝 Tavsifni o'zgartirish", callback_data=f"admin:medit:desc:{code}"),
                InlineKeyboardButton(text="🎬 Videoni yangilash", callback_data=f"admin:medit:video:{code}"),
            ],
            [
                InlineKeyboardButton(text="🗑 Kinoni o'chirish", callback_data=f"admin:medit:del:{code}"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ro'yxatga qaytish", callback_data=f"admin:movie:list:{back_page}"),
            ],
        ]
    )


def movie_delete_confirm_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Ha, o'chirilsin!", callback_data=f"admin:mdel_yes:{code}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin:movie:view:{code}"),
            ]
        ]
    )


def channels_admin_keyboard(channels: list[RequiredChannel]) -> InlineKeyboardMarkup:
    inline_keyboard = []
    for ch in channels:
        title = ch.title[:25]
        inline_keyboard.append([
            InlineKeyboardButton(text=f"📢 {title}", url=ch.invite_link if ch.invite_link.startswith("http") else f"https://t.me/{ch.invite_link}"),
            InlineKeyboardButton(text="❌ O'chirish", callback_data=f"admin:chdel:{ch.chat_id}"),
        ])
    inline_keyboard.append([
        InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="admin:chadd"),
    ])
    inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Asosiy admin panel", callback_data="admin:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
