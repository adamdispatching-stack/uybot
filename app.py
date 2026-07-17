# -*- coding: utf-8 -*-
"""UyWeb — real estate management web app. Run: python3 app.py"""
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import db
import notify
from config import BOT_TOKEN, DB_PATH, HOST, PHOTOS_DIR, PORT, REMINDER_HOUR, TIMEZONE

STATIC = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)) or ".", exist_ok=True)
MAX_PHOTO_MB = 10
SAFE_PHOTO = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp)$")


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(notify.check_rents, CronTrigger(hour=REMINDER_HOUR, minute=0),
                      misfire_grace_time=3600)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="UyWeb", lifespan=lifespan)


# ------------------- auth -------------------
def current_user(request: Request):
    user = db.user_by_session(request.cookies.get("session"))
    if not user:
        raise HTTPException(401, "not authenticated")
    return user


def admin_user(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "admin only")
    return user


class LoginIn(BaseModel):
    username: str
    password: str


class SetupIn(BaseModel):
    username: str
    password: str
    name: str | None = None


@app.get("/api/state")
def api_state(request: Request):
    """Bootstrap: is setup needed, who am I."""
    user = db.user_by_session(request.cookies.get("session"))
    return {
        "needs_setup": db.users_count() == 0,
        "user": {"id": user["id"], "username": user["username"], "name": user["name"],
                 "role": user["role"], "lang": user["lang"],
                 "tg_chat_id": user["tg_chat_id"],
                 "tg_enabled": bool(BOT_TOKEN)} if user else None,
    }


@app.post("/api/setup")
def api_setup(body: SetupIn, response: Response):
    if db.users_count() > 0:
        raise HTTPException(400, "already set up")
    if len(body.username.strip()) < 3 or len(body.password) < 4:
        raise HTTPException(400, "username min 3 chars, password min 4")
    uid = db.create_user(body.username, body.password, body.name, role="admin")
    token = db.create_session(uid)
    response.set_cookie("session", token, httponly=True, max_age=180 * 24 * 3600,
                        samesite="lax")
    return {"ok": True}


@app.post("/api/login")
def api_login(body: LoginIn, response: Response):
    user = db.get_user_by_username(body.username)
    if not user or not db.verify_password(body.password, user["password"]):
        raise HTTPException(401, "wrong credentials")
    token = db.create_session(user["id"])
    response.set_cookie("session", token, httponly=True, max_age=180 * 24 * 3600,
                        samesite="lax")
    return {"ok": True}


@app.post("/api/logout")
def api_logout(request: Request, response: Response):
    db.delete_session(request.cookies.get("session"))
    response.delete_cookie("session")
    return {"ok": True}


class ProfileIn(BaseModel):
    name: str | None = None
    lang: str | None = None
    tg_chat_id: str | None = None
    password: str | None = None


@app.post("/api/profile")
def api_profile(body: ProfileIn, user=Depends(current_user)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "lang" in data and data["lang"] not in ("ru", "uz"):
        raise HTTPException(400, "bad lang")
    db.update_user(user["id"], **data)
    return {"ok": True}


class UserIn(BaseModel):
    username: str
    password: str
    name: str | None = None
    role: str = "user"


@app.get("/api/users")
def api_users(user=Depends(admin_user)):
    return db.rows_to_dicts(db.list_users())


@app.post("/api/users")
def api_users_create(body: UserIn, user=Depends(admin_user)):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "bad role")
    if db.get_user_by_username(body.username):
        raise HTTPException(400, "username taken")
    if len(body.username.strip()) < 3 or len(body.password) < 4:
        raise HTTPException(400, "username min 3 chars, password min 4")
    db.create_user(body.username, body.password, body.name, role=body.role)
    return {"ok": True}


@app.delete("/api/users/{uid}")
def api_users_delete(uid: int, user=Depends(admin_user)):
    if uid == user["id"]:
        raise HTTPException(400, "cannot delete yourself")
    db.delete_user(uid)
    return {"ok": True}


@app.post("/api/test-telegram")
async def api_test_telegram(user=Depends(current_user)):
    me = db.get_user(user["id"])
    if not BOT_TOKEN:
        raise HTTPException(400, "BOT_TOKEN not set in config.py")
    if not me["tg_chat_id"]:
        raise HTTPException(400, "no chat id saved")
    ok = await notify.send_telegram(
        me["tg_chat_id"],
        "✅ UyWeb: уведомления работают! / Bildirishnomalar ishlayapti!")
    if not ok:
        raise HTTPException(400, "send failed — check token and chat id")
    return {"ok": True}


