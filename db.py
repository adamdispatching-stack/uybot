# -*- coding: utf-8 -*-
"""SQLite database layer for the web app."""
import hashlib
import os
import secrets
import sqlite3
from datetime import date

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,             -- salt$pbkdf2hash
    name        TEXT,
    lang        TEXT DEFAULT 'ru',
    role        TEXT DEFAULT 'user',       -- admin | user
    tg_chat_id  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS houses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    address         TEXT NOT NULL,
    district        TEXT,
    deal_type       TEXT NOT NULL DEFAULT 'rent',      -- sale | rent
    status          TEXT NOT NULL DEFAULT 'available', -- available | rented | sold | reserved
    purchase_price  REAL,
    purchase_currency TEXT,
    purchase_date   TEXT,
    owner_name      TEXT,
    owner_phone     TEXT,
    notes           TEXT,
    sale_price      REAL,
    sale_currency   TEXT,
    sale_date       TEXT,
    sale_buyer      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS partners (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id    INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    share       REAL,
    invested    REAL,
    invested_currency TEXT
);
CREATE TABLE IF NOT EXISTS tenants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id    INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    phone       TEXT,
    passport    TEXT,
    rent_amount REAL NOT NULL,
    rent_currency TEXT DEFAULT 'UZS',
    due_day     INTEGER NOT NULL DEFAULT 1,
    move_in     TEXT,
    move_out    TEXT,
    active      INTEGER DEFAULT 1,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    house_id    INTEGER NOT NULL,
    amount      REAL NOT NULL,
    currency    TEXT DEFAULT 'UZS',
    period_year INTEGER NOT NULL,
    period_month INTEGER NOT NULL,
    paid_at     TEXT DEFAULT (date('now')),
    note        TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id    INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    amount      REAL NOT NULL,
    currency    TEXT DEFAULT 'UZS',
    spent_at    TEXT DEFAULT (date('now')),
    note        TEXT
);
CREATE TABLE IF NOT EXISTS photos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id    INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ---------------- auth ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return secrets.compare_digest(calc, h)


def users_count():
    with conn() as c:
        return c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]


def create_user(username, password, name=None, role="user", lang="ru"):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password, name, role, lang) VALUES (?,?,?,?,?)",
            (username.strip().lower(), hash_password(password), name or username, role, lang))
        return cur.lastrowid


def get_user_by_username(username):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE username=?",
                         (username.strip().lower(),)).fetchone()


def get_user(uid):
    with conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def list_users():
    with conn() as c:
        return c.execute("SELECT id, username, name, role, lang, tg_chat_id FROM users").fetchall()


def delete_user(uid):
    with conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))


def update_user(uid, **kw):
    allowed = {"name", "lang", "tg_chat_id"}
    sets, vals = [], []
    for k, v in kw.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if kw.get("password"):
        sets.append("password=?")
        vals.append(hash_password(kw["password"]))
    if not sets:
        return
    vals.append(uid)
    with conn() as c:
        c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    with conn() as c:
        c.execute("INSERT INTO sessions (token, user_id) VALUES (?,?)", (token, user_id))
    return token


def user_by_session(token):
    if not token:
        return None
    with conn() as c:
        return c.execute("""SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                            WHERE s.token=?""", (token,)).fetchone()


def delete_session(token):
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


# ---------------- houses ----------------
HOUSE_FIELDS = ["address", "district", "deal_type", "status", "purchase_price",
                "purchase_currency", "purchase_date", "owner_name", "owner_phone", "notes"]


def add_house(**kw):
    vals = [kw.get(f) for f in HOUSE_FIELDS]
    with conn() as c:
        cur = c.execute(
            f"INSERT INTO houses ({','.join(HOUSE_FIELDS)}) VALUES ({','.join('?' * len(HOUSE_FIELDS))})",
            vals)
        return cur.lastrowid


def update_house(hid, **kw):
    sets, vals = [], []
    for f in HOUSE_FIELDS:
        if f in kw:
            sets.append(f"{f}=?")
            vals.append(kw[f])
    if not sets:
        return
    vals.append(hid)
    with conn() as c:
        c.execute(f"UPDATE houses SET {', '.join(sets)} WHERE id=?", vals)


def get_house(hid):
    with conn() as c:
        return c.execute("SELECT * FROM houses WHERE id=?", (hid,)).fetchone()


def list_houses(flt="all"):
    q = "SELECT * FROM houses"
    if flt == "sale":
        q += " WHERE deal_type='sale' AND status != 'sold'"
    elif flt == "rent_free":
        q += " WHERE deal_type='rent' AND status='available'"
    elif flt == "rented":
        q += " WHERE status='rented'"
    elif flt == "sold":
        q += " WHERE status='sold'"
    elif flt == "available":
        q += " WHERE status='available'"
    q += " ORDER BY id DESC"
    with conn() as c:
        return c.execute(q).fetchall()


def set_house_status(hid, status):
    with conn() as c:
        c.execute("UPDATE houses SET status=? WHERE id=?", (status, hid))


def delete_house(hid):
    with conn() as c:
        c.execute("DELETE FROM houses WHERE id=?", (hid,))


