import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN در فایل .env تنظیم نشده است")

if not ADMIN_IDS:
    raise ValueError("ADMIN_ID در فایل .env تنظیم نشده است")

ADMIN_IDS = int(ADMIN_IDS)