# ------------------- houses -------------------
class HouseIn(BaseModel):
    address: str
    district: str | None = None
    deal_type: str = "rent"
    purchase_price: float | None = None
    purchase_currency: str | None = None
    purchase_date: str | None = None
    owner_name: str | None = None
    owner_phone: str | None = None
    notes: str | None = None
    list_price: float | None = None
    list_currency: str | None = None
    public: int = 1
    public_desc: str | None = None


def house_full(hid):
    h = db.get_house(hid)
    if not h:
        raise HTTPException(404, "house not found")
    d = dict(h)
    d["partners"] = db.rows_to_dicts(db.list_partners(hid))
    d["expenses"] = db.rows_to_dicts(db.list_expenses(hid))
    d["expenses_total"] = db.rows_to_dicts(db.expenses_total(hid))
    d["payments"] = db.rows_to_dicts(db.list_payments(hid))
    d["rent_income"] = db.rows_to_dicts(db.rent_income(hid))
    tnt = db.active_tenant_of_house(hid)
    d["tenant"] = dict(tnt) if tnt else None
    if d["tenant"]:
        today = date.today()
        d["tenant"]["paid_this_month"] = db.payment_exists(tnt["id"], today.year, today.month)
    d["history"] = db.rows_to_dicts(db.tenant_history(hid))
    d["photos"] = db.rows_to_dicts(db.list_photos(hid))
    d["accounts"] = db.rows_to_dicts(db.list_accounts(hid))
    d["tasks"] = db.rows_to_dicts(db.list_tasks(hid, include_done=False))
    # profit for sold house (same currency only)
    if d["status"] == "sold" and d["sale_price"] and d["purchase_price"] \
            and d["purchase_currency"] == d["sale_currency"]:
        exp = sum(r["total"] for r in d["expenses_total"]
                  if r["currency"] == d["sale_currency"])
        d["profit"] = d["sale_price"] - d["purchase_price"] - exp
        d["profit_currency"] = d["sale_currency"]
    return d


@app.get("/api/houses")
def api_houses(flt: str = "all", user=Depends(current_user)):
    houses = db.rows_to_dicts(db.list_houses(flt))
    today = date.today()
    thumbs = db.first_photos()
    for h in houses:
        h["thumb"] = thumbs.get(h["id"])
        tnt = db.active_tenant_of_house(h["id"])
        if tnt:
            h["tenant_name"] = tnt["name"]
            h["rent_amount"] = tnt["rent_amount"]
            h["rent_currency"] = tnt["rent_currency"]
            h["paid_this_month"] = db.payment_exists(tnt["id"], today.year, today.month)
    return houses


@app.post("/api/houses")
def api_houses_create(body: HouseIn, user=Depends(current_user)):
    if body.deal_type not in ("sale", "rent"):
        raise HTTPException(400, "bad deal_type")
    hid = db.add_house(status="available", **body.model_dump())
    return house_full(hid)


@app.get("/api/houses/{hid}")
def api_house(hid: int, user=Depends(current_user)):
    return house_full(hid)


@app.patch("/api/houses/{hid}")
def api_house_update(hid: int, body: HouseIn, user=Depends(current_user)):
    if not db.get_house(hid):
        raise HTTPException(404, "house not found")
    db.update_house(hid, **body.model_dump())
    return house_full(hid)


class StatusIn(BaseModel):
    status: str


@app.post("/api/houses/{hid}/status")
def api_house_status(hid: int, body: StatusIn, user=Depends(current_user)):
    if body.status not in ("available", "rented", "sold", "reserved"):
        raise HTTPException(400, "bad status")
    db.set_house_status(hid, body.status)
    return house_full(hid)


@app.delete("/api/houses/{hid}")
def api_house_delete(hid: int, user=Depends(current_user)):
    db.delete_house(hid)
    return {"ok": True}


class SoldIn(BaseModel):
    price: float
    currency: str
    buyer: str | None = None
    date: str | None = None


@app.post("/api/houses/{hid}/sold")
def api_house_sold(hid: int, body: SoldIn, user=Depends(current_user)):
    if not db.get_house(hid):
        raise HTTPException(404, "house not found")
    db.mark_sold(hid, body.price, body.currency, body.buyer, body.date)
    return house_full(hid)


# ------------------- partners -------------------
class PartnerIn(BaseModel):
    name: str
    share: float | None = None
    invested: float | None = None
    invested_currency: str | None = "USD"


