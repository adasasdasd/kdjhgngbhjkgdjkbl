from aiogram import Router, F
from aiogram.types import Message

from database import get_active_subscription, log_action
from config import ALLOWED_CHAT_ID

router = Router()

@router.message(F.chat.id == ALLOWED_CHAT_ID)
async def handle_prefix_and_emoji(message: Message):
    prefix_sub = await get_active_subscription(message.from_user.id, message.chat.id, "prefix")
    emoji_sub = await get_active_subscription(message.from_user.id, message.chat.id, "emoji")

    if not prefix_sub and not emoji_sub:
        return

    new_text = message.text or ""

    if emoji_sub:
        emoji = emoji_sub[4]
        new_text = f"{emoji} {new_text}"

    if prefix_sub:
        prefix = prefix_sub[4]
        new_text = f"{prefix} {new_text}"

    try:
        await message.delete()
    except Exception as e:
        print(f"Ошибка удаления сообщения: {e}")

    await message.answer(new_text, parse_mode="HTML")

    await log_action(
        message.from_user.id,
        "prefix_emoji_used",
        f"префикс: {prefix_sub[4] if prefix_sub else ''} эмодзи: {emoji_sub[4] if emoji_sub else ''}"
    )