import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, OWNER_ID
from database import init_db, is_admin, add_admin
from handlers import start, payments, admin, group_handlers
from handlers.admin_panel import router as admin_panel_router
from services.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    await init_db()

    if OWNER_ID and not await is_admin(OWNER_ID):
        await add_admin(OWNER_ID, OWNER_ID)
        print(f"Администратор {OWNER_ID} добавлен.")

    dp.include_router(start.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    dp.include_router(group_handlers.router)
    dp.include_router(admin_panel_router)
    setup_scheduler()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())