@app.post("/api/houses/{hid}/partners")
def api_partner_add(hid: int, body: PartnerIn, user=Depends(current_user)):
    if not db.get_house(hid):
        raise HTTPException(404, "house not found")
    db.add_partner(hid, body.name, body.share, body.invested, body.invested_currency)
    return house_full(hid)


@app.delete("/api/partners/{pid}")
def api_partner_delete(pid: int, user=Depends(current_user)):
    db.delete_partner(pid)
    return {"ok": True}


# ------------------- tenants -------------------
class TenantIn(BaseModel):
    name: str
    phone: str | None = None
    passport: str | None = None
    rent_amount: float
    rent_currency: str = "UZS"
    due_day: int = 1
    move_in: str | None = None
    notes: str | None = None


@app.get("/api/tenants")
def api_tenants(user=Depends(current_user)):
    tenants = db.rows_to_dicts(db.list_active_tenants())
    today = date.today()
    for t in tenants:
        t["paid_this_month"] = db.payment_exists(t["id"], today.year, today.month)
    return tenants


@app.post("/api/houses/{hid}/tenants")
def api_tenant_add(hid: int, body: TenantIn, user=Depends(current_user)):
    house = db.get_house(hid)
    if not house:
        raise HTTPException(404, "house not found")
    if db.active_tenant_of_house(hid):
        raise HTTPException(400, "house already has active tenant")
    if not 1 <= body.due_day <= 28:
        raise HTTPException(400, "due_day must be 1..28")
    db.add_tenant(house_id=hid, move_in=body.move_in or date.today().isoformat(),
                  **body.model_dump(exclude={"move_in"}))
    return house_full(hid)


@app.post("/api/tenants/{tid}/moveout")
def api_tenant_moveout(tid: int, user=Depends(current_user)):
    tnt = db.get_tenant(tid)
    if not tnt:
        raise HTTPException(404, "tenant not found")
    db.move_out(tid)
    return house_full(tnt["house_id"])


# ------------------- payments -------------------
class PaymentIn(BaseModel):
    tenant_id: int
    amount: float
    currency: str
    period_year: int
    period_month: int
    note: str | None = None


@app.post("/api/payments")
def api_payment_add(body: PaymentIn, user=Depends(current_user)):
    tnt = db.get_tenant(body.tenant_id)
    if not tnt:
        raise HTTPException(404, "tenant not found")
    db.add_payment(body.tenant_id, tnt["house_id"], body.amount, body.currency,
                   body.period_year, body.period_month, body.note)
    return {"ok": True}


@app.delete("/api/payments/{pid}")
def api_payment_delete(pid: int, user=Depends(current_user)):
    db.delete_payment(pid)
    return {"ok": True}


# ------------------- expenses -------------------
class ExpenseIn(BaseModel):
    house_id: int
    category: str
    amount: float
    currency: str
    note: str | None = None
    date: str | None = None


@app.post("/api/expenses")
def api_expense_add(body: ExpenseIn, user=Depends(current_user)):
    if not db.get_house(body.house_id):
        raise HTTPException(404, "house not found")
    if body.category not in ("electricity", "gas", "water", "communal", "repair", "other"):
        raise HTTPException(400, "bad category")
    db.add_expense(body.house_id, body.category, body.amount, body.currency,
                   body.note, body.date)
    return {"ok": True}


@app.delete("/api/expenses/{eid}")
def api_expense_delete(eid: int, user=Depends(current_user)):
    db.delete_expense(eid)
    return {"ok": True}


# ------------------- photos -------------------
EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@app.post("/api/houses/{hid}/photos")
async def api_photo_upload(hid: int, file: UploadFile = File(...), user=Depends(current_user)):
    if not db.get_house(hid):
        raise HTTPException(404, "house not found")
    ext = EXT_BY_TYPE.get(file.content_type)
    if not ext:
        raise HTTPException(400, "only JPEG/PNG/WebP images")
    data = await file.read()
    if len(data) > MAX_PHOTO_MB * 1024 * 1024:
        raise HTTPException(400, f"photo too large (max {MAX_PHOTO_MB} MB)")
    filename = secrets.token_hex(16) + "." + ext
    with open(os.path.join(PHOTOS_DIR, filename), "wb") as f:
        f.write(data)
    db.add_photo(hid, filename)
    return {"photos": db.rows_to_dicts(db.list_photos(hid))}


@app.get("/photos/{filename}")
def api_photo_get(filename: str):
    if not SAFE_PHOTO.match(filename) or not db.photo_filename_exists(filename):
        raise HTTPException(404, "not found")
    path = os.path.join(PHOTOS_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "not found")
    return FileResponse(path)


