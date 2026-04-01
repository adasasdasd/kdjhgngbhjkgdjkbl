from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import (
    is_admin, add_admin, get_all_admins, get_recent_logs, get_stats,
    log_action, set_admin_broadcast, clear_admin_broadcast, get_chat_broadcast
)
from config import ALLOWED_CHAT_ID, CUSTOM_EMOJI_IDS, CUSTOM_EMOJIS

router = Router()

class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    waiting_for_admin_broadcast_text = State()
    waiting_for_user_id_for_admin = State()

async def check_admin(user_id: int) -> bool:
    return await is_admin(user_id)

async def show_admin_panel(message: Message):
    admin_text, _, _ = await get_chat_broadcast(ALLOWED_CHAT_ID)
    broadcast_status = "✅ Активна" if admin_text else "❌ Неактивна"

    stats_btn = InlineKeyboardButton(
        text="Статистика",
        callback_data="admin_stats",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["stats"]
    )
    broadcast_btn = InlineKeyboardButton(
        text="Рассылка пользователям",
        callback_data="admin_broadcast",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["broadcast"]
    )
    admin_broadcast_btn = InlineKeyboardButton(
        text=f"Админ-рассылка ({broadcast_status})",
        callback_data="admin_set_broadcast",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["pinned"]
    )
    logs_btn = InlineKeyboardButton(
        text="Логи",
        callback_data="admin_logs",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["logs"]
    )
    list_btn = InlineKeyboardButton(
        text="Список админов",
        callback_data="admin_list",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["list"]
    )
    add_btn = InlineKeyboardButton(
        text="Добавить админа",
        callback_data="admin_add",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["add"]
    )
    close_btn = InlineKeyboardButton(
        text="Закрыть",
        callback_data="admin_close",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["close"]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [stats_btn],
        [broadcast_btn],
        [admin_broadcast_btn],
        [logs_btn],
        [list_btn],
        [add_btn],
        [close_btn]
    ])
    await message.answer(
        f"{CUSTOM_EMOJIS['admin_panel']} Панель администратора:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await check_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    await show_admin_panel(message)


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    stats = await get_stats()
    text = f"{CUSTOM_EMOJIS['stats']} Статистика:\n\n"
    text += f"{CUSTOM_EMOJIS['user']} Пользователей: {stats['total_users']}\n"
    text += f"{CUSTOM_EMOJIS['subscription']} Активных подписок:\n"
    for typ, count in stats['active_subs'].items():
        text += f"  - {typ}: {count}\n"
    text += f"{CUSTOM_EMOJIS['wait']} Ожидающих платежей: {stats['pending_payments']}"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]), parse_mode="HTML")
    await callback.answer()

# ========================= РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ =========================
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите текст для рассылки всем пользователям (личные сообщения):")
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def process_broadcast(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = message.text
    if not text:
        await message.answer("Текст не может быть пустым. Попробуйте снова.")
        return
    from database import DB_PATH
    import aiosqlite
    count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            for (user_id,) in users:
                try:
                    await message.bot.send_message(user_id, f"📢 Рассылка от администратора:\n\n{text}", parse_mode="HTML")
                    count += 1
                except Exception:
                    pass
    await message.answer(f"Рассылка завершена. Отправлено {count} сообщений.")
    await log_action(message.from_user.id, "broadcast", f"текст: {text[:100]}")
    await state.clear()
    await show_admin_panel(message)

# ========================= АДМИНСКАЯ РАССЫЛКА В ГРУППУ =========================
@router.callback_query(F.data == "admin_set_broadcast")
async def set_admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    admin_text, _, _ = await get_chat_broadcast(ALLOWED_CHAT_ID)
    if admin_text:
        back_btn = InlineKeyboardButton(
            text="Оставить текущую",
            callback_data="admin_back",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
        )
        change_btn = InlineKeyboardButton(
            text="Изменить",
            callback_data="admin_change_broadcast",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["admin"]
        )
        disable_btn = InlineKeyboardButton(
            text="Отключить",
            callback_data="admin_clear_broadcast",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["close"]
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_btn], [change_btn], [disable_btn]])
        await callback.message.edit_text(
            f"🔁 Админ-рассылка уже активна:\n\n{admin_text}\n\nЧто хотите сделать?",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    await callback.message.edit_text("Введите текст для админской рассылки (будет отправляться каждые 30 минут):")
    await state.set_state(AdminStates.waiting_for_admin_broadcast_text)
    await callback.answer()

@router.callback_query(F.data == "admin_change_broadcast")
async def change_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите новый текст для админской рассылки:")
    await state.set_state(AdminStates.waiting_for_admin_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_admin_broadcast_text)
async def process_admin_broadcast(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = message.text.strip()
    if not text:
        await message.answer("Текст не может быть пустым. Попробуйте снова.")
        return
    await set_admin_broadcast(ALLOWED_CHAT_ID, text)
    await log_action(message.from_user.id, "admin_broadcast_set", f"текст: {text[:100]}")
    await message.answer("✅ Админская рассылка установлена! Бот будет отправлять это сообщение каждые 30 минут.")
    await state.clear()
    await show_admin_panel(message)

@router.callback_query(F.data == "admin_clear_broadcast")
async def clear_admin_broadcast_callback(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await clear_admin_broadcast(ALLOWED_CHAT_ID)
    await log_action(callback.from_user.id, "admin_broadcast_cleared", "")
    await callback.message.edit_text("❌ Админская рассылка отключена.")
    await callback.answer()

# ========================= ЛОГИ =========================
@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    logs = await get_recent_logs(limit=20)
    if not logs:
        text = f"{CUSTOM_EMOJIS['logs']} Логов пока нет."
    else:
        text = f"{CUSTOM_EMOJIS['logs']} Последние действия:\n\n"
        for user_id, action, details, ts in logs:
            text += f"🕒 {ts}\n👤 {user_id}: {action}\n"
            if details:
                text += f"📝 {details}\n"
            text += "——————————\n"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]), parse_mode="HTML")
    await callback.answer()

