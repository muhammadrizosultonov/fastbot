import asyncio
import contextlib
import html
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.filters.admin import IsAdmin
from app.keyboards.admin import (
    ADMIN_ADMINS,
    ADMIN_BACK_TO_USER,
    ADMIN_BROADCAST,
    ADMIN_CHANNELS,
    ADMIN_MOVIES,
    ADMIN_SETTINGS,
    ADMIN_STATS,
    admin_keyboard,
    admin_reply_keyboard,
    channels_admin_keyboard,
    movie_delete_confirm_keyboard,
    movie_detail_admin_keyboard,
    movies_crud_keyboard,
    movies_delete_admin_keyboard,
    movies_list_admin_keyboard,
)
from app.keyboards.user import RANDOM, TOP_MOVIES, user_menu
from app.repositories.models import Movie, RequiredChannel
from app.services.container import Services
from app.utils.movie_helpers import format_movie_caption

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AddChannel(StatesGroup):
    forward_or_id = State()
    title = State()
    link = State()


class AddMovie(StatesGroup):
    code = State()
    title = State()
    file_id = State()
    caption = State()


class EditMovie(StatesGroup):
    title = State()
    caption = State()
    video = State()


class DeleteMovieAdmin(StatesGroup):
    code = State()


class Broadcast(StatesGroup):
    message = State()


class AdminManagement(StatesGroup):
    user_id = State()


class SettingsManagement(StatesGroup):
    welcome = State()


# ==========================================
# 🏠 MAIN ADMIN PANEL
# ==========================================
@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=admin_reply_keyboard())


@router.message(Command("admin"))
async def panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🏠 <b>Boshqaruv paneli (Admin Panel):</b>\n\nQuyidagi menyu orqali kerakli bo'limni tanlang:",
        reply_markup=admin_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text == ADMIN_BACK_TO_USER)