@app.delete("/api/photos/{pid}")
def api_photo_delete(pid: int, user=Depends(current_user)):
    p = db.get_photo(pid)
    if p:
        try:
            os.remove(os.path.join(PHOTOS_DIR, p["filename"]))
        except OSError:
            pass
        db.delete_photo(pid)
    return {"ok": True}


# ------------------- utility accounts -------------------
class AccountIn(BaseModel):
    label: str
    account_no: str | None = None
    login: str | None = None
    password: str | None = None
    note: str | None = None


@app.post("/api/houses/{hid}/accounts")
def api_account_add(hid: int, body: AccountIn, user=Depends(current_user)):
    if not db.get_house(hid):
        raise HTTPException(404, "house not found")
    db.add_account(hid, body.label, body.account_no, body.login, body.password, body.note)
    return {"accounts": db.rows_to_dicts(db.list_accounts(hid))}


@app.delete("/api/accounts/{aid}")
def api_account_delete(aid: int, user=Depends(current_user)):
    db.delete_account(aid)
    return {"ok": True}


# ------------------- tasks -------------------
class TaskIn(BaseModel):
    title: str
    house_id: int | None = None
    due_date: str | None = None


@app.get("/api/tasks")
def api_tasks(user=Depends(current_user)):
    return db.rows_to_dicts(db.list_tasks())


@app.post("/api/tasks")
def api_task_add(body: TaskIn, user=Depends(current_user)):
    if not body.title.strip():
        raise HTTPException(400, "empty title")
    if body.house_id and not db.get_house(body.house_id):
        raise HTTPException(404, "house not found")
    db.add_task(body.title.strip(), body.house_id, body.due_date)
    return {"ok": True}


@app.post("/api/tasks/{tid}/toggle")
def api_task_toggle(tid: int, user=Depends(current_user)):
    db.toggle_task(tid)
    return {"ok": True}


@app.delete("/api/tasks/{tid}")
def api_task_delete(tid: int, user=Depends(current_user)):
    db.delete_task(tid)
    return {"ok": True}


# ------------------- public share page -------------------
class OrgIn(BaseModel):
    contact_phone: str | None = None
    agency_name: str | None = None


@app.get("/api/org")
def api_org_get(user=Depends(current_user)):
    return {"contact_phone": db.get_setting("contact_phone", ""),
            "agency_name": db.get_setting("agency_name", "")}


@app.post("/api/org")
def api_org_set(body: OrgIn, user=Depends(admin_user)):
    if body.contact_phone is not None:
        db.set_setting("contact_phone", body.contact_phone.strip())
    if body.agency_name is not None:
        db.set_setting("agency_name", body.agency_name.strip())
    return {"ok": True}


@app.get("/api/public/listings")
def api_public_listings():
    """NO AUTH — only safe, public fields."""
    return {"listings": db.public_listings(),
            "contact_phone": db.get_setting("contact_phone", ""),
            "agency_name": db.get_setting("agency_name", "")}


@app.get("/api/public/listings/{hid}")
def api_public_listing(hid: int):
    """NO AUTH — single listing, only if available and public."""
    listing = db.public_listing(hid)
    if not listing:
        raise HTTPException(404, "not available")
    return {"listing": listing,
            "contact_phone": db.get_setting("contact_phone", ""),
            "agency_name": db.get_setting("agency_name", "")}


@app.get("/share")
def share_page():
    return FileResponse(os.path.join(STATIC, "share.html"))


@app.get("/share/{hid}")
def share_one_page(hid: int):
    return FileResponse(os.path.join(STATIC, "share.html"))


@app.get("/{hid}")
def share_short(hid: int):
    """domain/5 → public page of house 5."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/share/{hid}")


# ------------------- analytics -------------------
@app.get("/api/analytics")
def api_analytics(user=Depends(current_user)):
    cn = db.counts()
    return {
        "monthly": db.monthly_series(12),
        "occupancy": {"rented": cn["rented"], "free": cn["rent_free"]},
        "houses_net": db.houses_net(),
    }


# ------------------- reports -------------------
@app.get("/api/reports")
def api_reports(user=Depends(current_user)):
    today = date.today()
    income, expense, sales = db.month_summary(today.year, today.month)
    return {
        "counts": db.counts(),
        "debtors": db.debtors(today),
        "month": {"year": today.year, "month": today.month,
                  "income": db.rows_to_dicts(income),
                  "expense": db.rows_to_dicts(expense),
                  "sales": db.rows_to_dicts(sales)},
    }


# ------------------- static -------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.exception_handler(HTTPException)
async def http_exc(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
