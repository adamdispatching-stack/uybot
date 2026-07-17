import os

# ============================================================
#  НАСТРОЙКА / SOZLAMALAR
# ============================================================

# Порт веб-приложения / Veb-ilova porti
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# --- Хранение данных / Ma'lumotlarni saqlash ---
# На Railway том (volume) находится автоматически через
# RAILWAY_VOLUME_MOUNT_PATH — переменные DB_PATH/PHOTOS_DIR задавать не
# обязательно. Если они заданы, они имеют приоритет.
_here = os.path.dirname(__file__)
_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")  # e.g. /data — set by Railway

DB_PATH = os.getenv("DB_PATH") or (
    os.path.join(_volume, "realestate.db") if _volume
    else os.path.join(_here, "realestate.db"))

PHOTOS_DIR = os.getenv("PHOTOS_DIR") or (
    os.path.join(_volume, "photos") if _volume
    else os.path.join(_here, "photos"))

# --- Telegram-напоминания (необязательно) / Telegram eslatmalar (ixtiyoriy) ---
# Токен от @BotFather — через переменную окружения BOT_TOKEN (на Railway)
# или впишите сюда вместо пустой строки.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Часовой пояс и время ежедневного напоминания
TIMEZONE = "Asia/Tashkent"
REMINDER_HOUR = 9

# Повторять напоминание должникам каждые N дней после срока
REMIND_EVERY_DAYS = 2

print(f"[uyweb] DB_PATH={DB_PATH}  PHOTOS_DIR={PHOTOS_DIR}  "
      f"volume={'yes: ' + _volume if _volume else 'no'}")
