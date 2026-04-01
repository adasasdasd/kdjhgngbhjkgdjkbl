import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from config import ADMIN_CHAT_ID

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        """)
        # Таблица подписок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                type TEXT,
                data TEXT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица настроек чата (рассылка)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                broadcast_text TEXT,
                broadcast_user_id INTEGER
            )
        """)
        # Таблица ожидающих платежей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                type TEXT,
                data TEXT,
                amount REAL,
                currency TEXT,
                provider TEXT,
                payment_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица администраторов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Таблица логов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Миграция: добавить столбец admin_broadcast_text в chat_settings
        cursor = await db.execute("PRAGMA table_info(chat_settings)")
        columns = await cursor.fetchall()
        if not any(col[1] == 'admin_broadcast_text' for col in columns):
            await db.execute("ALTER TABLE chat_settings ADD COLUMN admin_broadcast_text TEXT")
            await db.commit()

        # Миграция: добавить столбец duration в pending_payments
        cursor = await db.execute("PRAGMA table_info(pending_payments)")
        columns = await cursor.fetchall()
        if not any(col[1] == 'duration' for col in columns):
            await db.execute("ALTER TABLE pending_payments ADD COLUMN duration TEXT")
            await db.commit()


# -------- Функции пользователей --------
async def add_user(user_id: int, username: str = "", full_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        await db.commit()


# -------- Подписки --------
async def add_subscription(user_id: int, chat_id: int, sub_type: str, data: str, expires_at: datetime) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO subscriptions (user_id, chat_id, type, data, expires_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, chat_id, sub_type, data, expires_at)
        )
        await db.commit()
        return cursor.lastrowid


async def get_active_subscription(user_id: int, chat_id: int, sub_type: str) -> Optional[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND chat_id = ? AND type = ? AND expires_at > ?",
            (user_id, chat_id, sub_type, datetime.now())
        ) as cursor:
            return await cursor.fetchone()


async def get_active_broadcast(chat_id: int) -> Optional[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM subscriptions WHERE chat_id = ? AND type = 'broadcast' AND expires_at > ?",
            (chat_id, datetime.now())
        ) as cursor:
            return await cursor.fetchone()


async def set_chat_broadcast(chat_id: int, text: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, broadcast_text, broadcast_user_id) VALUES (?, ?, ?)",
            (chat_id, text, user_id)
        )
        await db.commit()


async def clear_chat_broadcast(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE chat_settings SET broadcast_text = NULL, broadcast_user_id = NULL WHERE chat_id = ?",
            (chat_id,)
        )
        await db.commit()


async def get_chat_broadcast(chat_id: int) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT admin_broadcast_text, broadcast_text, broadcast_user_id FROM chat_settings WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0], row[1], row[2]
            return None, None, None


async def set_admin_broadcast(chat_id: int, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, admin_broadcast_text) VALUES (?, ?)",
            (chat_id, text)
        )
        await db.commit()


async def clear_admin_broadcast(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE chat_settings SET admin_broadcast_text = NULL WHERE chat_id = ?",
            (chat_id,)
        )
        await db.commit()


async def delete_expired_subscriptions() -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, user_id, chat_id, type, data FROM subscriptions WHERE expires_at <= ?",
            (datetime.now(),)
        ) as cursor:
            expired = await cursor.fetchall()
        await db.execute("DELETE FROM subscriptions WHERE expires_at <= ?", (datetime.now(),))
        await db.commit()
        return expired


# -------- Платежи --------
async def add_pending_payment(
    user_id: int,
    chat_id: int,
    sub_type: str,
    data: str,
    amount: float,
    currency: str,
    provider: str,
    payment_id: str = "",
    duration: str = ""
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO pending_payments 
               (user_id, chat_id, type, data, amount, currency, provider, payment_id, duration)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, chat_id, sub_type, data, amount, currency, provider, payment_id, duration)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_payment(payment_id: str, provider: str) -> Optional[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM pending_payments WHERE payment_id = ? AND provider = ? AND status = 'pending'",
            (payment_id, provider)
        ) as cursor:
            return await cursor.fetchone()


async def update_payment_status(payment_id: str, provider: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pending_payments SET status = ? WHERE payment_id = ? AND provider = ?",
            (status, payment_id, provider)
        )
        await db.commit()


# -------- Администраторы --------
async def add_admin(user_id: int, added_by: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                (user_id, added_by)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None


async def get_all_admins() -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM admins") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


# -------- Логи --------
async def log_action(user_id: int, action: str, details: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)",
            (user_id, action, details)
        )
        await db.commit()
    if ADMIN_CHAT_ID:
        try:
            from main import bot
            text = f"👤 Пользователь: {user_id}\n🔄 Действие: {action}\n📝 {details}"
            await bot.send_message(ADMIN_CHAT_ID, text)
        except Exception as e:
            print(f"Ошибка отправки лога в админ-чат: {e}")


async def get_recent_logs(limit: int = 50) -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, action, details, timestamp FROM logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ) as cursor:
            return await cursor.fetchall()


# -------- Статистика --------
async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]
        now = datetime.now().isoformat()
        async with db.execute(
            "SELECT type, COUNT(*) FROM subscriptions WHERE expires_at > ? GROUP BY type",
            (now,)
        ) as cursor:
            active_subs = {row[0]: row[1] for row in await cursor.fetchall()}
        async with db.execute("SELECT COUNT(*) FROM pending_payments WHERE status = 'pending'") as cursor:
            pending_payments = (await cursor.fetchone())[0]
        return {
            "total_users": total_users,
            "active_subs": active_subs,
            "pending_payments": pending_payments
        }