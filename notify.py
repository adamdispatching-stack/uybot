# -*- coding: utf-8 -*-
"""Telegram reminders: daily rent-due / overdue notifications."""
import logging
from datetime import date

import httpx

import db
from config import BOT_TOKEN, REMIND_EVERY_DAYS

log = logging.getLogger(__name__)

MONTHS = {
    "ru": ["январь", "февраль", "март", "апрель", "май", "июнь",
           "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"],
}


def fmt_money(amount, currency, lang="ru"):
    if amount is None:
        return "—"
    num = f"{int(amount):,}".replace(",", " ") if amount == int(amount) \
        else f"{amount:,.2f}".replace(",", " ")
    return f"${num}" if currency == "USD" else f"{num} {'so’m' if lang == 'uz' else 'сум'}"


async def send_telegram(chat_id: str, text: str) -> bool:
    if not BOT_TOKEN or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"chat_id": chat_id, "text": text,
                                             "parse_mode": "HTML"})
            if r.status_code != 200:
                log.warning("telegram send failed %s: %s", chat_id, r.text[:200])
            return r.status_code == 200
    except Exception as e:
        log.warning("telegram send error: %s", e)
        return False


def build_reminder_text(tnt, today, lang):
    period = f"{MONTHS[lang if lang in MONTHS else 'ru'][today.month - 1]} {today.year}"
    money = fmt_money(tnt["rent_amount"], tnt["rent_currency"], lang)
    phone = tnt["phone"] or "—"
    overdue = today.day - tnt["due_day"]
    if lang == "uz":
        if overdue == 0:
            head = "🔔 <b>Bugun to'lov kuni!</b>"
        else:
            head = f"🔴 <b>{overdue} kun kechikdi!</b>"
        return (f"{head}\n👤 {tnt['name']} ({phone})\n🏠 {tnt['address']}\n"
                f"💰 {money} — {period} uchun\nTo'lov kuni: {tnt['due_day']}-sana")
    if overdue == 0:
        head = "🔔 <b>Сегодня день оплаты!</b>"
    else:
        head = f"🔴 <b>Просрочка {overdue} дн.!</b>"
    return (f"{head}\n👤 {tnt['name']} ({phone})\n🏠 {tnt['address']}\n"
            f"💰 {money} за {period}\nДень оплаты: {tnt['due_day']}-го")


async def check_rents():
    """Daily job: notify every user who saved a Telegram chat ID."""
    if not BOT_TOKEN:
        return
    today = date.today()
    users = [u for u in db.list_users() if u["tg_chat_id"]]
    if not users:
        return
    for tnt in db.list_active_tenants():
        if db.payment_exists(tnt["id"], today.year, today.month):
            continue
        if today.day < tnt["due_day"]:
            continue
        overdue = today.day - tnt["due_day"]
        if overdue != 0 and overdue % REMIND_EVERY_DAYS != 0:
            continue
        for u in users:
            await send_telegram(u["tg_chat_id"],
                                build_reminder_text(tnt, today, u["lang"] or "ru"))

    # due / overdue tasks
    tasks = db.due_tasks(today.isoformat())
    if tasks:
        for u in users:
            lang = u["lang"] or "ru"
            head = "📋 <b>Задачи на сегодня:</b>" if lang == "ru" else "📋 <b>Bugungi vazifalar:</b>"
            lines = [head]
            for tk in tasks:
                s = f"• {tk['title']}"
                if tk["address"]:
                    s += f" — 🏠 {tk['address']}"
                if tk["due_date"] < today.isoformat():
                    s += " ⚠️"
                lines.append(s)
            await send_telegram(u["tg_chat_id"], "\n".join(lines))
