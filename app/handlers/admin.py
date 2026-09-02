import html
import math
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.filters.admin import IsAdmin
from app.keyboards.admin import (
    admin_keyboard,
    channels_admin_keyboard,
    movie_delete_confirm_keyboard,
    movie_detail_admin_keyboard,
    movies_crud_keyboard,
    movies_list_admin_keyboard,
)
from app.repositories.models import Movie, RequiredChannel
from app.services.container import Services
from app.utils.movie_helpers import format_movie_caption

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# --- FSM States ---
class AddMovie(StatesGroup):
    code = State()
    video = State()
    caption = State()
    category = State()


class EditMovie(StatesGroup):
    code = State()
    title = State()
    category = State()
    caption = State()
    video = State()


class SearchMovieAdmin(StatesGroup):
    query = State()


class DeleteMovieAdmin(StatesGroup):
    code = State()


class AddChannel(StatesGroup):
    forward_or_id = State()
    title = State()
    link = State()


class Broadcast(StatesGroup):
    message = State()


class AdminManagement(StatesGroup):
    user_id = State()


class SettingsManagement(StatesGroup):
    welcome = State()


# ==========================================
# 🏠 MAIN ADMIN PANEL
# ==========================================
@router.message(Command("admin"))
async def panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🏠 <b>Boshqaruv paneli (Admin Panel):</b>", reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🏠 <b>Boshqaruv paneli (Admin Panel):</b>", reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def statistics(callback: CallbackQuery, services: Services) -> None:
    await callback.answer("⏳ Statistika tayyorlanmoqda...")
    db_stats = await services.users.get_comprehensive_stats()
    text = await services.discovery.build_stats_report(db_stats)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=admin_keyboard(), parse_mode=ParseMode.HTML)


# ==========================================
# 🔐 REQUIRED CHANNELS (AUTO-FORWARD + CRUD)
# ==========================================
@router.callback_query(F.data.in_({"admin:channels", "admin:channels:menu"}))
async def channels_menu(callback: CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    await callback.answer()
    channels = await services.channels.list_required()
    text = (
        f"🔐 <b>Majburiy Obuna Kanallari ({len(channels)} ta):</b>\n\n"
        f"💡 <b>Tezkor qo'shish:</b> Kanaldan istalgan postni to'g'ridan-to'g'ri botga <b>Forward</b> qiling!\n"
        f"Bot kanalni o'zi aniqlab, havola yaratib ro'yxatga qo'shadi."
    )
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=channels_admin_keyboard(channels), parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "admin:chadd")
async def channel_add_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddChannel.forward_or_id)
    text = (
        "📢 <b>Kanal qo'shish:</b>\n\n"
        "1. Botni kanalingizga admin qiling.\n"
        "2. Kanaldan istalgan postni shu yerga <b>Forward</b> qiling!\n\n"
        "<i>(Yoki kanal Chat ID sini qo'lda yuboring, masalan: -100123456789)</i>"
    )
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.forward_origin | F.forward_from_chat)
async def auto_add_channel_forward(message: Message, state: FSMContext, services: Services) -> None:
    chat = None
    if message.forward_origin and getattr(message.forward_origin, "type", None) == "channel":
        chat = getattr(message.forward_origin, "chat", None)
    elif getattr(message, "forward_from_chat", None) and message.forward_from_chat.type == "channel":
        chat = message.forward_from_chat

    if not chat:
        return

    chat_id = chat.id
    title = chat.title or "Kanal"
    username = chat.username

    if username:
        invite_link = f"https://t.me/{username}"
    else:
        try:
            link_obj = await message.bot.create_chat_invite_link(chat_id, name="Bot obuna")
            invite_link = link_obj.invite_link
        except Exception:
            try:
                invite_link = await message.bot.export_chat_invite_link(chat_id)
            except Exception:
                invite_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/1"

    # Check bot admin status
    try:
        member = await message.bot.get_chat_member(chat_id, message.bot.id)
        is_admin = member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        is_admin = False

    await services.channels.add(RequiredChannel(chat_id, title, invite_link, "joinchat" in invite_link or "+" in invite_link))
    await services.subscriptions.invalidate_channels()
    await state.clear()

    admin_note = "✅ <b>Bot ushbu kanalda admin.</b>" if is_admin else "⚠️ <b>Eslatma:</b> Bot ushbu kanalda admin emas! Foydalanuvchilar obunasini to'liq tekshirish uchun botni kanalda admin qiling."
    text = (
        f"🎉 <b>Kanal muvaffaqiyatli majburiy obunalarga qo'shildi!</b>\n\n"
        f"📢 <b>Nomi:</b> {html.escape(title)}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"🔗 <b>Havola:</b> {invite_link}\n\n"
        f"{admin_note}"
    )
    channels = await services.channels.list_required()
    await message.answer(text, reply_markup=channels_admin_keyboard(channels), parse_mode=ParseMode.HTML)