def mark_sold(hid, price, currency, buyer, when=None):
    with conn() as c:
        c.execute("""UPDATE houses SET status='sold', sale_price=?, sale_currency=?,
                     sale_buyer=?, sale_date=? WHERE id=?""",
                  (price, currency, buyer, when or date.today().isoformat(), hid))


# ---------------- partners ----------------
def add_partner(house_id, name, share, invested, invested_currency):
    with conn() as c:
        c.execute("INSERT INTO partners (house_id,name,share,invested,invested_currency) VALUES (?,?,?,?,?)",
                  (house_id, name, share, invested, invested_currency))


def delete_partner(pid):
    with conn() as c:
        c.execute("DELETE FROM partners WHERE id=?", (pid,))


def list_partners(house_id):
    with conn() as c:
        return c.execute("SELECT * FROM partners WHERE house_id=?", (house_id,)).fetchall()


# ---------------- tenants ----------------
def add_tenant(**kw):
    fields = ["house_id", "name", "phone", "passport", "rent_amount",
              "rent_currency", "due_day", "move_in", "notes"]
    vals = [kw.get(f) for f in fields]
    with conn() as c:
        cur = c.execute(
            f"INSERT INTO tenants ({','.join(fields)}) VALUES ({','.join('?' * len(fields))})", vals)
        c.execute("UPDATE houses SET status='rented' WHERE id=?", (kw["house_id"],))
        return cur.lastrowid


def get_tenant(tid):
    with conn() as c:
        return c.execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()


def active_tenant_of_house(house_id):
    with conn() as c:
        return c.execute("SELECT * FROM tenants WHERE house_id=? AND active=1",
                         (house_id,)).fetchone()


def list_active_tenants():
    with conn() as c:
        return c.execute("""SELECT t.*, h.address FROM tenants t
                            JOIN houses h ON h.id = t.house_id
                            WHERE t.active=1 ORDER BY t.due_day""").fetchall()


def move_out(tid):
    with conn() as c:
        row = c.execute("SELECT house_id FROM tenants WHERE id=?", (tid,)).fetchone()
        c.execute("UPDATE tenants SET active=0, move_out=? WHERE id=?",
                  (date.today().isoformat(), tid))
        if row:
            c.execute("UPDATE houses SET status='available' WHERE id=?", (row["house_id"],))


def tenant_history(house_id):
    with conn() as c:
        return c.execute("""SELECT t.*,
                            COALESCE((SELECT SUM(amount) FROM payments p WHERE p.tenant_id=t.id),0) total_paid
                            FROM tenants t WHERE t.house_id=? ORDER BY t.id DESC""",
                         (house_id,)).fetchall()


# ---------------- payments ----------------
def add_payment(tenant_id, house_id, amount, currency, year, month, note=None):
    with conn() as c:
        c.execute("""INSERT INTO payments (tenant_id,house_id,amount,currency,period_year,period_month,note)
                     VALUES (?,?,?,?,?,?,?)""",
                  (tenant_id, house_id, amount, currency, year, month, note))


def delete_payment(pid):
    with conn() as c:
        c.execute("DELETE FROM payments WHERE id=?", (pid,))


def payment_exists(tenant_id, year, month):
    with conn() as c:
        return c.execute("SELECT 1 FROM payments WHERE tenant_id=? AND period_year=? AND period_month=?",
                         (tenant_id, year, month)).fetchone() is not None


def list_payments(house_id, limit=50):
    with conn() as c:
        return c.execute("""SELECT p.*, t.name tenant_name FROM payments p
                            JOIN tenants t ON t.id=p.tenant_id
                            WHERE p.house_id=? ORDER BY p.id DESC LIMIT ?""",
                         (house_id, limit)).fetchall()


def rent_income(house_id):
    with conn() as c:
        return c.execute("""SELECT currency, SUM(amount) total FROM payments
                            WHERE house_id=? GROUP BY currency""", (house_id,)).fetchall()


# ---------------- expenses ----------------
def add_expense(house_id, category, amount, currency, note=None, when=None):
    with conn() as c:
        c.execute("""INSERT INTO expenses (house_id,category,amount,currency,spent_at,note)
                     VALUES (?,?,?,?,?,?)""",
                  (house_id, category, amount, currency, when or date.today().isoformat(), note))


def delete_expense(eid):
    with conn() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (eid,))


def list_expenses(house_id, limit=100):
    with conn() as c:
        return c.execute("SELECT * FROM expenses WHERE house_id=? ORDER BY id DESC LIMIT ?",
                         (house_id, limit)).fetchall()


def expenses_total(house_id):
    with conn() as c:
        return c.execute("""SELECT currency, SUM(amount) total FROM expenses
                            WHERE house_id=? GROUP BY currency""", (house_id,)).fetchall()


# ---------------- reports ----------------
def debtors(today=None):
    today = today or date.today()
    res = []
    for tnt in list_active_tenants():
        if today.day >= tnt["due_day"] and not payment_exists(tnt["id"], today.year, today.month):
            d = dict(tnt)
            d["overdue_days"] = today.day - tnt["due_day"]
            res.append(d)
    return res


