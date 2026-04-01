from aiogram import Router, F
from aiogram.types import PreCheckoutQuery, Message, SuccessfulPayment

from database import get_pending_payment, update_payment_status, log_action
from services.subscription import activate_subscription

router = Router()

@router.pre_checkout_query()
async def pre_checkout_query(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payment_id = payment.invoice_payload
    pending = await get_pending_payment(payment_id, "stars")
    if pending:
        await update_payment_status(payment_id, "stars", "paid")
        user_id, chat_id, sub_type, data, duration = pending[1], pending[2], pending[3], pending[4], pending[10]
        await activate_subscription(user_id, chat_id, sub_type, data, duration)
        await log_action(message.from_user.id, "payment_success", f"{sub_type} через Stars")
        await message.answer("Подписка активирована! Спасибо за покупку.")
    else:
        await message.answer("Ошибка активации подписки.")