# ========================= СПИСОК АДМИНОВ =========================
@router.callback_query(F.data == "admin_list")
async def list_admins(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    admins = await get_all_admins()
    if not admins:
        text = "👥 Список администраторов пуст."
    else:
        text = "👥 Администраторы:\n"
        for uid in admins:
            text += f"- {uid}\n"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]))
    await callback.answer()

# ========================= ДОБАВЛЕНИЕ АДМИНА =========================
@router.callback_query(F.data == "admin_add")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите ID пользователя, которого хотите сделать администратором:")
    await state.set_state(AdminStates.waiting_for_user_id_for_admin)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id_for_admin)
async def process_add_admin(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("ID должен быть числом. Попробуйте снова.")
        return
    success = await add_admin(user_id, message.from_user.id)
    if success:
        await message.answer(f"✅ Пользователь {user_id} добавлен в администраторы.")
        await log_action(message.from_user.id, "add_admin", f"добавлен {user_id}")
    else:
        await message.answer(f"⚠️ Пользователь {user_id} уже является администратором.")
    await state.clear()
    await show_admin_panel(message)

# ========================= НАЗАД В ГЛАВНОЕ МЕНЮ =========================
@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: CallbackQuery):
    await show_admin_panel(callback.message)
    await callback.answer()

# ========================= ЗАКРЫТИЕ ПАНЕЛИ =========================
@router.callback_query(F.data == "admin_close")
async def close_admin(callback: CallbackQuery):
    await callback.message.delete()
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import (
    is_admin, add_admin, get_all_admins, get_recent_logs, get_stats,
    log_action, set_admin_broadcast, clear_admin_broadcast, get_chat_broadcast
)
from config import ALLOWED_CHAT_ID, CUSTOM_EMOJI_IDS, CUSTOM_EMOJIS

router = Router()

class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    waiting_for_admin_broadcast_text = State()
    waiting_for_user_id_for_admin = State()

async def check_admin(user_id: int) -> bool:
    return await is_admin(user_id)

async def show_admin_panel(message: Message):
    admin_text, _, _ = await get_chat_broadcast(ALLOWED_CHAT_ID)
    broadcast_status = "✅ Активна" if admin_text else "❌ Неактивна"

    stats_btn = InlineKeyboardButton(
        text="Статистика",
        callback_data="admin_stats",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["stats"]
    )
    broadcast_btn = InlineKeyboardButton(
        text="Рассылка пользователям",
        callback_data="admin_broadcast",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["broadcast"]
    )
    admin_broadcast_btn = InlineKeyboardButton(
        text=f"Админ-рассылка ({broadcast_status})",
        callback_data="admin_set_broadcast",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["pinned"]
    )
    logs_btn = InlineKeyboardButton(
        text="Логи",
        callback_data="admin_logs",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["logs"]
    )
    list_btn = InlineKeyboardButton(
        text="Список админов",
        callback_data="admin_list",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["list"]
    )
    add_btn = InlineKeyboardButton(
        text="Добавить админа",
        callback_data="admin_add",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["add"]
    )
    close_btn = InlineKeyboardButton(
        text="Закрыть",
        callback_data="admin_close",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["close"]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [stats_btn],
        [broadcast_btn],
        [admin_broadcast_btn],
        [logs_btn],
        [list_btn],
        [add_btn],
        [close_btn]
    ])
    await message.answer(
        f"{CUSTOM_EMOJIS['admin_panel']} Панель администратора:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await check_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    await show_admin_panel(message)

# ========================= СТАТИСТИКА =========================
@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    stats = await get_stats()
    text = f"{CUSTOM_EMOJIS['stats']} Статистика:\n\n"
    text += f"{CUSTOM_EMOJIS['user']} Пользователей: {stats['total_users']}\n"
    text += f"{CUSTOM_EMOJIS['subscription']} Активных подписок:\n"
    for typ, count in stats['active_subs'].items():
        text += f"  - {typ}: {count}\n"
    text += f"{CUSTOM_EMOJIS['wait']} Ожидающих платежей: {stats['pending_payments']}"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]), parse_mode="HTML")
    await callback.answer()