def month_summary(year, month):
    with conn() as c:
        income = c.execute("""SELECT currency, SUM(amount) total FROM payments
                              WHERE period_year=? AND period_month=? GROUP BY currency""",
                           (year, month)).fetchall()
        expense = c.execute("""SELECT currency, SUM(amount) total FROM expenses
                               WHERE strftime('%Y', spent_at)=? AND strftime('%m', spent_at)=?
                               GROUP BY currency""",
                            (str(year), f"{month:02d}")).fetchall()
        sales = c.execute("""SELECT sale_currency currency, SUM(sale_price) total FROM houses
                             WHERE sale_date IS NOT NULL
                               AND strftime('%Y', sale_date)=? AND strftime('%m', sale_date)=?
                             GROUP BY sale_currency""",
                          (str(year), f"{month:02d}")).fetchall()
    return income, expense, sales


# ---------------- photos ----------------
def add_photo(house_id, filename):
    with conn() as c:
        cur = c.execute("INSERT INTO photos (house_id, filename) VALUES (?,?)",
                        (house_id, filename))
        return cur.lastrowid


def list_photos(house_id):
    with conn() as c:
        return c.execute("SELECT * FROM photos WHERE house_id=? ORDER BY id", (house_id,)).fetchall()


def get_photo(pid):
    with conn() as c:
        return c.execute("SELECT * FROM photos WHERE id=?", (pid,)).fetchone()


def photo_filename_exists(filename):
    with conn() as c:
        return c.execute("SELECT 1 FROM photos WHERE filename=?", (filename,)).fetchone() is not None


def delete_photo(pid):
    with conn() as c:
        c.execute("DELETE FROM photos WHERE id=?", (pid,))


def first_photos():
    """house_id -> first photo filename, for list thumbnails."""
    with conn() as c:
        rows = c.execute("""SELECT house_id, MIN(id) mid FROM photos GROUP BY house_id""").fetchall()
        out = {}
        for r in rows:
            p = c.execute("SELECT filename FROM photos WHERE id=?", (r["mid"],)).fetchone()
            if p:
                out[r["house_id"]] = p["filename"]
        return out


# ---------------- analytics ----------------
def monthly_series(months=12):
    """Last N months of rent income (by period) and expenses (by date), per currency."""
    from datetime import date as _date
    today = _date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    out = [{"year": k[0], "month": k[1], "income": {}, "expense": {}} for k in keys]
    idx = {k: i for i, k in enumerate(keys)}
    with conn() as c:
        for r in c.execute("""SELECT period_year y, period_month m, currency, SUM(amount) total
                              FROM payments GROUP BY y, m, currency""").fetchall():
            k = (r["y"], r["m"])
            if k in idx:
                out[idx[k]]["income"][r["currency"]] = r["total"]
        for r in c.execute("""SELECT CAST(strftime('%Y', spent_at) AS INT) y,
                                     CAST(strftime('%m', spent_at) AS INT) m,
                                     currency, SUM(amount) total
                              FROM expenses GROUP BY y, m, currency""").fetchall():
            k = (r["y"], r["m"])
            if k in idx:
                out[idx[k]]["expense"][r["currency"]] = r["total"]
    return out


def houses_net():
    """Per house: rent income minus expenses, per currency; plus sold profit info."""
    res = []
    with conn() as c:
        for h in c.execute("SELECT * FROM houses ORDER BY id").fetchall():
            inc = {r["currency"]: r["total"] for r in c.execute(
                "SELECT currency, SUM(amount) total FROM payments WHERE house_id=? GROUP BY currency",
                (h["id"],)).fetchall()}
            exp = {r["currency"]: r["total"] for r in c.execute(
                "SELECT currency, SUM(amount) total FROM expenses WHERE house_id=? GROUP BY currency",
                (h["id"],)).fetchall()}
            net = {}
            for cur in set(inc) | set(exp):
                net[cur] = inc.get(cur, 0) - exp.get(cur, 0)
            if h["status"] == "sold" and h["sale_price"] and h["purchase_price"] \
                    and h["sale_currency"] == h["purchase_currency"]:
                cur = h["sale_currency"]
                net[cur] = net.get(cur, 0) + h["sale_price"] - h["purchase_price"]
            if net:
                res.append({"id": h["id"], "address": h["address"],
                            "status": h["status"], "net": net})
    return res


def counts():
    with conn() as c:
        return {
            "total": c.execute("SELECT COUNT(*) n FROM houses").fetchone()["n"],
            "sale": c.execute("SELECT COUNT(*) n FROM houses WHERE deal_type='sale' AND status!='sold'").fetchone()["n"],
            "rent_free": c.execute("SELECT COUNT(*) n FROM houses WHERE deal_type='rent' AND status='available'").fetchone()["n"],
            "rented": c.execute("SELECT COUNT(*) n FROM houses WHERE status='rented'").fetchone()["n"],
            "sold": c.execute("SELECT COUNT(*) n FROM houses WHERE status='sold'").fetchone()["n"],
        }
