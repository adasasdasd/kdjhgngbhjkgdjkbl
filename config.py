import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print(f"ОШИБКА: BOT_TOKEN не найден в {env_path}")
    exit(1)

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
CRYPTOBOT_API_URL = "https://pay.crypt.bot/api"
XROCKET_API_KEY = os.getenv("XROCKET_API_KEY")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", -1001234567890))
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
OWNER_ID = int(os.getenv("OWNER_ID", 0))

# Цены подписок (в долларах США) – ключи без подчёркиваний!
SUBSCRIPTION_PRICES = {
    "admin": {
        "1week": 33,
        "2weeks": 40,
        "1month": 60
    },
    "broadcast": {
        "1week": 21,
        "2weeks": 30,
        "1month": 70
    },
    "prefix": {
        "1month": 25,
        "3months": 70,
        "6months": 110
    }
}

# Длительность в днях для каждого типа и срока
DURATIONS = {
    "admin": {
        "1week": 7,
        "2weeks": 14,
        "1month": 30
    },
    "broadcast": {
        "1week": 7,
        "2weeks": 14,
        "1month": 30
    },
    "prefix": {
        "1month": 30,
        "3months": 90,
        "6months": 180
    }
}

# ID кастомных премиум-эмодзи
CUSTOM_EMOJI_IDS = {
    "stats": "5275979556308674886",
    "broadcast": "5278528159837348960",
    "admin": "5276262671962892944",
    "logs": "5424972470023104089",
    "list": "5395695537687123235",
    "add": "5406683434124859552",
    "close": "5406683434124859552",
    "back": "5395695537687123235",
    "success": "5251203410396458957",
    "error": "5215346626817713558",
    "wait": "5424972470023104089",
    "user": "5275979556308674886",
    "subscription": "5395695537687123235",
    "greeting": "5278611606756942667",
    "my_subs": "5278578973595427038",
    "pinned": "5278305362703835500",
    "admin_panel": "5276262671962892944",
    "top_up": "5276398496008663230",
    "pin_week": "5274099962655816924",
    "prefix_month": "5275979556308674886",
    "autoposting": "5278528159837348960",
    "buy_ad": "5278528159837348960",
}

# HTML-теги для текстовых сообщений
CUSTOM_EMOJIS = {key: f'<tg-emoji emoji-id="{CUSTOM_EMOJI_IDS[key]}">😎</tg-emoji>' for key in CUSTOM_EMOJI_IDS}