async def back_to_user_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🎬 <b>Foydalanuvchi menyusiga qaytdingiz.</b>",
        reply_markup=user_menu(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            "🏠 <b>Boshqaruv paneli (Admin Panel):</b>",
            reply_markup=admin_reply_keyboard(),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(F.data == "admin:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(F.text == ADMIN_STATS)
@router.callback_query(F.data == "admin:stats")
async def statistics(event: Message | CallbackQuery, services: Services) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer("⏳ Statistika tayyorlanmoqda...")
        msg = event.message
    else:
        msg = event

    db_stats = await services.users.get_comprehensive_stats()
    text = await services.discovery.build_stats_report(db_stats)
    if msg and isinstance(msg, Message):
        await msg.answer(text, reply_markup=admin_reply_keyboard(), parse_mode=ParseMode.HTML)


# ==========================================
# 🔐 REQUIRED CHANNELS (AUTO-FORWARD + CRUD)
# ==========================================
@router.message(F.text == ADMIN_CHANNELS)
@router.callback_query(F.data.in_({"admin:channels", "admin:channels:menu"}))
async def channels_menu(event: Message | CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    channels = await services.channels.list_required()
    text = (
        f"🔐 <b>Majburiy Obuna Kanallari ({len(channels)} ta):</b>\n\n"
        f"💡 <b>Tezkor qo'shish:</b> Kanaldan istalgan postni to'g'ridan-to'g'ri botga <b>Forward</b> qiling!\n"
        f"Bot kanalni o'zi aniqlab, zayavkali havola yaratib ro'yxatga qo'shadi."
    )
    if msg and isinstance(msg, Message):
        await msg.answer(text, reply_markup=channels_admin_keyboard(channels), parse_mode=ParseMode.HTML)


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

    # Check bot admin status
    try:
        member = await message.bot.get_chat_member(chat_id, message.bot.id)
        is_admin = member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        is_admin = False

    is_join_req = False
    invite_link = None

    if is_admin:
        try:
            link_obj = await message.bot.create_chat_invite_link(
                chat_id,
                name="Bot obuna (Zayavka)",
                creates_join_request=True,
            )
            invite_link = link_obj.invite_link
            is_join_req = True
        except Exception:
            pass

    if not invite_link:
        if username:
            invite_link = f"https://t.me/{username}"
            is_join_req = False
        else:
            try:
                link_obj = await message.bot.create_chat_invite_link(chat_id, name="Bot obuna")
                invite_link = link_obj.invite_link
                is_join_req = True
            except Exception:
                try:
                    invite_link = await message.bot.export_chat_invite_link(chat_id)
                    is_join_req = True
                except Exception:
                    invite_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/1"
                    is_join_req = True

    await services.channels.add(RequiredChannel(chat_id, title, invite_link, is_join_req))
    await services.subscriptions.invalidate_channels()
    await state.clear()

    admin_note = "✅ <b>Bot ushbu kanalda admin. Zayavka havolasi avtomatik yaratildi!</b>" if is_admin else "⚠️ <b>Eslatma:</b> Bot ushbu kanalda admin emas! Foydalanuvchilar obunasi to'liq ishlashi uchun botni kanalda admin qiling."
    text = (
        f"🎉 <b>Kanal muvaffaqiyatli majburiy obunalarga qo'shildi!</b>\n\n"
        f"📢 <b>Nomi:</b> {html.escape(title)}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"🔗 <b>Avtomatik havola:</b> {invite_link}\n"
        f"📩 <b>Turi:</b> {'Zayavkali kanal (Join Request)' if is_join_req else 'Ochiq kanal'}\n\n"
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
@router.message(F.text == ADMIN_MOVIES)
@router.callback_query(F.data.in_({"admin:movies", "admin:movies:menu"}))
async def movies_crud_menu(event: Message | CallbackQuery, state: FSMContext, services: Services) -> None:
    await state.clear()
    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    total = await services.movies.repository.count_active()
    text = (
        f"🎬 <b>Kinolar Boshqaruvi:</b>\n\n"
        f"Bazada jami: <b>{total:,}</b> ta faol kino mavjud.\n\n"
        f"Kerakli amalni tanlang:"
    )
    if msg and isinstance(msg, Message):
        await msg.answer(text, reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


# 1. READ: List movies with pagination
@router.callback_query(F.data.startswith("admin:movie:list:"))
async def movies_list_paginated(callback: CallbackQuery, services: Services) -> None:
    page = int(callback.data[17:])
    limit = 5
    movies, total = await services.movies.repository.list_paginated(limit=limit, offset=page * limit)
    await callback.answer()
    text = f"📋 <b>Kinolar ro'yxati</b> (Jami: {total:,} ta):\n\nBatafsil ko'rish yoki tahrirlash uchun tanlang:"
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


# 3. CREATE: Add new movie wizard (4 steps: kodi, nomi, media, izohi)
@router.callback_query(F.data == "admin:movie:add")
async def add_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AddMovie.code)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🎬 <b>Yangi kino qo'shish (1/4):</b>\n\nKino kodini yuboring (masalan: <code>101</code>):", parse_mode=ParseMode.HTML)


@router.message(AddMovie.code, F.text)
async def add_movie_code(message: Message, state: FSMContext, services: Services) -> None:
    code = message.text.strip().lower()
    existing = await services.movies.find(code)
    if existing:
        await message.answer(f"⚠️ <code>{code}</code> kodli kino allaqachon mavjud! Boshqa kod yuboring:", parse_mode=ParseMode.HTML)
        return
    await state.update_data(code=code)
    await state.set_state(AddMovie.title)
    await message.answer("🎬 <b>(2/4)</b> Kino nomini yuboring (masalan: <i>Forsaj 10</i>):", parse_mode=ParseMode.HTML)


@router.message(AddMovie.title, F.text)
async def add_movie_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AddMovie.file_id)
    await message.answer("🎬 <b>(3/4)</b> Kinoning <b>video yoki rasmini</b> yuboring:", parse_mode=ParseMode.HTML)


@router.message(AddMovie.file_id, F.video | F.photo | F.document | F.animation)
async def add_movie_media(message: Message, state: FSMContext) -> None:
    if message.video:
        file_id = message.video.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.animation:
        file_id = message.animation.file_id
    else:
        await message.answer("Iltimos, video yoki rasm yuboring.")
        return
    await state.update_data(file_id=file_id)
    await state.set_state(AddMovie.caption)
    await message.answer("🎬 <b>(4/4)</b> Video/rasm tagidagi <b>izohni</b> yuboring (yoki bo'sh qoldirish uchun <code>-</code>):", parse_mode=ParseMode.HTML)


@router.message(AddMovie.caption, F.text)
async def add_movie_finish(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    raw_caption = message.text.strip()
    caption = "" if raw_caption == "-" else raw_caption

    movie = Movie(
        code=data["code"],
        file_id=data["file_id"],
        title=data["title"],
        caption=caption,
        category="Boshqa",
    )
    await services.movies.save(movie)
    await state.clear()
    caption_display = movie.caption if movie.caption else "(yo'q)"
    text = (
        f"🎉 <b>Kino muvaffaqiyatli saqlandi!</b>\n\n"
        f"🔢 <b>Kodi:</b> <code>{movie.code}</code>\n"
        f"🎬 <b>Nomi:</b> {html.escape(movie.title or '')}\n"
        f"📝 <b>Izoh:</b> {html.escape(caption_display)}"
    )
    await message.answer(text, reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)


# 4. DELETE: Direct list with delete button next to each movie
@router.callback_query(F.data.startswith("admin:movie:del_list:"))
async def movies_delete_list(callback: CallbackQuery, services: Services) -> None:
    page = int(callback.data[21:])
    limit = 5
    movies, total = await services.movies.repository.list_paginated(limit=limit, offset=page * limit)
    await callback.answer()
    text = (
        f"🗑 <b>Kinolar o'chirish ro'yxati</b> (Jami: {total:,} ta):\n\n"
        f"O'chirmoqchi bo'lgan kinongiz yonidagi <b>«🗑 O'chirish»</b> tugmasini bosing:"
    )
    kb = movies_delete_admin_keyboard(movies, page, total, limit=limit)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:movdel:"))
async def movie_delete_direct_callback(callback: CallbackQuery, services: Services) -> None:
    parts = callback.data.split(":")
    code = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    await services.movies.delete(code)
    await callback.answer(f"✅ #{code} kodli kino o'chirildi!", show_alert=True)

    limit = 5
    movies, total = await services.movies.repository.list_paginated(limit=limit, offset=page * limit)
    if not movies and page > 0:
        page -= 1
        movies, total = await services.movies.repository.list_paginated(limit=limit, offset=page * limit)

    text = (
        f"🗑 <b>Kinolar o'chirish ro'yxati</b> (Jami: {total:,} ta):\n\n"
        f"O'chirmoqchi bo'lgan kinongiz yonidagi <b>«🗑 O'chirish»</b> tugmasini bosing:"
    )
    kb = movies_delete_admin_keyboard(movies, page, total, limit=limit)
    if callback.message and isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)


# 5. UPDATE: Edit movie fields
@router.callback_query(F.data.startswith("admin:medit:title:"))
async def edit_title_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[18:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.title)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"🎬 <code>{code}</code> kodi uchun <b>yangi nom</b> kiriting:", parse_mode=ParseMode.HTML)


@router.message(EditMovie.title, F.text)
async def edit_title_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.title = message.text.strip()
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer(f"✅ Kino nomi <b>{html.escape(movie.title)}</b> ga o'zgartirildi!", reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data.startswith("admin:medit:desc:"))
async def edit_desc_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data[17:]
    await state.update_data(edit_code=code)
    await state.set_state(EditMovie.caption)
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(f"📝 <code>{code}</code> kodi uchun <b>yangi izohni</b> kiriting (yoki tozalash uchun <code>-</code>):", parse_mode=ParseMode.HTML)


@router.message(EditMovie.caption, F.text)
async def edit_desc_save(message: Message, state: FSMContext, services: Services) -> None:
    data = await state.get_data()
    code = data["edit_code"]
    movie = await services.movies.find(code)
    if movie:
        movie.caption = "" if message.text.strip() == "-" else message.text.strip()
        await services.movies.save(movie)
        await state.clear()
        kb = movie_detail_admin_keyboard(code)
        await message.answer("✅ Kino izohi yangilandi!", reply_markup=kb, parse_mode=ParseMode.HTML)


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
@router.message(F.text == ADMIN_BROADCAST)
@router.callback_query(F.data == "admin:broadcast")
async def broadcast_menu(event: Message | CallbackQuery, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    await state.set_state(Broadcast.message)
    if msg and isinstance(msg, Message):
        await msg.answer("✉️ <b>Yuboriladigan xabarni jo'nating:</b>\n<i>(Foydalanuvchilarga nusxa (copy_message) qilib yuboriladi, bekor qilish: /cancel)</i>", parse_mode=ParseMode.HTML)


@router.message(Broadcast.message)
async def create_broadcast(message: Message, state: FSMContext, services: Services) -> None:
    if message.text and message.text.startswith("/"):
        await state.clear()
        return

    job_id = await services.broadcasts.enqueue(
        creator_id=message.from_user.id,
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        progress_chat_id=message.chat.id,
    )
    await state.clear()
    status_msg = await message.answer(
        f"🚀 <b>Xabar yuborish navbatga qo'shildi!</b> (Job #{job_id})\n\n"
        f"📊 Holat: <i>Boshlanmoqda...</i>",
        reply_markup=admin_reply_keyboard(),
        parse_mode=ParseMode.HTML,
    )

    async def poll_progress() -> None:
        for _ in range(300):
            await asyncio.sleep(2)
            job = await services.broadcasts.jobs.get(job_id)
            if not job:
                break
            stats = await services.broadcasts.get_stats(job_id)
            with contextlib.suppress(Exception):
                await status_msg.edit_text(
                    f"🚀 <b>Xabar yuborilmoqda:</b> Job #{job_id}\n\n"
                    f"📊 <b>Holat:</b> {job.status.upper()}\n"
                    f"✅ Yuborildi: <b>{stats.get('sent', 0):,}</b> ta\n"
                    f"❌ Xatolik: <b>{stats.get('failed', 0):,}</b> ta\n"
                    f"⏳ Qolgan: <b>{stats.get('pending', 0):,}</b> ta",
                    parse_mode=ParseMode.HTML,
                )
            if job.status in {"finished", "failed", "cancelled"}:
                break

    asyncio.create_task(poll_progress())


@router.message(F.text == ADMIN_ADMINS)
@router.callback_query(F.data == "admin:admins")
async def admins_menu(event: Message | CallbackQuery, state: FSMContext, services: Services) -> None:
    user_id = event.from_user.id if event.from_user else 0
    if not services.admins.is_root(user_id):
        if isinstance(event, CallbackQuery):
            await event.answer("Faqat bosh admin adminlarni boshqara oladi.", show_alert=True)
        else:
            await event.answer("Faqat bosh admin adminlarni boshqara oladi.")
        return

    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    await state.set_state(AdminManagement.user_id)
    existing = ", ".join(map(str, await services.admins.list_active())) or "yo'q"
    if msg and isinstance(msg, Message):
        await msg.answer(f"👤 <b>Adminlar:</b> {existing}\n\nQo'shish uchun user ID yuboring.\nO'chirish: /deladmin USER_ID", parse_mode=ParseMode.HTML)


@router.message(AdminManagement.user_id, F.text, ~F.text.startswith("/deladmin"))
async def add_admin(message: Message, state: FSMContext, services: Services) -> None:
    if not message.from_user or not services.admins.is_root(message.from_user.id):
        return
    text = message.text.strip()
    if text.startswith("/") or text in {ADMIN_MOVIES, ADMIN_CHANNELS, ADMIN_STATS, ADMIN_BROADCAST, ADMIN_ADMINS, ADMIN_SETTINGS, ADMIN_BACK_TO_USER, RANDOM, TOP_MOVIES}:
        await state.clear()
        if text == "/cancel":
            await message.answer("❌ Bekor qilindi.", reply_markup=admin_reply_keyboard())
            return
        if text == ADMIN_MOVIES:
            total = await services.movies.repository.count_active()
            await message.answer(f"🎬 <b>Kinolar Boshqaruvi:</b> (Bazada {total:,} ta kino)", reply_markup=movies_crud_keyboard(), parse_mode=ParseMode.HTML)
            return
        if text == ADMIN_STATS:
            db_stats = await services.users.get_comprehensive_stats()
            t = await services.discovery.build_stats_report(db_stats)
            await message.answer(t, reply_markup=admin_reply_keyboard(), parse_mode=ParseMode.HTML)
            return

    try:
        user_id = int(text)
    except ValueError:
        await message.answer("❌ User ID faqat son bo'lishi kerak (masalan: <code>123456789</code>).\nBekor qilish uchun: /cancel", parse_mode=ParseMode.HTML)
        return
    await services.admins.add(user_id)
    await state.clear()
    await message.answer(f"✅ <code>{user_id}</code> admin qilindi.", reply_markup=admin_reply_keyboard(), parse_mode=ParseMode.HTML)


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


@router.message(F.text == ADMIN_SETTINGS)
@router.callback_query(F.data == "admin:settings")
async def settings_menu(event: Message | CallbackQuery, state: FSMContext) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer()
        msg = event.message
    else:
        msg = event

    await state.set_state(SettingsManagement.welcome)
    text = (
        "⚙️ <b>/start xabarini sozlash:</b>\n\n"
        "Foydalanuvchi /start bosganda chiqadigan yangi matnni yuboring.\n\n"
        "<i>(Standart matnga qaytarish uchun <code>/default</code> yozing yoki bekor qilish uchun <code>/cancel</code>)</i>"
    )
    if msg and isinstance(msg, Message):
        await msg.answer(text, parse_mode=ParseMode.HTML)


@router.message(SettingsManagement.welcome, F.text)
async def set_welcome(message: Message, state: FSMContext, services: Services) -> None:
    raw_text = message.text.strip()
    if raw_text in {"/default", "/reset"}:
        from app.handlers.common import DEFAULT_WELCOME_TEXT
        await services.configuration.set("welcome_text", DEFAULT_WELCOME_TEXT)
        await state.clear()
        await message.answer("✅ /start xabari standart holatga qaytarildi.", reply_markup=admin_reply_keyboard())
        return

    from app.handlers.common import INVALID_WELCOME_VALUES
    if raw_text in INVALID_WELCOME_VALUES:
        await message.answer("⚠️ Bu menyu tugmasi nomi. Iltimos, /start uchun haqiqiy xush kelibsiz matnini yuboring (yoki standartga qaytarish uchun /default):")
        return

    await services.configuration.set("welcome_text", raw_text[:4096])
    await state.clear()
    await message.answer("✅ /start xabari yangilandi.", reply_markup=admin_reply_keyboard())