# ========================= РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ =========================
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите текст для рассылки всем пользователям (личные сообщения):")
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_text)
async def process_broadcast(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = message.text
    if not text:
        await message.answer("Текст не может быть пустым. Попробуйте снова.")
        return
    from database import DB_PATH
    import aiosqlite
    count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            for (user_id,) in users:
                try:
                    await message.bot.send_message(user_id, f"📢 Рассылка от администратора:\n\n{text}", parse_mode="HTML")
                    count += 1
                except Exception:
                    pass
    await message.answer(f"Рассылка завершена. Отправлено {count} сообщений.")
    await log_action(message.from_user.id, "broadcast", f"текст: {text[:100]}")
    await state.clear()
    await show_admin_panel(message)

# ========================= АДМИНСКАЯ РАССЫЛКА В ГРУППУ =========================
@router.callback_query(F.data == "admin_set_broadcast")
async def set_admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    admin_text, _, _ = await get_chat_broadcast(ALLOWED_CHAT_ID)
    if admin_text:
        back_btn = InlineKeyboardButton(
            text="Оставить текущую",
            callback_data="admin_back",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
        )
        change_btn = InlineKeyboardButton(
            text="Изменить",
            callback_data="admin_change_broadcast",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["admin"]
        )
        disable_btn = InlineKeyboardButton(
            text="Отключить",
            callback_data="admin_clear_broadcast",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["close"]
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_btn], [change_btn], [disable_btn]])
        await callback.message.edit_text(
            f"🔁 Админ-рассылка уже активна:\n\n{admin_text}\n\nЧто хотите сделать?",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    await callback.message.edit_text("Введите текст для админской рассылки (будет отправляться каждые 30 минут):")
    await state.set_state(AdminStates.waiting_for_admin_broadcast_text)
    await callback.answer()

@router.callback_query(F.data == "admin_change_broadcast")
async def change_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите новый текст для админской рассылки:")
    await state.set_state(AdminStates.waiting_for_admin_broadcast_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_admin_broadcast_text)
async def process_admin_broadcast(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = message.text.strip()
    if not text:
        await message.answer("Текст не может быть пустым. Попробуйте снова.")
        return
    await set_admin_broadcast(ALLOWED_CHAT_ID, text)
    await log_action(message.from_user.id, "admin_broadcast_set", f"текст: {text[:100]}")
    await message.answer("✅ Админская рассылка установлена! Бот будет отправлять это сообщение каждые 30 минут.")
    await state.clear()
    await show_admin_panel(message)

@router.callback_query(F.data == "admin_clear_broadcast")
async def clear_admin_broadcast_callback(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await clear_admin_broadcast(ALLOWED_CHAT_ID)
    await log_action(callback.from_user.id, "admin_broadcast_cleared", "")
    await callback.message.edit_text("❌ Админская рассылка отключена.")
    await callback.answer()

# ========================= ЛОГИ =========================
@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    logs = await get_recent_logs(limit=20)
    if not logs:
        text = f"{CUSTOM_EMOJIS['logs']} Логов пока нет."
    else:
        text = f"{CUSTOM_EMOJIS['logs']} Последние действия:\n\n"
        for user_id, action, details, ts in logs:
            text += f"🕒 {ts}\n👤 {user_id}: {action}\n"
            if details:
                text += f"📝 {details}\n"
            text += "——————————\n"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]), parse_mode="HTML")
    await callback.answer()

# ========================= СПИСОК АДМИНОВ =========================
@router.callback_query(F.data == "admin_list")
async def list_admins(callback: CallbackQuery):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    admins = await get_all_admins()
    if not admins:
        text = "👥 Список администраторов пуст."
    else:
        text = "👥 Администраторы:\n"
        for uid in admins:
            text += f"- {uid}\n"
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="admin_back",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_btn]]))
    await callback.answer()

# ========================= ДОБАВЛЕНИЕ АДМИНА =========================
@router.callback_query(F.data == "admin_add")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите ID пользователя, которого хотите сделать администратором:")
    await state.set_state(AdminStates.waiting_for_user_id_for_admin)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id_for_admin)
async def process_add_admin(message: Message, state: FSMContext):
    if not await check_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("ID должен быть числом. Попробуйте снова.")
        return
    success = await add_admin(user_id, message.from_user.id)
    if success:
        await message.answer(f"✅ Пользователь {user_id} добавлен в администраторы.")
        await log_action(message.from_user.id, "add_admin", f"добавлен {user_id}")
    else:
        await message.answer(f"⚠️ Пользователь {user_id} уже является администратором.")
    await state.clear()
    await show_admin_panel(message)

# ========================= НАЗАД В ГЛАВНОЕ МЕНЮ =========================
@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: CallbackQuery):
    await show_admin_panel(callback.message)
    await callback.answer()

# ========================= ЗАКРЫТИЕ ПАНЕЛИ =========================
@router.callback_query(F.data == "admin_close")
async def close_admin(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()