@router.message(AddChannel.forward_or_id, F.text)
async def channel_manual_id(message: Message, state: FSMContext) -> None:
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Kanaldan post forward qiling yoki Chat ID ni son sifatida yuboring (masalan: -1001234567890).")
        return
    await state.update_data(chat_id=chat_id)
    await state.set_state(AddChannel.title)
    await message.answer("Kanal nomini yuboring:")


@router.message(AddChannel.title, F.text)
async def channel_manual_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text[:128].strip())
    await state.set_state(AddChannel.link)
    await message.answer("Kanal havolasini (invite link) yuboring:")


@router.message(AddChannel.link, F.text)
async def channel_manual_link(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    link = message.text.strip()
    await services.channels.add(RequiredChannel(data["chat_id"], data["title"], link, "joinchat" in link or "+" in link))
    await services.subscriptions.invalidate_channels()
    await state.clear()
    channels = await services.channels.list_required()
    await message.answer(f"✅ <b>{html.escape(data['title'])}</b> kanali saqlandi.", reply_markup=channels_admin_keyboard(channels), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:chdel:"))
async def channel_delete_callback(callback: CallbackQuery, services: Services) -> None:
    chat_id = int(callback.data[12:])
    await services.channels.deactivate(chat_id)
    await services.subscriptions.invalidate_channels()
    await callback.answer("✅ Kanal o'chirildi!")
    channels = await services.channels.list_required()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=channels_admin_keyboard(channels))


# ==========================================
# 🎬 MOVIES CRUD OPERATIONS
# ==========================================
@router.callback_query(F.data.in_({"admin:movies", "admin:movies:menu"}))
async def movies_crud_menu(callback: CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    await callback.answer()
    total = await services.movies.repository.count_active()
    text = (
        f"🎬 <b>Kinolar Boshqaruvi (CRUD):</b>\n\n"
        f"Bazada jami: <b>{total:,}</b> ta faol kino mavjud.\n\n"
        f"Kerakli bo'limni tanlang:"
    )
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


# 1. READ: List movies with pagination
@router.callback_query(F.data.startswith("admin:movie:list:"))
async def movies_list_paginated(callback: CallbackQuery, services: Services) -> None:
    page = int(callback.data[17:])
    limit = 5
    movies, total = await services.movies.repository.list_paginated(limit=limit, offset=page * limit)
    await callback.answer()
    text = f"📋 <b>Kinolar ro'yxati</b> (Jami: {total:,} ta):\n\nBatafsil ko'rish, tahrirlash yoki o'chirish uchun kinoni tanlang:"
    kb = movies_list_admin_keyboard(movies, page, total, limit=limit)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# 2. READ: View single movie detail
@router.callback_query(F.data.startswith("admin:movie:view:"))
async def movie_view_detail(callback: CallbackQuery, services: Services) -> None:
    code = callback.data[17:]
    movie = await services.movies.find(code)
    await callback.answer()
    if not movie:
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer("❌ Bu kino topilmadi yoki o'chirilgan.")
        return

    avg_rating, votes_count, _ = await services.movies.repository.get_rating_info(code)
    caption = format_movie_caption(movie, avg_rating, votes_count)
    kb = movie_detail_admin_keyboard(code)
    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.answer_video(
                movie.file_id,
                caption=caption,
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await callback.message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)


# 3. CREATE: Add movie flow
@router.callback_query(F.data == "admin:movie:add")
async def add_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddMovie.code)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🔢 <b>Yangi kino kodini yuboring:</b>\n<i>(Masalan: 123 yoki avatar_2)</i>", parse_mode=ParseMode.HTML)


@router.message(AddMovie.code, F.text)
async def add_movie_code(message: Message, state: FSMContext) -> None:
    code = message.text.strip().lower()
    if not code.replace("_", "").replace("-", "").isalnum() or len(code) > 64:
        await message.answer("❌ Kod faqat harf, raqam, _ yoki - bo'lishi mumkin.")
        return
    await state.update_data(code=code)
    await state.set_state(AddMovie.video)
    await message.answer("📹 <b>Videoni yuboring:</b>", parse_mode=ParseMode.HTML)


@router.message(AddMovie.video, F.video)
async def add_movie_video(message: Message, state: FSMContext) -> None:
    caption_with_video = message.caption or None
    await state.update_data(
        file_id=message.video.file_id,
        video_caption=caption_with_video,
    )
    await state.set_state(AddMovie.caption)
    await message.answer("🏷 <b>Kino nomini / sarlavhasini yuboring:</b>\n<i>(Masalan: Forsaj 10 yoki /skip yozing)</i>", parse_mode=ParseMode.HTML)


@router.message(AddMovie.caption, F.text)
async def add_movie_caption(message: Message, state: FSMContext) -> None:
    raw_text = message.text.strip()
    if raw_text == "/skip":
        title = None
        caption = None
    else:
        title = raw_text.split("\n", 1)[0].strip()[:255]
        caption = raw_text

    await state.update_data(title=title, caption=caption)
    await state.set_state(AddMovie.category)
    await message.answer("🎭 <b>Kategoriya nomini yuboring:</b>\n<i>(Masalan: Jangari, Komediya yoki /skip yozing)</i>", parse_mode=ParseMode.HTML)


@router.message(AddMovie.category, F.text)
async def add_movie_category(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    category = "Boshqa" if message.text.strip() == "/skip" else message.text.strip()[:48]

    title = data.get("title") or data.get("video_caption")
    caption = data.get("caption") or data.get("video_caption")
    if not title and not caption:
        title = f"Kino #{data['code']}"

    movie = Movie(
        code=data["code"],
        file_id=data["file_id"],
        title=title,
        caption=caption,
        category=category,
    )
    await services.movies.save(movie)
    await state.clear()
    kb = movie_detail_admin_keyboard(data["code"])
    await message.answer(
        f"✅ <b>Kino muvaffaqiyatli saqlandi!</b>\n\n"
        f"🎬 <b>Nomi:</b> {html.escape(movie.title or '')}\n"
        f"🔢 <b>Kodi:</b> <code>{movie.code}</code>\n"
        f"🎭 <b>Kategoriya:</b> {html.escape(movie.category)}",
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )


# 4. SEARCH: Search movie
@router.callback_query(F.data == "admin:movie:search")
async def search_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SearchMovieAdmin.query)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🔍 <b>Qidirmoqchi bo'lgan kino kodi yoki nomini yuboring:</b>", parse_mode=ParseMode.HTML)


@router.message(SearchMovieAdmin.query, F.text)
async def search_movie_query(message: Message, state: FSMContext, services: Services) -> None:
    query = message.text.strip()
    await state.clear()
    movie = await services.movies.find(query.lower())
    if movie:
        kb = movie_detail_admin_keyboard(movie.code)
        avg_rating, votes_count, _ = await services.movies.repository.get_rating_info(movie.code)
        caption = format_movie_caption(movie, avg_rating, votes_count)
        await message.answer(f"✅ <b>Kino topildi:</b>\n\n{caption}", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    movies = await services.movies.repository.search_by_title(query, limit=10)
    if movies:
        kb = movies_list_admin_keyboard(movies, page=0, total=len(movies), limit=10)
        await message.answer(f"🔍 <b>{len(movies)} ta kino topildi:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await message.answer("❌ Bunday kod yoki nomli kino topilmadi.", reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


# 5. UPDATE: Edit Movie Fields
@router.callback_query(F.data.startswith("admin:medit:title:"))
async def edit_title_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[18:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.title)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"✏️ <code>{code}</code> kodi uchun <b>yangi nom</b> kiriting:", parse_mode=ParseMode.HTML)


@router.message(EditMovie.title, F.text)
async def edit_title_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.title = message.text.strip()[:255]
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer(f"✅ Kino nomi <b>{html.escape(movie.title)}</b> ga o'zgartirildi!", reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:medit:cat:"))
async def edit_cat_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[16:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.category)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"🎭 <code>{code}</code> kodi uchun <b>yangi kategoriya</b> kiriting:", parse_mode=ParseMode.HTML)


@router.message(EditMovie.category, F.text)
async def edit_cat_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.category = message.text.strip()[:48]
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer(f"✅ Kategoriya <b>{html.escape(movie.category)}</b> ga o'zgartirildi!", reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:medit:desc:"))
async def edit_desc_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[17:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.caption)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"📝 <code>{code}</code> kodi uchun <b>yangi tavsif</b> kiriting (yoki /clear):", parse_mode=ParseMode.HTML)


@router.message(EditMovie.caption, F.text)
async def edit_desc_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.caption = None if message.text.strip() == "/clear" else message.text.strip()
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer("✅ Kino tavsifi yangilandi!", reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:medit:video:"))
async def edit_video_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[18:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.video)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"🎬 <code>{code}</code> kodi uchun <b>yangi videoni</b> yuboring:", parse_mode=ParseMode.HTML)


@router.message(EditMovie.video, F.video)
async def edit_video_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.file_id = message.video.file_id
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer("✅ Video fayli yangilandi!", reply_markup=kb, parse_mode=ParseMode.HTML)


# 6. DELETE: Delete movie with confirmation
@router.callback_query(F.data == "admin:movie:del_prompt")
async def delete_prompt_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(DeleteMovieAdmin.code)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🗑 <b>O'chirmoqchi bo'lgan kino kodini kiriting:</b>", parse_mode=ParseMode.HTML)


@router.message(DeleteMovieAdmin.code, F.text)
async def delete_movie_by_input(message: Message, state: FSMContext, services: Services) -> None:
    code = message.text.strip().lower()
    await state.clear()
    deleted = await services.movies.delete(code)
    if deleted:
        await message.answer(f"✅ <code>{code}</code> kodli kino o'chirildi.", reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)
    else:
        await message.answer("❌ Kino topilmadi.", reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:medit:del:"))
async def delete_movie_confirm_ask(callback: CallbackQuery) -> None:
    code = callback.data[16:]
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            f"⚠️ <b>Haqiqatan ham <code>{code}</code> kodli kinoni o'chirmoqchimisiz?</b>",
            reply_markup=movie_delete_confirm_keyboard(code),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data.startswith("admin:mdel_yes:"))
async def delete_movie_confirmed(callback: CallbackQuery, services: Services) -> None:
    code = callback.data[15:]
    await services.movies.delete(code)
    await callback.answer("✅ Kino o'chirildi!")
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"🗑 <code>{code}</code> kodli kino o'chirildi.", reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


# ==========================================
# ✉️ BROADCAST & ADMINS & SETTINGS
# ==========================================
@router.callback_query(F.data == "admin:broadcast")
async def broadcast_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Broadcast.message)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("✉️ <b>Yuboriladigan xabarni jo'nating:</b>\n<i>(Foydalanuvchilarga nusxa (copy_message) qilib yuboriladi)</i>", parse_mode=ParseMode.HTML)


@router.message(Broadcast.message)
async def create_broadcast(message: Message, state: FSMContext, services: Services) -> None:
    if message.from_user:
        await services.users.ensure_exists(message.from_user.id, message.from_user.username, message.from_user.full_name)
    creator_id = message.from_user.id if message.from_user else message.chat.id
    job_id = await services.broadcasts.create(creator_id, message.chat.id, message.message_id)
    await state.clear()
    progress = await message.answer(f"⏳ Broadcast #{job_id} tayyorlanmoqda...")
    await services.broadcasts.attach_progress_message(job_id, progress.chat.id, progress.message_id)


@router.callback_query(F.data == "admin:admins")
async def admins_menu(callback: CallbackQuery, state: FSMContext, services: Services) -> None:
    if not callback.from_user or not services.admins.is_root(callback.from_user.id):
        await callback.answer("Faqat bosh admin adminlarni boshqara oladi.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminManagement.user_id)
    existing = ", ".join(map(str, await services.admins.list_active())) or "yo'q"
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"👤 <b>Adminlar:</b> {existing}\n\nQo'shish uchun user ID yuboring.\nO'chirish: /deladmin USER_ID", parse_mode=ParseMode.HTML)


@router.message(AdminManagement.user_id, F.text, ~F.text.startswith("/deladmin"))
async def add_admin(message: Message, state: FSMContext, services: Services) -> None:
    if not message.from_user or not services.admins.is_root(message.from_user.id):
        return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("User ID son bo'lishi kerak.")
        return
    await services.admins.add(user_id)
    await state.clear()
    await message.answer(f"✅ {user_id} admin qilindi.")


@router.message(Command("deladmin"), F.text)
async def delete_admin(message: Message, services: Services) -> None:
    if not message.from_user or not services.admins.is_root(message.from_user.id):
        await message.answer("Faqat bosh admin bu amalni bajaradi.")
        return
    parts = message.text.split(maxsplit=1)
    try:
        user_id = int(parts[1])
    except (IndexError, ValueError):
        await message.answer("Foydalanish: /deladmin USER_ID")
        return
    deleted = await services.admins.deactivate(user_id)
    await message.answer("✅ Admin o'chirildi." if deleted else "❌ Bootstrap adminni o'chirib bo'lmaydi yoki topilmadi.")


@router.callback_query(F.data == "admin:settings")
async def settings_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsManagement.welcome)
    text = (
        "⚙️ <b>/start xabarini sozlash:</b>\n\n"
        "Foydalanuvchi /start bosganda chiqadigan yangi matnni yuboring.\n\n"
        "<i>(Standart matnga qaytarish uchun <code>/default</code> yozing yoki bekor qilish uchun <code>/cancel</code>)</i>"
    )
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, parse_mode=ParseMode.HTML)


@router.message(SettingsManagement.welcome, F.text)
async def set_welcome(message: Message, state: FSMContext, services: Services) -> None:
    raw_text = message.text.strip()
    if raw_text in {"/default", "/reset"}:
        from app.handlers.common import DEFAULT_WELCOME_TEXT
        await services.configuration.set("welcome_text", DEFAULT_WELCOME_TEXT)
        await state.clear()
        await message.answer("✅ /start xabari standart holatga qaytarildi.", reply_markup=admin_keyboard())
        return

    from app.handlers.common import INVALID_WELCOME_VALUES
    if raw_text in INVALID_WELCOME_VALUES:
        await message.answer("⚠️ Bu menyu tugmasi nomi. Iltimos, /start uchun haqiqiy xush kelibsiz matnini yuboring (yoki standartga qaytarish uchun /default):")
        return

    await services.configuration.set("welcome_text", raw_text[:4096])
    await state.clear()
    await message.answer("✅ /start xabari yangilandi.", reply_markup=admin_keyboard())
