from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus
from database import add_admin, is_admin, log_action

router = Router()

@router.message(Command("make_admin"))
async def make_admin(message: Message):
    # Проверяем, что это группа
    if not message.chat.type in ("group", "supergroup"):
        await message.reply("Эта команда работает только в группах.")
        return

    # Проверяем, что пользователь имеет право назначать администраторов
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if not (member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR) and
            (member.can_promote_members or member.status == ChatMemberStatus.CREATOR)):
        await message.reply("Вы не можете назначать бота администратором (нет права can_promote_members).")
        return

    # Назначаем бота администратором, если ещё не админ
    bot_member = await message.bot.get_chat_member(message.chat.id, message.bot.id)
    if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
        try:
            await message.bot.promote_chat_member(
                message.chat.id,
                message.bot.id,
                can_change_info=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=False
            )
            await message.reply("✅ Бот назначен администратором группы. Теперь он может управлять подписками.")
        except Exception as e:
            await message.reply(f"❌ Не удалось назначить бота администратором: {e}")
            return
    else:
        await message.reply("🤖 Бот уже является администратором группы.")

    # Добавляем пользователя в администраторы бота (если ещё не добавлен)
    if not await is_admin(message.from_user.id):
        await add_admin(message.from_user.id, message.from_user.id)
        await log_action(message.from_user.id, "became_admin", "автоматически добавлен через /make_admin")
        await message.reply("✅ Вы также добавлены в администраторы бота. Теперь вы можете использовать /admin для доступа к панели.")
    else:
        await message.reply("Вы уже администратор бота.")