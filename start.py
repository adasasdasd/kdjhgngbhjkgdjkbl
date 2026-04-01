from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import add_user, log_action, is_admin
from services.payment_providers import create_cryptobot_invoice, create_xrocket_invoice
from config import ALLOWED_CHAT_ID, CUSTOM_EMOJI_IDS, CUSTOM_EMOJIS, SUBSCRIPTION_PRICES

router = Router()

class SubscriptionStates(StatesGroup):
    choosing_duration = State()
    entering_text = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await log_action(message.from_user.id, "start", "запустил бота")
    await state.clear()

    admin_btn = InlineKeyboardButton(
        text="Купить админку",
        callback_data="buy_admin",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["admin"]
    )
    broadcast_btn = InlineKeyboardButton(
        text="Купить рассылку",
        callback_data="buy_broadcast",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["broadcast"]
    )
    prefix_btn = InlineKeyboardButton(
        text="Купить префикс",
        callback_data="buy_prefix",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["stats"]
    )
    my_subs_btn = InlineKeyboardButton(
        text="Мои подписки",
        callback_data="my_subs",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["my_subs"]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [admin_btn],
        [broadcast_btn],
        [prefix_btn],
        [my_subs_btn]
    ])
    if await is_admin(message.from_user.id):
        admin_panel_btn = InlineKeyboardButton(
            text="Админ-панель",
            callback_data="admin_panel",
            icon_custom_emoji_id=CUSTOM_EMOJI_IDS["admin_panel"]
        )
        keyboard.inline_keyboard.append([admin_panel_btn])

    await message.answer(
        f"{CUSTOM_EMOJIS['greeting']} Добро пожаловать! Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "buy_admin")
async def buy_admin(callback: CallbackQuery, state: FSMContext):
    await state.update_data(sub_type="admin")
    await show_duration_options(callback.message, "admin", state)
    await callback.answer()

@router.callback_query(F.data == "buy_broadcast")
async def buy_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите текст для рассылки (будет отправляться каждые 30 минут):")
    await state.set_state(SubscriptionStates.entering_text)
    await state.update_data(sub_type="broadcast")
    await callback.answer()

@router.callback_query(F.data == "buy_prefix")
async def buy_prefix(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите текст префикса (например, [VIP]):")
    await state.set_state(SubscriptionStates.entering_text)
    await state.update_data(sub_type="prefix")
    await callback.answer()

@router.message(SubscriptionStates.entering_text)
async def process_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    data = await state.get_data()
    sub_type = data["sub_type"]
    await state.update_data(data_text=text)
    await show_duration_options(message, sub_type, state)

async def show_duration_options(message: Message, sub_type: str, state: FSMContext):
    prices = SUBSCRIPTION_PRICES[sub_type]
    buttons = []
    for duration_key, price in prices.items():
        # Отображаемое название срока
        if duration_key == "1week":
            display = "1 неделя"
        elif duration_key == "2weeks":
            display = "2 недели"
        elif duration_key == "1month":
            display = "1 месяц"
        elif duration_key == "3months":
            display = "3 месяца"
        elif duration_key == "6months":
            display = "6 месяцев"
        else:
            display = duration_key
        buttons.append([InlineKeyboardButton(
            text=f"{display} – {price}$",
            callback_data=f"duration_{sub_type}_{duration_key}"
        )])
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="back_to_start")])
    await message.answer("Выберите срок подписки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(SubscriptionStates.choosing_duration)

@router.callback_query(SubscriptionStates.choosing_duration, F.data.startswith("duration_"))
async def duration_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    # parts: ['duration', 'admin', '1week'] или ['duration', 'broadcast', '1month']
    sub_type = parts[1]
    duration = parts[2]
    await state.update_data(duration=duration)
    data = await state.get_data()
    sub_type = data["sub_type"]
    data_text = data.get("data_text", "")
    await show_payment_options(callback.message, sub_type, data_text, state, duration)
    await callback.answer()

async def show_payment_options(message: Message, sub_type: str, data_text: str, state: FSMContext, duration: str):
    price = SUBSCRIPTION_PRICES[sub_type][duration]
    cryptobot_btn = InlineKeyboardButton(
        text="CryptoBot",
        callback_data=f"pay_cryptobot_{sub_type}_{duration}_{data_text}",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["stats"]
    )
    xrocket_btn = InlineKeyboardButton(
        text="Xrocket",
        callback_data=f"pay_xrocket_{sub_type}_{duration}_{data_text}",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["broadcast"]
    )
    back_btn = InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_start",
        icon_custom_emoji_id=CUSTOM_EMOJI_IDS["back"]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [cryptobot_btn],
        [xrocket_btn],
        [back_btn]
    ])
    await message.answer(f"Выберите способ оплаты. Стоимость: {price} USD.", reply_markup=keyboard)

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split("_")
    provider = data_parts[1]          # cryptobot или xrocket
    sub_type = data_parts[2]
    duration = data_parts[3]
    data_text = data_parts[4] if len(data_parts) > 4 else ""
    user_id = callback.from_user.id

    amount = SUBSCRIPTION_PRICES[sub_type][duration]
    currency = "USD"

    if provider == "cryptobot":
        invoice = await create_cryptobot_invoice(amount, f"Подписка {sub_type} на {duration}")
        if invoice:
            from database import add_pending_payment
            payment_id = invoice["invoice_id"]
            await add_pending_payment(user_id, ALLOWED_CHAT_ID, sub_type, data_text, amount, currency, provider, payment_id, duration)
            await callback.message.answer(f"Оплатите по ссылке: {invoice['pay_url']}\nПосле оплаты подписка активируется автоматически.")
        else:
            await callback.message.answer("Ошибка создания счёта CryptoBot.")
    elif provider == "xrocket":
        invoice = await create_xrocket_invoice(amount, f"Подписка {sub_type} на {duration}")
        if invoice:
            from database import add_pending_payment
            payment_id = invoice["id"]
            await add_pending_payment(user_id, ALLOWED_CHAT_ID, sub_type, data_text, amount, currency, provider, payment_id, duration)
            await callback.message.answer(f"Оплатите по ссылке: {invoice['pay_url']}\nПосле оплаты подписка активируется автоматически.")
        else:
            await callback.message.answer("Ошибка создания счёта Xrocket.")
    await callback.answer()

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_start(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "my_subs")
async def my_subscriptions(callback: CallbackQuery):
    await callback.message.answer("Информация о подписках пока не реализована.")
    await callback.answer()

@router.callback_query(F.data == "admin_panel")
async def go_to_admin_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    from handlers.admin_panel import admin_panel
    await admin_panel(callback.message)
    await callback.answer()