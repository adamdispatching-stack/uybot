# 🏠 UyWeb — веб-приложение для управления недвижимостью

Мобильное веб-приложение для риэлтора в Ташкенте: объекты, аренда, арендаторы,
платежи, расходы, партнёры, отчёты + **Telegram-напоминания об оплате**.

- Интерфейс: **Русский + O'zbekcha** (кнопка RU/UZ вверху)
- Валюты: **USD и UZS** (выбираются при каждой сумме)
- Работает в браузере телефона; можно добавить на главный экран как приложение
- Несколько пользователей (брат + партнёры), у каждого свой логин

---

## Возможности

- **🏠 Объекты** — фильтры: все / продажа / свободные / сданные / проданные.
  Карточка: владелец и его телефон, цена покупки, партнёры и доли, расходы,
  арендатор, доход с аренды, прибыль после продажи.
- **👥 Арендаторы** — заселение (имя, телефон, паспорт, аренда/мес, день оплаты),
  выселение с сохранением истории: кто жил, сколько, сколько всего заплатил.
- **💵 Оплаты** — приём оплаты за выбранный месяц, сумма подставляется сама.
  Значок «Оплачено / Не оплачено» на каждом объекте и арендаторе.
- **🧾 Расходы** — электричество, газ, вода, коммуналка, ремонт, другое.
- **📷 Фото** — к каждому объекту можно загрузить фотографии с телефона
  (сжимаются автоматически), миниатюра в списке, галерея в карточке.
- **🔎 Поиск и сортировка** — поиск по адресу, району, владельцу и арендатору;
  сортировка по цене.
- **📊 Отчёты и аналитика** — счётчики объектов, **должники** (с телефоном и днями
  просрочки), итоги месяца, график дохода/расходов за 12 месяцев по валютам,
  заполняемость, прибыль по каждому объекту.
- **🔐 Доступы для оплаты** — у каждого объекта: логины/пароли/лицевые счета для
  оплаты электричества, газа и т.д. Пароли скрыты точками (нажать — показать),
  кнопка 📋 копирует в буфер.
- **📋 Задачи** — дела по объектам (или общие) со сроками: «починить кран»,
  «показ квартиры». Просроченные подсвечиваются, входят в утреннее
  Telegram-напоминание.
- **🌐 Публичная страница** — ссылка `ваш-адрес/share` для клиентов: свободные
  объекты для продажи и аренды с фото, ценой из объявления и кнопкой «Позвонить».
  Владелец, цена покупки, партнёры и прочее приватное НЕ показываются.
  Название агентства и телефон задаются в ⚙️ Настройках; объект можно скрыть
  переключателем «Показывать на публичной странице».
- **🔔 Telegram** — каждый день в 9:00 (Ташкент) сервер сам присылает в Telegram,
  у кого сегодня день оплаты и кто просрочил (повтор каждые 2 дня до оплаты),
  плюс список задач на сегодня.

---

## Установка на VPS (5–10 минут)

```bash
sudo apt update && sudo apt install -y python3 python3-pip
# скопируйте папку uyweb на сервер, затем:
cd uyweb
pip3 install -r requirements.txt
python3 app.py
```

Откройте в браузере телефона: `http://IP-СЕРВЕРА:8080`

При первом входе приложение попросит **создать администратора** — придумайте
логин и пароль. Готово: можно добавлять объекты.

### Автозапуск 24/7 (systemd)

```bash
sudo nano /etc/systemd/system/uyweb.service
```

```ini
[Unit]
Description=UyWeb real estate app
After=network.target

[Service]
WorkingDirectory=/root/uyweb
ExecStart=/usr/bin/python3 /root/uyweb/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now uyweb
journalctl -u uyweb -f        # логи
```

---

## Telegram-напоминания (рекомендую включить)

1. В Telegram откройте **@BotFather** → `/newbot` → скопируйте **токен**.
2. Вставьте токен в `config.py`:
   ```python
   BOT_TOKEN = "1234567890:AAE..."
   ```
3. Перезапустите: `sudo systemctl restart uyweb`
4. Каждый пользователь: напишите своему боту `/start` (иначе Telegram не даст
   боту писать вам), узнайте свой ID у **@userinfobot** и вставьте его в
   приложении: ⚙️ Настройки → «Telegram chat ID» → Сохранить →
   «Проверить уведомление».

---

## HTTPS и красивый адрес (по желанию)

Если есть домен, проще всего поставить **Caddy** — он сам получает SSL-сертификат:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

`/etc/caddy/Caddyfile`:

```
uy.вашдомен.uz {
    reverse_proxy 127.0.0.1:8080
}
```

`sudo systemctl restart caddy` — и приложение доступно по `https://uy.вашдомен.uz`.

С HTTPS-адресом можно также сделать **Telegram Mini App**: в @BotFather →
`/mybots` → ваш бот → Bot Settings → Menu Button → вставьте URL приложения.
Тогда оно будет открываться прямо внутри Telegram.

---

## Важно

- **Все данные** — файл `realestate.db` + папка `photos/` (пути меняются
  переменными `DB_PATH` и `PHOTOS_DIR`). Бэкап раз в неделю:
  `cp realestate.db backup_$(date +%F).db`
- Добавить сотрудника: ⚙️ Настройки → «Добавить пользователя».
- День оплаты вводится 1–28, чтобы напоминания работали и в феврале.
- Порт меняется в `config.py` (`PORT`).

## Quick start (English)

1. Copy the `uyweb` folder to a VPS, `pip3 install -r requirements.txt`, `python3 app.py`.
2. Open `http://SERVER_IP:8080`, create the admin account on first run.
3. Optional Telegram reminders: put a @BotFather token into `config.py` → each user
   saves their chat ID (from @userinfobot) in Settings. Daily check at 9:00 Tashkent.
4. Use the systemd unit above to keep it running 24/7. `test_api.py` +
   `python3 app.py` = full offline test suite.

Files: `app.py` (FastAPI backend), `db.py` (SQLite), `notify.py` (Telegram),
`config.py` (settings), `static/index.html` (mobile UI, RU/UZ), `test_api.py`.
