import os

# ============================================================
#  НАСТРОЙКА / SOZLAMALAR
# ============================================================

# Порт веб-приложения / Veb-ilova porti
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# Файл базы данных / Ma'lumotlar bazasi fayli
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "realestate.db"))

# --- Telegram-напоминания (необязательно) / Telegram eslatmalar (ixtiyoriy) ---
# 1) Создайте бота у @BotFather и вставьте токен сюда:
#    @BotFather orqali bot yarating va tokenni shu yerga qo'ying:
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# 2) Каждый пользователь указывает свой Telegram chat ID в «Настройках» приложения.
#    Узнать свой ID: напишите @userinfobot в Telegram.

# Часовой пояс и время ежедневного напоминания
TIMEZONE = "Asia/Tashkent"
REMINDER_HOUR = 9

# Повторять напоминание должникам каждые N дней после срока
REMIND_EVERY_DAYS = 2
